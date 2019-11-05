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

r"""
Blueprints describe the geometric and composition details of the objects in the reactor
(e.g. fuel assemblies, control rods, etc.).

Inputs captured within this blueprints module pertain to major design criteria like
custom material properties or basic structures like the assemblies in use.

This is essentially a wrapper for a yaml loader.
The given yaml file is expected to rigidly adhere to given key:value pairings.

See the :doc:`blueprints documentation </user/inputs/blueprints>` for more details.

The file structure is expectation is:

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


Notes
-----
The blueprints system was built to enable round trip translations between
text representations of input and objects in the code.


"""
import copy
import collections
from collections import OrderedDict
import os
import traceback

import tabulate

import six
import yamlize
import yamlize.objects
import ordered_set

import armi
from armi import context
from armi import runLog
from armi import settings
from armi import plugins
from armi.localization.exceptions import InputError
from armi.nucDirectory import nuclideBases

# NOTE: using non-ARMI-standard imports because these are all a part of this package,
# and using the module imports would make the attribute definitions extremely long
# without adding detail
from armi.reactor.blueprints.reactorBlueprint import Systems
from armi.reactor.blueprints.assemblyBlueprint import AssemblyKeyedList
from armi.reactor.blueprints.blockBlueprint import BlockKeyedList
from armi.reactor.blueprints.isotopicOptions import (
    NuclideFlags,
    NuclideFlag,
    CustomIsotopics,
)
from armi.reactor.blueprints.gridBlueprint import Grids

context.BLUEPRINTS_IMPORTED = True
context.BLUEPRINTS_IMPORT_CONTEXT = "".join(traceback.format_stack())


