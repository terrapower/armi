# Copyright 2019 TerraPower, LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Blueprints describe the geometric and composition details of the objects in the reactor
(e.g. fuel assemblies, control rods, etc.).

Inputs captured within this blueprints module pertain to major design criteria like
custom material properties or basic structures like the assemblies in use.

This is essentially a wrapper for a yaml loader.
The given yaml file is expected to rigidly adhere to given key:value pairings.

See the :doc:`blueprints documentation </user/inputs/blueprints>` for more details.

The file structure is expectation is::

    nuclide flags:
        AM241: {burn: true, xs: true}
        ...

    custom isotopics: {} # optional

    blocks:
        name:
            component name:
                component dimensions
        ...

    assemblies:
        name:
            specifier: ABC
            blocks: [...]
            height: [...]
            axial mesh points: [...]
            xs types: [...]

            # optional
            myMaterialModification1: [...]
            myMaterialModification2: [...]

            # optionally extra settings (note this is probably going to be a removed feature)
            #    hotChannelFactors: TWRPclad

Examples
--------
>>> design = blueprints.Blueprints.load(self.yamlString)
>>> print(design.gridDesigns)

Notes
-----
The blueprints system was built to enable round trip translations between
text representations of input and objects in the code.
"""
import copy
import os
import pathlib
import traceback
import typing

from ruamel.yaml import CLoader, RoundTripLoader
import ordered_set
import tabulate
import yamlize
import yamlize.objects

from armi import context
from armi import getPluginManager, getPluginManagerOrFail
from armi import plugins
from armi import runLog
from armi.nucDirectory import nuclideBases
from armi.reactor import assemblies
from armi.reactor import geometry
from armi.reactor import systemLayoutInput
from armi.reactor.flags import Flags
from armi.scripts import migration
from armi.utils.customExceptions import InputError
from armi.utils import textProcessors
from armi.settings.fwSettings.globalSettings import (
    CONF_DETAILED_AXIAL_EXPANSION,
    CONF_ASSEM_FLAGS_SKIP_AXIAL_EXP,
    CONF_INPUT_HEIGHTS_HOT,
    CONF_NON_UNIFORM_ASSEM_FLAGS,
    CONF_ACCEPTABLE_BLOCK_AREA_ERROR,
    CONF_GEOM_FILE,
)
from armi.physics.neutronics.settings import CONF_LOADING_FILE

# NOTE: using non-ARMI-standard imports because these are all a part of this package,
# and using the module imports would make the attribute definitions extremely long
# without adding detail
from armi.reactor.blueprints import isotopicOptions
from armi.reactor.blueprints.assemblyBlueprint import AssemblyKeyedList
from armi.reactor.blueprints.blockBlueprint import BlockKeyedList
from armi.reactor.blueprints.componentBlueprint import ComponentGroups
from armi.reactor.blueprints.componentBlueprint import ComponentKeyedList
from armi.reactor.blueprints.gridBlueprint import Grids, Triplet
from armi.reactor.blueprints.reactorBlueprint import Systems, SystemBlueprint
from armi.reactor.converters import axialExpansionChanger

context.BLUEPRINTS_IMPORTED = True
context.BLUEPRINTS_IMPORT_CONTEXT = "".join(traceback.format_stack())


def loadFromCs(cs, roundTrip=False):
    r"""Function to load Blueprints based on supplied ``CaseSettings``."""
    from armi.utils import directoryChangers

    with directoryChangers.DirectoryChanger(cs.inputDirectory, dumpOnException=False):
        with open(cs[CONF_LOADING_FILE], "r") as bpYaml:
            root = pathlib.Path(cs[CONF_LOADING_FILE]).parent.absolute()
            bpYaml = textProcessors.resolveMarkupInclusions(bpYaml, root)
            try:
                bp = Blueprints.load(bpYaml, roundTrip=roundTrip)
            except yamlize.yamlizing_error.YamlizingError as err:
                if "cross sections" in err.args[0]:
                    runLog.error(
                        "The loading file {} contains invalid `cross sections` input. "
                        "Please run the `modify` entry point on this case to automatically convert."
                        "".format(cs[CONF_LOADING_FILE])
                    )
                raise
    return bp


class _BlueprintsPluginCollector(yamlize.objects.ObjectType):
    """
    Simple metaclass for adding yamlize.Attributes from plugins to Blueprints.

    This calls the defineBlueprintsSections() plugin hook to discover new class
    attributes to add before the yamlize code fires off to make the root yamlize.Object.
    Since yamlize.Object itself uses a metaclass to define the attributes to turn into
    yamlize.Attributes, these need to be folded in early.
    """

    def __new__(mcs, name, bases, attrs):
        pm = getPluginManager()
        if pm is None:
            runLog.warning(
                "Blueprints were instantiated before the framework was "
                "configured with plugins. Blueprints cannot be imported before "
                "ARMI has been configured."
            )
        else:
            pluginSections = pm.hook.defineBlueprintsSections()
            for plug in pluginSections:
                for (attrName, section, resolver) in plug:
                    assert isinstance(section, yamlize.Attribute)
                    if attrName in attrs:
                        raise plugins.PluginError(
                            "There is already a section called '{}' in the reactor "
                            "blueprints".format(attrName)
                        )
                    attrs[attrName] = section
                    attrs["_resolveFunctions"].append(resolver)

        newType = yamlize.objects.ObjectType.__new__(mcs, name, bases, attrs)

        return newType


class Blueprints(yamlize.Object, metaclass=_BlueprintsPluginCollector):
    """Base Blueprintsobject representing all the subsections in the input file."""

    nuclideFlags = yamlize.Attribute(
        key="nuclide flags", type=isotopicOptions.NuclideFlags, default=None
    )
    customIsotopics = yamlize.Attribute(
        key="custom isotopics", type=isotopicOptions.CustomIsotopics, default=None
    )
    blockDesigns = yamlize.Attribute(key="blocks", type=BlockKeyedList, default=None)
    assemDesigns = yamlize.Attribute(
        key="assemblies", type=AssemblyKeyedList, default=None
    )
    systemDesigns = yamlize.Attribute(key="systems", type=Systems, default=None)
    gridDesigns = yamlize.Attribute(key="grids", type=Grids, default=None)
    componentDesigns = yamlize.Attribute(
        key="components", type=ComponentKeyedList, default=None
    )
    componentGroups = yamlize.Attribute(
        key="component groups", type=ComponentGroups, default=None
    )

    # These are used to set up new attributes that come from plugins.
    _resolveFunctions = []

    def __new__(cls):
        # yamlizable does not call __init__, so attributes that are not defined above
        # need to be initialized here
        self = yamlize.Object.__new__(cls)
        self.assemblies = {}
        self._prepped = False
        self._assembliesBySpecifier = {}

        # Better for performance since these are used for lookups
        self.allNuclidesInProblem = ordered_set.OrderedSet()
        self.activeNuclides = ordered_set.OrderedSet()
        self.inertNuclides = ordered_set.OrderedSet()
        self.nucsToForceInXsGen = ordered_set.OrderedSet()
        self.elementsToExpand = []
        return self

    def __init__(self):
        # Yamlize does not call __init__, instead we use Blueprints.load which
        # creates and instance of a Blueprints object and initializes it with values
        # using setattr.
        self._assembliesBySpecifier = {}
        self._prepped = False
        self.systemDesigns = Systems()
        self.assemDesigns = AssemblyKeyedList()
        self.blockDesigns = BlockKeyedList()
        self.assemblies = {}
        self.grids = Grids()
        self.elementsToExpand = []

    def __repr__(self):
        return "<{} Assemblies:{} Blocks:{}>".format(
            self.__class__.__name__, len(self.assemDesigns), len(self.blockDesigns)
        )

    def constructAssem(self, cs, name=None, specifier=None):
        """
        Construct a new assembly instance from the assembly designs in this Blueprints object.

        Parameters
        ----------
        cs : CaseSettings object
            Used to apply various modeling options when constructing an assembly.

        name : str (optional, and should be exclusive with specifier)
            Name of the assembly to construct. This should match the key that was used
            to define the assembly in the Blueprints YAML file.

        specifier : str (optional, and should be exclusive with name)
            Identifier of the assembly to construct. This should match the identifier
            that was used to define the assembly in the Blueprints YAML file.

        Raises
        ------
        ValueError
            If neither name nor specifier are passed

        Notes
        -----
        There is some possibility for "compiling" the logic with closures to make
        constructing an assembly / block / component faster. At this point is is pretty
        much irrelevant because we are currently just deepcopying already constructed
        assemblies.

        Currently, this method is backward compatible with other code in ARMI and
        generates the `.assemblies` attribute (the BOL assemblies). Eventually, this
        should be removed.
        """
        self._prepConstruction(cs)

        # TODO: this should be migrated assembly designs instead of assemblies
        if name is not None:
            assem = self.assemblies[name]
        elif specifier is not None:
            assem = self._assembliesBySpecifier[specifier]
        else:
            raise ValueError("Must supply assembly name or specifier to construct")

        a = copy.deepcopy(assem)
        # since a deepcopy has the same assembly numbers and block id's, we need to make it unique
        a.makeUnique()
        return a

    def _prepConstruction(self, cs):
        """
        This method initializes a bunch of information within a Blueprints object such
        as assigning assembly and block type numbers, resolving the nuclides in the
        problem, and pre-populating assemblies.

        Ideally, it would not be necessary at all, but the ``cs`` currently contains a
        bunch of information necessary to create the applicable model. If it were
        possible, it would be terrific to override the Yamlizable.from_yaml method to
        run this code after the instance has been created, but we need additional
        information in order to build the assemblies that is not within the YAML file.

        This method should not be called directly, but it is used in testing.
        """
        if not self._prepped:
            self._assignTypeNums()
            for func in self._resolveFunctions:
                func(self, cs)
            self._resolveNuclides(cs)
            self._assembliesBySpecifier.clear()
            self.assemblies.clear()

            for aDesign in self.assemDesigns:
                a = aDesign.construct(cs, self)
                self._assembliesBySpecifier[aDesign.specifier] = a
                self.assemblies[aDesign.name] = a

            runLog.header("=========== Verifying Assembly Configurations ===========")
            self._checkAssemblyAreaConsistency(cs)

            if not cs[CONF_DETAILED_AXIAL_EXPANSION]:
                # this is required to set up assemblies so they know how to snap
                # to the reference mesh. They wont know the mesh to conform to
                # otherwise....
                axialExpansionChanger.makeAssemsAbleToSnapToUniformMesh(
                    self.assemblies.values(), cs[CONF_NON_UNIFORM_ASSEM_FLAGS]
                )

            if not cs[CONF_INPUT_HEIGHTS_HOT]:
                runLog.header(
                    "=========== Axially expanding all assemblies from Tinput to Thot ==========="
                )
                # expand axial heights from cold to hot so dims and masses are consistent
                # with specified component hot temperatures.
                assemsToSkip = [
                    Flags.fromStringIgnoreErrors(t)
                    for t in cs[CONF_ASSEM_FLAGS_SKIP_AXIAL_EXP]
                ]
                assemsToExpand = list(
                    a
                    for a in list(self.assemblies.values())
                    if not any(a.hasFlags(f) for f in assemsToSkip)
                )
                axialExpansionChanger.expandColdDimsToHot(
                    assemsToExpand,
                    cs[CONF_DETAILED_AXIAL_EXPANSION],
                )

            getPluginManagerOrFail().hook.afterConstructionOfAssemblies(
                assemblies=self.assemblies.values(), cs=cs
            )

        self._prepped = True

    def _assignTypeNums(self):
        if self.blockDesigns is None:
            # this happens when directly defining assemblies.
            self.blockDesigns = BlockKeyedList()
            for aDesign in self.assemDesigns:
                for bDesign in aDesign.blocks:
                    if bDesign not in self.blockDesigns:
                        self.blockDesigns.add(bDesign)

    def _resolveNuclides(self, cs):
        """
        Process elements and determine how to expand them to natural isotopics.

        Also builds meta-data about which nuclides are in the problem.

        This system works by building a dictionary in the
        ``elementsToExpand`` attribute with ``Element`` keys
        and list of ``NuclideBase`` values.

        The actual expansion of elementals to isotopics occurs during
        :py:meth:`Component construction <armi.reactor.blueprints.componentBlueprint.
        ComponentBlueprint._constructMaterial>`.
        """
        from armi import utils

        actives = set()
        inerts = set()

        nuclideFlags = self.nuclideFlags or isotopicOptions.genDefaultNucFlags()

        nucsToForceInXsGen = set()
        # just expanding flags now. ndense gets expanded in comp blueprints
        self.elementsToExpand = []
        for nucFlag in nuclideFlags:
            # this returns any nuclides that are flagged specifically for expansion by input
            (
                expandedElements,
                undefBurnChainActiveNuclides,
            ) = nucFlag.fileAsActiveOrInert(
                actives,
                inerts,
            )
            self.elementsToExpand.extend(expandedElements)

        inerts -= actives
        self.customIsotopics = self.customIsotopics or isotopicOptions.CustomIsotopics()
        eleKeep, eleExpand = isotopicOptions.eleExpandInfoBasedOnCodeENDF(cs)

        # Flag all elementals for expansion unless they've been flagged otherwise by
        # user input or automatic lattice/datalib rules.
        for nucBase in nuclideBases.instances:
            isAlreadyIsotopic = not isinstance(nucBase, nuclideBases.NaturalNuclideBase)
            if isAlreadyIsotopic:
                # `elemental` may be a NaturalNuclideBase or a NuclideBase
                # skip all NuclideBases (isotopics)
                continue

            # we now know its an elemental
            elemental = nucBase
            if elemental in eleKeep:
                continue

            if elemental.name in actives:
                currentSet = actives
            elif elemental.name in inerts:
                currentSet = inerts
            else:
                # This was not specified in the nuclide flags at all as burn or xs.
                # If a material with this in its composition is brought in
                # it's nice from a user perspective to allow it.
                # But current behavior is that all nuclides in problem
                # must be declared up front.
                continue

            self.elementsToExpand.append(elemental.element)

            if (
                elemental.name in nuclideFlags
                and nuclideFlags[elemental.element.symbol].expandTo
            ):
                # user-input expandTo has precedence
                newNuclides = [
                    nuclideBases.byName[nn]
                    for nn in nuclideFlags[elemental.element.symbol].expandTo
                ]
            elif elemental in eleExpand and elemental.element.symbol in nuclideFlags:
                # code-specific expansion required based on code and ENDF
                newNuclides = eleExpand[elemental]
                # overlay code details onto nuclideFlags for other parts of the code
                # that will use them.
                # TODO: would be better if nuclideFlags did this upon reading s.t.
                # order didn't matter. On the other hand, this is the only place in
                # the code where NuclideFlags get built and have user settings around
                # (hence "resolve").
                # This must be updated because the operative expansion code just uses the flags
                #
                # Also, if this element is not in nuclideFlags at all, we just don't add it
                nuclideFlags[elemental.element.symbol].expandTo = [
                    nb.name for nb in newNuclides
                ]
            else:
                # expand to all possible natural isotopics
                newNuclides = elemental.element.getNaturalIsotopics()

            # remove the elemental and add the isotopic
            currentSet.remove(elemental.name)
            for nb in newNuclides:
                currentSet.add(nb.name)

        # force everything asked for in xsGen
        nucsToForceInXsGen = ordered_set.OrderedSet(sorted(actives.union(inerts)))

        # add all detailed isotopes in ENDF if requested
        isotopicOptions.autoUpdateNuclideFlags(cs, nuclideFlags, inerts)
        self.nuclideFlags = nuclideFlags

        if self.elementsToExpand:
            runLog.info(
                "Will expand {} elementals to have natural isotopics".format(
                    ", ".join(element.symbol for element in self.elementsToExpand)
                )
            )

        self.activeNuclides = ordered_set.OrderedSet(sorted(actives))
        self.inertNuclides = ordered_set.OrderedSet(sorted(inerts))
        self.allNuclidesInProblem = ordered_set.OrderedSet(
            sorted(actives.union(inerts))
        )
        self.nucsToForceInXsGen = ordered_set.OrderedSet(sorted(nucsToForceInXsGen))

        # Inform user which nuclides are truncating the burn chain.
        if undefBurnChainActiveNuclides and nuclideBases.burnChainImposed:
            runLog.info(
                tabulate.tabulate(
                    [
                        [
                            "Nuclides truncating the burn-chain:",
                            utils.createFormattedStrWithDelimiter(
                                list(undefBurnChainActiveNuclides)
                            ),
                        ]
                    ],
                    tablefmt="plain",
                ),
                single=True,
            )

    def _checkAssemblyAreaConsistency(self, cs):
        references = None
        for a in self.assemblies.values():
            if references is None:
                references = (a, a.getArea())
                continue

            assemblyArea = a.getArea()
            if isinstance(a, assemblies.RZAssembly):
                # R-Z assemblies by definition have different areas, so skip the check
                continue
            if abs(references[1] - assemblyArea) > 1e-9:
                runLog.error("REFERENCE COMPARISON ASSEMBLY:")
                references[0][0].printContents()
                runLog.error("CURRENT COMPARISON ASSEMBLY:")
                a[0].printContents()
                raise InputError(
                    "Assembly {} has a different area {} than assembly {} {}.  Check inputs for accuracy".format(
                        a, assemblyArea, references[0], references[1]
                    )
                )

            blockArea = a[0].getArea()
            for b in a[1:]:
                if (
                    abs(b.getArea() - blockArea) / blockArea
                    > cs[CONF_ACCEPTABLE_BLOCK_AREA_ERROR]
                ):
                    runLog.error("REFERENCE COMPARISON BLOCK:")
                    a[0].printContents(includeNuclides=False)
                    runLog.error("CURRENT COMPARISON BLOCK:")
                    b.printContents(includeNuclides=False)

                    for c in b.getChildren():
                        runLog.error(
                            "{0} area {1} effective area {2}"
                            "".format(c, c.getArea(), c.getVolume() / b.getHeight())
                        )

                    raise InputError(
                        "Block {} has a different area {} than block {} {}. Check inputs for accuracy".format(
                            b, b.getArea(), a[0], blockArea
                        )
                    )

    @classmethod
    def migrate(cls, inp: typing.TextIO):
        """Given a stream representation of a blueprints file, migrate it.

        Parameters
        ----------
        inp : typing.TextIO
            Input stream to migrate.
        """
        for migI in migration.ACTIVE_MIGRATIONS:
            if issubclass(migI, migration.base.BlueprintsMigration):
                mig = migI(stream=inp)
                inp = mig.apply()
        return inp

    @classmethod
    def load(cls, stream, roundTrip=False):
        """This class method is a wrapper around the `yamlize.Object.load()` method.

        The reason for the wrapper is to allow us to default to `Cloader`. Essentially,
        the `CLoader` class is 10x faster, but doesn't allow for "round trip" (read-
        write) access to YAMLs; for that we have the `RoundTripLoader`.
        """
        loader = RoundTripLoader if roundTrip else CLoader
        return super().load(stream, Loader=loader)

    def addDefaultSFP(self):
        """Create a default SFP if it's not in the blueprints."""
        if self.systemDesigns is not None:
            if not any(structure.typ == "sfp" for structure in self.systemDesigns):
                sfp = SystemBlueprint("Spent Fuel Pool", "sfp", Triplet())
                sfp.typ = "sfp"
                self.systemDesigns["Spent Fuel Pool"] = sfp
        else:
            runLog.warning(
                f"Can't add default SFP to {self}, there are no systemDesigns!"
            )


