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
This module defines the ARMI input for a component definition, and code for constructing an ARMI ``Component``.
"""
import yamlize
from armi.utils import units

from armi import materials
from armi import runLog
from armi.localization import exceptions
from armi.nucDirectory import elements
from armi.nucDirectory import nucDir
from armi.nucDirectory import nuclideBases
from armi.utils import densityTools


ALLOWED_KEYS = set(nuclideBases.byName.keys()) | set(elements.bySymbol.keys())


class NuclideFlag(yamlize.Object):
    """
    This class defines a nuclide options for use within the ARMI simulation, defining whether or not it should be
    included in the burn chain and cross sections.
    """

    nuclideName = yamlize.Attribute(type=str)

    @nuclideName.validator
    def nuclideName(self, value):
        if value not in ALLOWED_KEYS:
            raise ValueError(
                "`{}` is not a valid nuclide name, must be one of: {}".format(
                    value, ALLOWED_KEYS
                )
            )

    burn = yamlize.Attribute(type=bool)
    xs = yamlize.Attribute(type=bool)

    def __init__(self, nuclideName, burn, xs):
        # note: yamlize does not call an __init__ method, instead it uses __new__ and setattr
        self.nuclideName = nuclideName
        self.burn = burn
        self.xs = xs

    def __repr__(self):
        return "<NuclideFlag name:{} burn:{} xs:{}>".format(
            self.nuclideName, self.burn, self.xs
        )

    def prepForCase(self, activeSet, inertSet, undefinedBurnChainActiveNuclides):
        """Take in the string nuclide or element name, try to expand it out to its bases correctly."""
        actualNuclides = nucDir.getNuclidesFromInputName(self.nuclideName)
        for actualNuclide in actualNuclides:
            if self.burn:
                if not actualNuclide.trans and not actualNuclide.decays:
                    undefinedBurnChainActiveNuclides.add(actualNuclide.name)
                activeSet.add(actualNuclide.name)

            if self.xs:
                inertSet.add(actualNuclide.name)


class NuclideFlags(yamlize.KeyedList):
    """
    An OrderedDict of ``NuclideFlags``, keyed by their ``nuclideName``.
    """

    item_type = NuclideFlag
    key_attr = NuclideFlag.nuclideName


class CustomIsotopic(yamlize.Map):
    """
    User specified, custom isotopics input defined by a name (such as MOX), and key/pairs of nuclide names and numeric
    values consistent with the ``input format``.
    """

    key_type = yamlize.Typed(str)
    value_type = yamlize.Typed(float)
    name = yamlize.Attribute(type=str)
    inputFormat = yamlize.Attribute(key="input format", type=str)

    @inputFormat.validator
    def inputFormat(self, value):
        if value not in self._allowedFormats:
            raise ValueError(
                "Cannot set `inputFormat` to `{}`, must be one of: {}".format(
                    value, self._allowedFormats
                )
            )

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
            raise ValueError(
                "Key `{}` is not valid, must be one of: {}".format(key, ALLOWED_KEYS)
            )

        yamlize.Map.__setitem__(self, key, value)

    @property
    def density(self):
        return self._computedDensity or self._density

    @density.setter
    def density(self, value):
        if self._computedDensity is not None:
            raise AttributeError(
                "Density was computed from number densities, and should not be "
                "set directly."
            )
        self._density = value
        if value is not None and value < 0:
            raise ValueError(
                "Cannot set `density` to `{}`, must greater than 0".format(value)
            )

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
            # use a YamlizingError to line/column of erroneous input
            raise yamlize.YamlizingError(str(ex), node)

        return self

    @classmethod
    def from_yaml_key_val(cls, loader, key_node, val_node, key_attr, rtd):
        """
        Override the ``Yamlizable.from_yaml`` to inject custom data validation logic, and complete initialization of the
        object.
        """
        self = yamlize.Map.from_yaml_key_val.__func__(
            cls, loader, key_node, val_node, key_attr, rtd
        )

        try:
            self._initializeMassFracs()
            self._expandElementMassFracs()
        except Exception as ex:
            # use a YamlizingError to line/column of erroneous input
            raise yamlize.YamlizingError(str(ex), val_node)

        return self

    def _initializeMassFracs(self):
        self.massFracs = dict()  # defaults to 0.0, __init__ is not called

        if any(v < 0.0 for v in self.values()):
            raise ValueError(
                "Custom isotopic input for {} is negative".format(self.name)
            )

        valSum = sum(self.values())
        if not abs(valSum - 1.0) < 1e-5 and "fractions" in self.inputFormat:
            raise ValueError(
                "Fractional custom isotopic input values must sum to 1.0 in: {}".format(
                    self.name
                )
            )

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
                raise exceptions.InputError(
                    "Custom isotopic `{}` is over-specified. It was provided as number "
                    "densities, and but density ({}) was also provided. Is the input format "
                    "correct?".format(self.name, self.density)
                )

            M = {
                nuc: Ni
                / units.MOLES_PER_CC_TO_ATOMS_PER_BARN_CM
                * nucDir.getAtomicWeight(nuc)
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
            raise ValueError(
                "Unrecognized custom isotopics input format {}.".format(
                    self.inputFormat
                )
            )

    def _expandElementMassFracs(self):
        """
        Expand the massFrac dictionary element inputs to isotopics inputs (keys are strings) when the element name is
        not a elemental nuclide. Most everywhere else expects Nuclide objects (or nuclide names). This input allows a
        user to enter "U" which would expand to the naturally occurring uranium isotopics.

        This is different than the isotopic expansion done for meeting user-specified modeling options (such as an
        MC**2, or MCNP expecting elements or isotopes), because it translates the user input into something that can be
        used later on.
        """
        elementsToExpand = []
        for nucName in self.massFracs:
            if nucName not in nuclideBases.byName:
                element = elements.bySymbol.get(nucName)
                if element is not None:
                    runLog.info(
                        "Expanding custom isotopic `{}` element `{}` to natural isotopics".format(
                            self.name, nucName
                        )
                    )
                    elementsToExpand.append(element)
                else:
                    raise exceptions.InputError(
                        "Unrecognized nuclide/isotope/element in input: {}".format(
                            nucName
                        )
                    )

        densityTools.expandElementalMassFracsToNuclides(
            self.massFracs, elementsToExpand
        )

    def apply(self, material):
        """
        Apply specific isotopic compositions to a component.

        Generically, materials have composition-dependent bulk properties such as mass density.
        Note that this operation does not update these material properties. Use with care.

        Parameters
        ----------
        material : Material
            An ARMI Material instance.
        """
        material.p.massFrac = dict(self.massFracs)
        if self.density is not None:
            if not isinstance(material, materials.Custom):
                runLog.warning(
                    "You specified a custom mass density on `{}` with custom isotopics `{}`. "
                    "This has no effect; you can only set this on `Custom` "
                    "materials. Continuing to use {} mass density.".format(
                        material, self.name, material
                    )
                )
                return  # specifically, non-Custom materials only use refDensity and dLL, .p.density has no effect
            material.p.density = self.density


class CustomIsotopics(yamlize.KeyedList):
    """
    OrderedDict of CustomIsotopic objects, keyed by their name.
    """

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
        material : Material
            Material instance to adjust.

        customIsotopicName : str
            String corresponding to the ``CustomIsoptopic.name``.
        """
        if customIsotopicsName not in self:
            raise KeyError(
                "The input custom isotopics do not include {}. "
                "The only present specifications are {}".format(
                    customIsotopicsName, self.keys()
                )
            )

        custom = self[customIsotopicsName]
        custom.apply(material)