def loadFromCs(cs):
    """
    Function to load Blueprints based on supplied ``CaseSettings``.
    """
    from armi.utils import directoryChangers  # circular import protection

    with directoryChangers.DirectoryChanger(cs.inputDirectory):
        with open(cs["loadingFile"], "r") as bpYaml:
            try:
                bp = Blueprints.load(bpYaml)
            except yamlize.yamlizing_error.YamlizingError as err:
                if "cross sections" in err.args[0]:
                    runLog.error(
                        "The loading file {} contains invalid `cross sections` input. "
                        "Please run the `modify` entry point on this case to automatically convert."
                        "".format(cs["loadingFile"])
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
        # pylint: disable=no-member
        plugins = armi.getPluginManager()
        if plugins is None:
            runLog.warning(
                "Blueprints were instantiated before the framework was "
                "configured with plugins. Blueprints cannot be imported before "
                "ARMI has been configured."
            )
        else:
            pluginSections = plugins.hook.defineBlueprintsSections()
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

        return yamlize.objects.ObjectType.__new__(mcs, name, bases, attrs)


@six.add_metaclass(_BlueprintsPluginCollector)
class Blueprints(yamlize.Object):
    """Base Blueprintsobject representing all the subsections in the input file."""

    nuclideFlags = yamlize.Attribute(
        key="nuclide flags", type=NuclideFlags, default=None
    )
    customIsotopics = yamlize.Attribute(
        key="custom isotopics", type=CustomIsotopics, default=None
    )
    blockDesigns = yamlize.Attribute(key="blocks", type=BlockKeyedList, default=None)
    assemDesigns = yamlize.Attribute(
        key="assemblies", type=AssemblyKeyedList, default=None
    )
    systemDesigns = yamlize.Attribute(key="systems", type=Systems, default=None)
    gridDesigns = yamlize.Attribute(key="grids", type=Grids, default=None)

    # These are used to set up new attributes that come from plugins. Defining its
    # initial state here to make pylint happy
    _resolveFunctions = []

    def __new__(cls):
        # yamlizable does not call __init__, so attributes that are not defined above
        # need to be initialized here
        self = yamlize.Object.__new__(cls)
        self.assemblies = {}
        self._prepped = False
        self._assembliesBySpecifier = {}
        self.allNuclidesInProblem = (
            ordered_set.OrderedSet()
        )  # Better for performance since these are used for lookups
        self.activeNuclides = ordered_set.OrderedSet()
        self.inertNuclides = ordered_set.OrderedSet()
        self.elementsToExpand = []
        return self

    def __init__(self):
        # again, yamlize does not call __init__, instead we use Blueprints.load which creates and
        # instance of a Blueprints object and initializes it with values using setattr. Since the
        # method is never called, it serves the purpose of preventing pylint from issuing warnings
        # about attributes not existing.
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

    def constructAssem(self, geomType, cs, name=None, specifier=None):
        """
        Construct a new assembly instance from the assembly designs in this Blueprints object.

        Parameters
        ----------
        geomType : str
            string indicating the geometry type. This is used to select the correct
            Assembly and Block subclasses. ``'hex'`` should be used to create hex
            assemblies. This input is derived based on the Geometry object, though it
            would be nice to instead infer it from block components, and then possibly
            fail if there is mismatch. Though, you can fit a round peg in a square hole
            so long as D <= s.

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
        self._prepConstruction(geomType, cs)

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

    def _prepConstruction(self, geomType, cs):
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

            self._checkAssemblyAreaConsistency(cs)

            runLog.header("=========== Verifying Assembly Configurations ===========")

            # pylint: disable=no-member
            armi.getPluginManagerOrFail().hook.afterConstructionOfAssemblies(
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
        """Expands the density of any elemental nuclides to its natural isotopics."""

        from armi import utils

        # expand burn-chain to only contain nuclides, no elements
        actives = set()
        inerts = set()
        undefBurnChainActiveNuclides = set()
        if self.nuclideFlags is None:
            self.nuclideFlags = genDefaultNucFlags()
        for nucFlag in self.nuclideFlags:
            nucFlag.prepForCase(actives, inerts, undefBurnChainActiveNuclides)

        inerts -= actives
        self.customIsotopics = self.customIsotopics or CustomIsotopics()
        self.elementsToExpand = []

        elementalsToSkip = self._selectNuclidesToExpandForModeling(cs)

        # if elementalsToSkip=[CR], we expand everything else. e.g. CR -> CR (unchanged)
        nucsFromInput = actives | inerts  # join

        for elemental in nuclideBases.instances:
            if not isinstance(elemental, nuclideBases.NaturalNuclideBase):
                continue
            if elemental.name not in nucsFromInput:
                continue

            # we've now confirmed this elemental is in the problem
            if elemental in elementalsToSkip:
                continue

            nucsInProblem = actives if elemental.name in actives else inerts
            nucsInProblem.remove(elemental.name)

            self.elementsToExpand.append(elemental.element)

            for nb in elemental.element.getNaturalIsotopics():
                nucsInProblem.add(nb.name)

        if self.elementsToExpand:
            runLog.info(
                "Expanding {} elementals to have natural isotopics".format(
                    ", ".join(element.symbol for element in self.elementsToExpand)
                )
            )

        self.activeNuclides = ordered_set.OrderedSet(sorted(actives))
        self.inertNuclides = ordered_set.OrderedSet(sorted(inerts))
        self.allNuclidesInProblem = ordered_set.OrderedSet(
            sorted(actives.union(inerts))
        )

        # Inform user that the burn-chain may not be complete
        if undefBurnChainActiveNuclides:
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

    @staticmethod
    def _selectNuclidesToExpandForModeling(cs):
        elementalsToSkip = set()
        endf70Elementals = [nuclideBases.byName[name] for name in ["C", "V", "ZN"]]
        endf71Elementals = [nuclideBases.byName[name] for name in ["C"]]
        endf80Elementals = []

        if "MCNP" in cs["neutronicsKernel"]:
            if int(cs["mcnpLibrary"]) == 50:
                elementalsToSkip.update(nuclideBases.instances)  # skip expansion
            # ENDF/B VII.0
            elif 70 <= int(cs["mcnpLibrary"]) <= 79:
                elementalsToSkip.update(endf70Elementals)
            # ENDF/B VII.1
            elif 80 <= int(cs["mcnpLibrary"]) <= 89:
                elementalsToSkip.update(endf71Elementals)
            else:
                raise InputError(
                    "Failed to determine nuclides for modeling. "
                    "The `mcnpLibrary` setting value ({}) is not supported.".format(
                        cs["mcnpLibrary"]
                    )
                )

        elif cs["xsKernel"] in ["SERPENT", "MC2v3", "MC2v3-PARTISN"]:
            elementalsToSkip.update(endf70Elementals)
        elif cs["xsKernel"] == "DRAGON":
            # Users need to use default nuclear lib name. This is documented.
            dragLib = cs["dragonDataPath"]
            # only supports ENDF/B VII/VIII at the moment.
            if "7r0" in dragLib:
                elementalsToSkip.update(endf70Elementals)
            elif "7r1" in dragLib:
                elementalsToSkip.update(endf71Elementals)
            elif "8r0" in dragLib:
                elementalsToSkip.update(endf80Elementals)
            else:
                raise ValueError(
                    f"Unrecognized DRAGLIB name: {dragLib} Use default file name."
                )

        elif cs["xsKernel"] == "MC2v2":
            elementalsToSkip.update(nuclideBases.instances)  # skip expansion

        return elementalsToSkip

    def _checkAssemblyAreaConsistency(self, cs):
        references = None
        for a in self.assemblies.values():
            if references is None:
                references = (a, a.getArea())
                continue

            assemblyArea = a.getArea()
            if abs(references[1] - assemblyArea) > 1e-9 and not hasattr(
                a.location, "ThRZmesh"
            ):
                # if the location has a mesh then the assemblies can have irregular areas
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
                    > cs["acceptableBlockAreaError"]
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


def genDefaultNucFlags():
    """Perform all the yamlize-required type conversions."""
    flagsDict = nuclideBases.getDefaultNuclideFlags()
    flags = NuclideFlags()
    for nucName, nucFlags in flagsDict.items():
        flag = NuclideFlag(nucName, nucFlags["burn"], nucFlags["xs"])
        flags[nucName] = flag
    return flags