def migrate(bp: Blueprints, cs):
    """
    Apply migrations to the input structure.

    This is a good place to perform migrations that address changes to the system design
    description (settings, blueprints, geom file). We have access to all three here, so
    we can even move stuff between files. Namely, this:

     * creates a grid blueprint to represent the core layout from the old ``geomFile``
       setting, and applies that grid to a ``core`` system.
     * moves the radial and azimuthal submesh values from the ``geomFile`` to the
       assembly designs, but only if they are uniform (this is limiting, but could be
       made more sophisticated in the future, if there is need)

    This allows settings-driven core map to still be used for backwards compatibility.
    At some point once the input stabilizes, we may wish to move this out to the
    dedicated migration portion of the code, and not perform the migration so
    implicitly.
    """
    from armi.reactor.blueprints import gridBlueprint

    if bp.systemDesigns is None:
        bp.systemDesigns = Systems()
    if bp.gridDesigns is None:
        bp.gridDesigns = gridBlueprint.Grids()

    if "core" in [rd.name for rd in bp.gridDesigns]:
        raise ValueError("Cannot auto-create a 2nd `core` grid. Adjust input.")

    geom = systemLayoutInput.SystemLayoutInput()
    geom.readGeomFromFile(os.path.join(cs.inputDirectory, cs[CONF_GEOM_FILE]))
    gridDesigns = geom.toGridBlueprints("core")
    for design in gridDesigns:
        bp.gridDesigns[design.name] = design

    if "core" in [rd.name for rd in bp.systemDesigns]:
        raise ValueError(
            "Core map is defined in both the ``geometry`` setting and in "
            "the blueprints file. Only one definition may exist. "
            "Update inputs."
        )
    bp.systemDesigns["core"] = SystemBlueprint("core", "core", Triplet())

    if geom.geomType in (geometry.GeomType.RZT, geometry.GeomType.RZ):
        aziMeshes = {indices[4] for indices, _ in geom.assemTypeByIndices.items()}
        radMeshes = {indices[5] for indices, _ in geom.assemTypeByIndices.items()}

        if len(aziMeshes) > 1 or len(radMeshes) > 1:
            raise ValueError(
                "The system layout described in {} has non-uniform "
                "azimuthal and/or radial submeshing. This migration is currently "
                "only smart enough to handle a single radial and single azimuthal "
                "submesh for all assemblies.".format(cs[CONF_GEOM_FILE])
            )
        radMesh = next(iter(radMeshes))
        aziMesh = next(iter(aziMeshes))

        for _, aDesign in bp.assemDesigns.items():
            aDesign.radialMeshPoints = radMesh
            aDesign.azimuthalMeshPoints = aziMesh

    # Someday: write out the migrated file. At the moment this messes up the case
    # title and doesn't yet have the other systems in place so this isn't the right place.


#     cs.writeToXMLFile(cs.caseTitle + '.migrated.xml')
#     with open(os.path.split(cs['loadingFile'])[0] + '.migrated.' + '.yaml', 'w') as loadingFile:
#         blueprints.Blueprints.dump(bp, loadingFile)
