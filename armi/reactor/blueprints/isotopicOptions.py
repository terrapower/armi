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
Defines nuclide flags and custom isotopics via input.

Nuclide flags control meta-data about nuclides. Custom isotopics
allow specification of arbitrary isotopic compositions.
"""

import yamlize

from armi import materials, runLog
from armi.nucDirectory import elements, nucDir, nuclideBases
from armi.physics.neutronics.fissionProductModel.fissionProductModelSettings import (
    CONF_FISSION_PRODUCT_LIBRARY_NAME,
    CONF_FP_MODEL,
)
from armi.physics.neutronics.settings import (
    CONF_MCNP_LIB_BASE,
    CONF_NEUTRONICS_KERNEL,
    CONF_XS_KERNEL,
)
from armi.utils import densityTools, units
from armi.utils.customExceptions import InputError

ALLOWED_KEYS = set(nuclideBases.byName.keys()) | set(elements.bySymbol.keys())


class NuclideFlag(yamlize.Object):
    """
    Defines whether or not each nuclide is included in the burn chain and cross sections.

    Also controls which nuclides get expanded from elementals to isotopics and which natural
    isotopics to exclude (if any). Oftentimes, cross section library creators include some natural
    isotopes but not all. For example, it is common to include O16 but not O17 or O18. Each code has
    slightly different interpretations of this so we give the user full control here.

    We also try to provide useful defaults.

    There are lots of complications that can arise in these choices. It makes reasonable sense to
    use elemental compositions for things that are typically used  without isotopic modifications
    (Fe, O, Zr, Cr, Na). If we choose to expand some or all of these to isotopics at initialization
    based on cross section library requirements, a single case will work fine with a given lattice
    physics option. However, restarting from that case with different cross section needs is
    challenging.

    .. impl:: The blueprint object that represents a nuclide flag.
        :id: I_ARMI_BP_NUC_FLAGS1
        :implements: R_ARMI_BP_NUC_FLAGS

        This class creates a yaml interface for the user to specify in their blueprints which
        isotopes should be depleted. It is incorporated into the "nuclide flags" section of a
        blueprints file by being included as key-value pairs within the
        :py:class:`~armi.reactor.blueprints.isotopicOptions.NuclideFlags` class, which is in turn
        included into the overall blueprints within :py:class:`~armi.reactor.blueprints.Blueprints`.

        This class includes a boolean ``burn`` attribute which can be specified for any nuclide.
        This attribute is examined by the
        :py:meth:`~armi.reactor.blueprints.isotopicOptions.NuclideFlag.fileAsActiveOrInert` method
        to sort the nuclides into sets of depletable or not, which is typically called during
        construction of assemblies in :py:meth:`~armi.reactor.blueprints.Blueprints.constructAssem`.

        Note that while the ``burn`` attribute can be set by the user in the blueprints, other
        methods may also set it based on case settings (see, for instance,
        :py:func:`~armi.reactor.blueprints.isotopicOptions.genDefaultNucFlags`,
        :py:func:`~armi.reactor.blueprints.isotopicOptions.autoUpdateNuclideFlags`, and
        :py:func:`~armi.reactor.blueprints.isotopicOptions.getAllNuclideBasesByLibrary`).

    Attributes
    ----------
    nuclideName : str
        The name of the nuclide
    burn : bool
        True if this nuclide should be added to the burn chain. If True, all reachable nuclides via
        transmutation and decay must be included as well.
    xs : bool
        True if this nuclide should be included in the cross section libraries. Effectively, if this
        nuclide is in the problem at all, this should be true.
    expandTo : list of str, optional
        isotope nuclideNames to expand to. For example, if nuclideName is ``O`` then this could be
        ``["O16", "O17"]`` to expand it into those two isotopes (but not ``O18``). The nuclides will
        be scaled up uniformly to account for any missing natural nuclides.
    """

    nuclideName = yamlize.Attribute(type=str)

    @nuclideName.validator
    def nuclideName(self, value):
        if value not in ALLOWED_KEYS:
            raise ValueError("`{}` is not a valid nuclide name, must be one of: {}".format(value, ALLOWED_KEYS))

    burn = yamlize.Attribute(type=bool)
    xs = yamlize.Attribute(type=bool)
    expandTo = yamlize.Attribute(type=yamlize.StrList, default=None)

    def __init__(self, nuclideName, burn, xs, expandTo):
        # note: yamlize does not call an __init__ method, instead it uses __new__ and setattr
        self.nuclideName = nuclideName
        self.burn = burn
        self.xs = xs
        self.expandTo = expandTo

    def __repr__(self):
        return "<NuclideFlag name:{} burn:{} xs:{}>".format(self.nuclideName, self.burn, self.xs)

    def fileAsActiveOrInert(self, activeSet, inertSet):
        """
        Given a nuclide or element name, file it as either active or inert.

        If isotopic expansions are requested, include the isotopics
        rather than the NaturalNuclideBase, as the NaturalNuclideBase will never
        occur in such a problem.
        """
        undefBurnChainActiveNuclides = set()
        nb = nuclideBases.byName[self.nuclideName]
        if self.expandTo:
            nucBases = [nuclideBases.byName[nn] for nn in self.expandTo]
            expanded = [nb.element]  # error to expand non-elements
        else:
            nucBases = [nb]
            expanded = []

        for nuc in nucBases:
            if self.burn:
                if not nuc.trans and not nuc.decays:
                    # DUMPs and LFPs usually
                    undefBurnChainActiveNuclides.add(nuc.name)
                activeSet.add(nuc.name)
            if self.xs:
                inertSet.add(nuc.name)
        return expanded, undefBurnChainActiveNuclides


class NuclideFlags(yamlize.KeyedList):
    """An OrderedDict of ``NuclideFlags``, keyed by their ``nuclideName``."""

    item_type = NuclideFlag
    key_attr = NuclideFlag.nuclideName


class CustomIsotopic(yamlize.Map):
    """
    User specified, custom isotopics input defined by a name (such as MOX), and key/pairs of nuclide
    names and numeric values consistent with the ``input format``.

    .. impl:: Certain material modifications will be applied using this code.
        :id: I_ARMI_MAT_USER_INPUT2
        :implements: R_ARMI_MAT_USER_INPUT

        Defines a yaml construct that allows the user to define a custom isotopic vector from within
        their blueprints file, including a name and key-value pairs corresponding to nuclide names
        and their concentrations.

        Relies on the underlying infrastructure from the ``yamlize`` package for reading from text
        files, serialization, and internal storage of the data.

        Is implemented as part of a blueprints file by being used in key-value pairs within the
        :py:class:`~armi.reactor.blueprints.isotopicOptions.CustomIsotopics` class, which is
        imported and used as an attribute within the larger
        :py:class:`~armi.reactor.blueprints.Blueprints` class.

        These isotopics are linked to a component during calls to
        :py:meth:`~armi.reactor.blueprints.componentBlueprint.ComponentBlueprint.construct`, where
        the name specified in the ``isotopics`` attribute of the component blueprint is searched
        against the available ``CustomIsotopics`` defined in the "custom isotopics" section of the
        blueprints. Once linked, the
        :py:meth:`~armi.reactor.blueprints.isotopicOptions.CustomIsotopic.apply` method is called,
        which adjusts the ``massFrac`` attribute of the component's material class.
    """

    key_type = yamlize.Typed(str)
    value_type = yamlize.Typed(float)
    name = yamlize.Attribute(type=str)
    inputFormat = yamlize.Attribute(key="input format", type=str)

    @inputFormat.validator
    def inputFormat(self, value):
        if value not in self._allowedFormats:
            raise ValueError("Cannot set `inputFormat` to `{}`, must be one of: {}".format(value, self._allowedFormats))

    _density = yamlize.Attribute(key="density", type=float, default=None)

    _allowedFormats = {"number fractions", "number densities", "mass fractions"}

    def __new__(cls, *args):
        self = yamlize.Map.__new__(cls, *args)

        # the density as computed by source number densities
        self._computedDensity = None
        return self

    def __init__(self, name, inputFormat, density):
        # note: yamlize does not call an __init__ method, instead it uses __new__ and setattr
        self._name = None
        self.name = name
        self._inputFormat = None
        self.inputFormat = inputFormat
        self.density = density
        self.massFracs = {}

    def __setitem__(self, key, value):
        if key not in ALLOWED_KEYS:
            raise ValueError("Key `{}` is not valid, must be one of: {}".format(key, ALLOWED_KEYS))

        yamlize.Map.__setitem__(self, key, value)

    @property
    def density(self):
        return self._computedDensity or self._density

    @density.setter
    def density(self, value):
        if self._computedDensity is not None:
            raise AttributeError("Density was computed from number densities, and should not be set directly.")
        self._density = value
        if value is not None and value < 0:
            raise ValueError("Cannot set `density` to `{}`, must greater than 0".format(value))

    @classmethod
    def from_yaml(cls, loader, node, rtd):
        """
        Override the ``Yamlizable.from_yaml`` to inject custom data validation logic, and complete initialization of the
        object.
        """
        self = yamlize.Map.from_yaml.__func__(cls, loader, node, rtd)

        try:
            self._initializeMassFracs()
            self._expandElementMassFracs()
        except Exception as ex:
            # use a YamlizingError to get line/column of erroneous input
            raise yamlize.YamlizingError(str(ex), node)

        return self

    @classmethod
    def from_yaml_key_val(cls, loader, key_node, val_node, key_attr, rtd):
        """
        Override the ``Yamlizable.from_yaml`` to inject custom data validation logic, and complete initialization of the
        object.
        """
        self = yamlize.Map.from_yaml_key_val.__func__(cls, loader, key_node, val_node, key_attr, rtd)

        try:
            self._initializeMassFracs()
            self._expandElementMassFracs()
        except Exception as ex:
            # use a YamlizingError to get line/column of erroneous input
            raise yamlize.YamlizingError(str(ex), val_node)

        return self

    def _initializeMassFracs(self):
        self.massFracs = dict()  # defaults to 0.0, __init__ is not called

        if any(v < 0.0 for v in self.values()):
            raise ValueError("Custom isotopic input for {} is negative".format(self.name))

        valSum = sum(self.values())
        if not abs(valSum - 1.0) < 1e-5 and "fractions" in self.inputFormat:
            raise ValueError("Fractional custom isotopic input values must sum to 1.0 in: {}".format(self.name))

        if self.inputFormat == "number fractions":
            sumNjAj = 0.0

            for nuc, nj in self.items():
                if nj:
                    sumNjAj += nj * nucDir.getAtomicWeight(nuc)

            for nuc, value in self.items():
                massFrac = value * nucDir.getAtomicWeight(nuc) / sumNjAj
                self.massFracs[nuc] = massFrac

        elif self.inputFormat == "number densities":
            if self._density is not None:
                raise InputError(
                    "Custom isotopic `{}` is over-specified. It was provided as number "
                    "densities, and but density ({}) was also provided. Is the input format "
                    "correct?".format(self.name, self.density)
                )

            M = {
                nuc: Ni / units.MOLES_PER_CC_TO_ATOMS_PER_BARN_CM * nucDir.getAtomicWeight(nuc)
                for nuc, Ni in self.items()
            }
            densityTotal = sum(M.values())
            if densityTotal < 0:
                raise ValueError("Computed density is negative")

            for nuc, Mi in M.items():
                self.massFracs[nuc] = Mi / densityTotal

            self._computedDensity = densityTotal

        elif self.inputFormat == "mass fractions":
            self.massFracs = dict(self)  # as input

        else:
            raise ValueError("Unrecognized custom isotopics input format {}.".format(self.inputFormat))

    def _expandElementMassFracs(self):
        """
        Expand the custom isotopics input entries that are elementals to isotopics.

        This is necessary when the element name is not a elemental nuclide.
        Most everywhere else expects Nuclide objects (or nuclide names). This input allows a
        user to enter "U" which would expand to the naturally occurring uranium isotopics.

        This is different than the isotopic expansion done for meeting user-specified
        modeling options (such as an MC**2, or MCNP expecting elements or isotopes),
        because it translates the user input into something that can be used later on.
        """
        elementsToExpand = []
        for nucName in self.massFracs:
            if nucName not in nuclideBases.byName:
                element = elements.bySymbol.get(nucName)
                if element is not None:
                    runLog.info(
                        "Expanding custom isotopic `{}` element `{}` to natural isotopics".format(self.name, nucName)
                    )
                    # include all natural isotopes with None flag
                    elementsToExpand.append((element, None))
                else:
                    raise InputError("Unrecognized nuclide/isotope/element in input: {}".format(nucName))

        densityTools.expandElementalMassFracsToNuclides(self.massFracs, elementsToExpand)

    def apply(self, material):
        """
        Apply specific isotopic compositions to a component.

        Generically, materials have composition-dependent bulk properties such as mass density.
        Note that this operation does not update these material properties. Use with care.

        Parameters
        ----------
        material : armi.materials.material.Material
            An ARMI Material instance.
        """
        material.massFrac = dict(self.massFracs)
        if self.density is not None:
            if not isinstance(material, materials.Custom):
                runLog.important(
                    "A custom isotopic with associated density has been specified for non-`Custom` "
                    f"material {material}. The reference density of materials in the materials library "
                    "will not be changed, but the associated components will use the density "
                    "implied by the custom isotopics.",
                    single=True,
                )
                # specifically, non-Custom materials only use refDensity and dLL, mat.customDensity has no effect
                return

            material.customDensity = self.density


class CustomIsotopics(yamlize.KeyedList):
    """OrderedDict of CustomIsotopic objects, keyed by their name."""

    item_type = CustomIsotopic

    key_attr = CustomIsotopic.name

    # note: yamlize does not call an __init__ method, instead it uses __new__ and setattr

    def apply(self, material, customIsotopicsName):
        """
        Apply specific isotopic compositions to a component.

        Generically, materials have composition-dependent bulk properties such as mass density.
        Note that this operation does not update these material properties. Use with care.

        Parameters
        ----------
        material : armi.materials.material.Material
            Material instance to adjust.

        customIsotopicName : str
            String corresponding to the ``CustomIsoptopic.name``.
        """
        if customIsotopicsName not in self:
            raise KeyError(
                "The input custom isotopics do not include {}. The only present specifications are {}".format(
                    customIsotopicsName, self.keys()
                )
            )

        custom = self[customIsotopicsName]
        custom.apply(material)


def getDefaultNuclideFlags():
    """
    Return a default set of nuclides to model and deplete.

    Notes
    -----
    The nuclideFlags input on blueprints has confused new users and is infrequently
    changed. It will be moved to be a user setting, but in any case a reasonable default
    should be provided. We will by default model medium-lived and longer actinides between
    U234 and CM247.

    We will include B10 and B11 without depletion, sodium, and structural elements.

    We will include LFPs with depletion.
    """
    nuclideFlags = {}
    actinides = {
        "U": [234, 235, 236, 238],
        "NP": [237, 238],
        "PU": [236] + list(range(238, 243)),
        "AM": range(241, 244),
        "CM": range(242, 248),
    }

    for el, masses in actinides.items():
        for mass in masses:
            nuclideFlags[f"{el}{mass}"] = {"burn": True, "xs": True, "expandTo": None}

    for fp in [35, 38, 39, 40, 41]:
        nuclideFlags[f"LFP{fp}"] = {"burn": True, "xs": True, "expandTo": None}

    for dmp in [1, 2]:
        nuclideFlags[f"DUMP{dmp}"] = {"burn": True, "xs": True, "expandTo": None}

    for boron in [10, 11]:
        nuclideFlags[f"B{boron}"] = {"burn": False, "xs": True, "expandTo": None}

    for struct in ["ZR", "C", "SI", "V", "CR", "MN", "FE", "NI", "MO", "W", "NA", "HE"]:
        nuclideFlags[struct] = {"burn": False, "xs": True, "expandTo": None}

    return nuclideFlags


def eleExpandInfoBasedOnCodeENDF(cs):
    """
    Intelligently choose elements to expand based on code and ENDF version.

    If settings point to a particular code and library and we know
    that combo requires certain elementals to be expanded, we
    flag them here to make the user input as simple as possible.

    This determines both which elementals to keep and which
    specific expansion subsets to use.

    Notes
    -----
    This logic is expected to be moved to respective plugins in time.

    Returns
    -------
    elementalsToKeep : set
        Set of NaturalNuclideBase instances to not expand into
        natural isotopics.
    expansions : dict
        Element to list of nuclides for expansion.
        For example: {oxygen: [oxygen16]} indicates that all
        oxygen should be expanded to O16, ignoring natural
        O17 and O18. (variables are Natural/NuclideBases)
    """
    elementalsToKeep = set()
    oxygenElementals = [nuclideBases.byName["O"]]
    hydrogenElementals = [nuclideBases.byName[name] for name in ["H"]]
    endf70Elementals = [nuclideBases.byName[name] for name in ["C", "V", "ZN"]]
    endf71Elementals = [nuclideBases.byName[name] for name in ["C"]]
    endf80Elementals = []
    elementalsInMC2 = set()
    expansionStrings = {}
    mc2Expansions = {
        "HE": ["HE4"],  # neglect HE3
        "O": ["O16"],  # neglect O17 and O18
        "W": ["W182", "W183", "W184", "W186"],  # neglect W180
    }
    mcnpExpansions = {"O": ["O16"]}

    for element in elements.byName.values():
        # any NaturalNuclideBase that's available in MC2 libs
        nnb = nuclideBases.byName.get(element.symbol)
        if nnb and nnb.getMcc2Id():
            elementalsInMC2.add(nnb)

    if "MCNP" in cs[CONF_NEUTRONICS_KERNEL]:
        expansionStrings.update(mcnpExpansions)
        if cs[CONF_MCNP_LIB_BASE] == "ENDF/B-V.0":
            # ENDF/B V.0
            elementalsToKeep.update(nuclideBases.instances)  # skip expansion
        elif cs[CONF_MCNP_LIB_BASE] == "ENDF/B-VII.0":
            # ENDF/B VII.0
            elementalsToKeep.update(endf70Elementals)
        elif cs[CONF_MCNP_LIB_BASE] == "ENDF/B-VII.1":
            # ENDF/B VII.1
            elementalsToKeep.update(endf71Elementals)
        elif cs[CONF_MCNP_LIB_BASE] == "ENDF/B-VIII.0":
            # ENDF/B VIII.0
            elementalsToKeep.update(endf80Elementals)
        else:
            raise InputError(
                "Failed to determine nuclides for modeling. The `mcnpLibraryVersion` "
                f"setting value ({cs[CONF_MCNP_LIB_BASE]}) is not supported."
            )

    elif cs[CONF_XS_KERNEL] == "SERPENT":
        elementalsToKeep.update(endf70Elementals)
        expansionStrings.update(mc2Expansions)

    elif cs[CONF_XS_KERNEL] in ["", "MC2v3", "MC2v3-PARTISN"]:
        elementalsToKeep.update(endf71Elementals)
        expansionStrings.update(mc2Expansions)

    elif cs[CONF_XS_KERNEL] == "DRAGON":
        # Users need to use default nuclear lib name. This is documented.
        dragLib = cs["dragonDataPath"]
        # only supports ENDF/B VII/VIII at the moment.
        if "7r0" in dragLib:
            elementalsToKeep.update(endf70Elementals)
        elif "7r1" in dragLib:
            elementalsToKeep.update(endf71Elementals)
        elif "8r0" in dragLib:
            elementalsToKeep.update(endf80Elementals)
            elementalsToKeep.update(hydrogenElementals)
            elementalsToKeep.update(oxygenElementals)
        else:
            raise ValueError(f"Unrecognized DRAGLIB name: {dragLib} Use default file name.")

    elif cs[CONF_XS_KERNEL] == "MC2v2":
        # strip out any NaturalNuclideBase with no getMcc2Id() (not on mcc-nuclides.yaml)
        elementalsToKeep.update(elementalsInMC2)
        expansionStrings.update(mc2Expansions)

    # convert convenient string notation to actual NuclideBase objects
    expansions = {}
    for nnb, nbs in expansionStrings.items():
        expansions[nuclideBases.byName[nnb]] = [nuclideBases.byName[nb] for nb in nbs]

    return elementalsToKeep, expansions


def genDefaultNucFlags():
    """Perform all the yamlize-required type conversions."""
    flagsDict = getDefaultNuclideFlags()
    flags = NuclideFlags()
    for nucName, nucFlags in flagsDict.items():
        flag = NuclideFlag(nucName, nucFlags["burn"], nucFlags["xs"], nucFlags["expandTo"])
        flags[nucName] = flag
    return flags


def autoUpdateNuclideFlags(cs, nuclideFlags, inerts):
    """
    This function is responsible for examining the fission product model treatment
    that is selected by the user and adding a set of nuclides to the `nuclideFlags`
    list.

    Notes
    -----
    The reason for adding this method is that when switching between fission product
    modeling treatments it can be time-consuming to manually adjust the ``nuclideFlags``
    inputs.

    See Also
    --------
    genDefaultNucFlags
    """
    nbs = getAllNuclideBasesByLibrary(cs)
    if nbs:
        runLog.info(
            "Adding explicit fission products to the nuclide flags based on the "
            f"fission product model set to `{cs[CONF_FP_MODEL]}`."
        )
        for nb in nbs:
            nuc = nb.name
            if nuc in nuclideFlags or elements.byZ[nb.z] in nuclideFlags:
                continue
            nuclideFlags[nuc] = NuclideFlag(nuc, burn=False, xs=True, expandTo=[])
            # inert since burn is False
            inerts.add(nuc)


def getAllNuclideBasesByLibrary(cs):
    """
    Return a list of nuclide bases available for cross section modeling
    based on the ``CONF_FISSION_PRODUCT_LIBRARY_NAME`` setting.
    """
    nbs = []
    if cs[CONF_FP_MODEL] == "explicitFissionProducts":
        if not cs[CONF_FISSION_PRODUCT_LIBRARY_NAME]:
            nbs = []
        if cs[CONF_FISSION_PRODUCT_LIBRARY_NAME] == "MC2-3":
            nbs = nuclideBases.byMcc3Id.values()
        else:
            raise ValueError(
                "An option to handle the `CONF_FISSION_PRODUCT_LIBRARY_NAME` "
                f"set to `{cs[CONF_FISSION_PRODUCT_LIBRARY_NAME]}` has not been "
                "implemented."
            )
    return nbs
