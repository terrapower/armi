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
Contains classes that build case suites from perturbing inputs.

The general use case is to create a :py:class:`~SuiteBuilder` with a base
:py:class:`~armi.cases.case.Case`, use :py:meth:`~SuiteBuilder.addDegreeOfFreedom` to
adjust inputs according to the supplied arguments, and finally use ``.buildSuite`` to
generate inputs. The case suite can then be discovered, submitted, and analyzed using
the standard ``CaseSuite`` objects.

This module contains a variety of ``InputModifier`` objects as well, which are examples
of how you can modify inputs for parameter sweeping. Power-users will generally make
their own ``Modifier``s that are design-specific.

"""
import copy
import os
import random

from armi.reactor import flags
from armi.reactor.components import component
from armi.cases import suite


def getInputModifiers(cls):
    return cls.__subclasses__() + [
        g for s in cls.__subclasses__() for g in getInputModifiers(s)
    ]


class SuiteBuilder(object):
    """
    Class for constructing a CaseSuite from combinations of modifications on base inputs.

    Attributes
    ----------
    baseCase : armi.cases.case.Case
        A Case object to perturb

    modifierSets : list(tuple(InputModifier))
        Contains a list of tuples of ``InputModifier`` instances. A single case is
        constructed by running a series (the tuple) of InputModifiers on the case.

        NOTE: This is public such that someone could pop an item out of the list if it
        is known to not work, or be unnecessary.
    """

    def __init__(self, baseCase):
        self.baseCase = baseCase
        self.modifierSets = []

        # use an instance variable instead of global lookup. this could allow someone to add their own
        # modifiers, and also prevents it memory usage / discovery from simply loading the module.
        self._modifierLookup = {k.__name__: k for k in getInputModifiers(InputModifier)}

    def __len__(self):
        return len(self.modifierSets)

    def __repr__(self):
        return "<SuiteBuilder len:{} baseCase:{}>".format(len(self), self.baseCase)

    def addDegreeOfFreedom(self, inputModifiers):
        """
        Add a degree of freedom to the SweepBuilder.

        The exact application of this is dependent on a subclass.

        Parameters
        ----------
        inputModifiers : list(callable(CaseSettings, Blueprints, SystemLayoutInput))
            A list of callable objects with the signature
            ``(CaseSettings, Blueprints, SystemLayoutInput)``. When these objects are called
            they should perturb the settings, blueprints, and/or geometry by some amount determined
            by their construction.
        """
        raise NotImplementedError

    def buildSuite(self, namingFunc=None):
        """
        Builds a ``CaseSuite`` based on the modifierSets contained in the SuiteBuilder.

        For each sequence of modifications, this creates a new ``Case`` from the ``baseCase``, and
        runs the sequence of modifications on the new ``Case``'s inputs. The modified ``Case`` is
        then added to a ``CaseSuite``. The resulting ``CaseSuite`` is returned.

        Parameters
        ----------
        namingFunc : callable(index, case, tuple(InputModifier)), (optional)
            Function used to name each case. It is supplied with the index (int), the case (Case),
            and a tuple of InputModifiers used to edit the case. This should be enough information
            for someone to derive a meaningful name.

            The function should return a string specifying the path of the ``CaseSettings``, this
            allows the user to specify the directories where each case will be run.

            If not supplied the path will be ``./case-suite/<0000>/<title>-<0000>``, where
            ``<0000>`` is the four-digit case index, and ``<title>`` is the ``baseCase.title``.


        Raises
        ------
        RuntimeError
            When order of modifications is deemed to be invalid.

        Returns
        -------
        caseSuite : CaseSuite
            Derived from the ``baseCase`` and modifications.
        """
        caseSuite = suite.CaseSuite(self.baseCase.cs)

        if namingFunc is None:

            def namingFunc(index, _case, _mods):  # pylint: disable=function-redefined
                uniquePart = "{:0>4}".format(index)
                return os.path.join(
                    ".",
                    "case-suite",
                    uniquePart,
                    self.baseCase.title + "-" + uniquePart,
                )

        for index, modList in enumerate(self.modifierSets):
            case = copy.deepcopy(self.baseCase)
            previousMods = []

            for mod in modList:
                # it may seem late to figure this out, but since we are doing it now, someone could
                # filter these conditions out before the buildSuite. optionally, we could have a
                # flag for "skipInvalidModficationCombos=False"
                shouldHaveBeenBefore = [
                    fail
                    for fail in getattr(mod, "FAIL_IF_AFTER", ())
                    if fail in previousMods
                ]

                if any(shouldHaveBeenBefore):
                    raise RuntimeError(
                        "{} must occur before {}".format(
                            mod, ",".join(repr(m) for m in shouldHaveBeenBefore)
                        )
                    )

                previousMods.append(type(mod))
                mod(case.cs, case.bp, case.geom)
                case.independentVariables.update(mod.independentVariable)

            case.cs.path = namingFunc(index, case, modList)

            caseSuite.add(case)

        return caseSuite


class FullFactorialSuiteBuilder(SuiteBuilder):
    """Builds a suite that has every combination of each modifier."""

    def __init__(self, baseCase):
        SuiteBuilder.__init__(self, baseCase)
        # initialize with empty tuple to trick cross-product to always work
        self.modifierSets.append(())

    def addDegreeOfFreedom(self, inputModifiers):
        """
        Add a degree of freedom to the SuiteBuilder.

        Creates the Cartesian product of the ``inputModifiers`` supplied and those already applied.

        For example::

            class SettingModifier(InputModifier):

                def __init__(self, settingName, value):
                    self.settingName = settingName
                    self.value = value

                def __call__(self, cs, bp, geom):
                    cs[settignName] = value

            builder = FullFactorialSuiteBuilder(someCase)
            builder.addDegreeOfFreedom(SettingsModifier('settingName1', value) for value in (1,2))
            builder.addDegreeOfFreedom(SettingsModifier('settingName2', value) for value in (3,4,5))

        would result in 6 cases:

        | Index | ``settingName1`` | ``settingName2`` |
        | ----- | ---------------- | ---------------- |
        | 0     | 1                | 3                |
        | 1     | 2                | 3                |
        | 2     | 1                | 4                |
        | 3     | 2                | 4                |
        | 4     | 1                | 5                |
        | 5     | 2                | 5                |

        See Also
        --------
        SuiteBuilder.addDegreeOfFreedom
        """
        # Cartesian product. Append a new modifier to the end of a chain of previously defined.
        new = [
            existingModSet + (newModifier,)
            for newModifier in inputModifiers
            for existingModSet in self.modifierSets
        ]
        del self.modifierSets[:]
        self.modifierSets.extend(new)


class FullFactorialSuiteBuilderNoisy(FullFactorialSuiteBuilder):
    """
    Adds a bit of noise to each independent variable to avoid duplicates.

    This can be useful in some statistical postprocessors.

    .. warning:: Use with caution. This is part of ongoing research.
    """

    def __init__(self, baseCase, noiseFraction):
        FullFactorialSuiteBuilder.__init__(self, baseCase)
        self.noiseFraction = noiseFraction

    def addDegreeOfFreedom(self, inputModifiers):

        new = []
        for newMod in inputModifiers:
            for existingModSet in self.modifierSets:
                existingModSetCopy = copy.deepcopy(existingModSet)
                for mod in existingModSetCopy:
                    self._perturb(mod)
                newModCopy = copy.deepcopy(newMod)
                self._perturb(newModCopy)
                new.append(existingModSetCopy + (newModCopy,))

        del self.modifierSets[:]
        self.modifierSets.extend(new)

    def _perturb(self, mod):
        indeps = {}
        for key, val in mod.independentVariable.items():
            # perturb values by 10% randomly
            newVal = val + val * self.noiseFraction * (2 * random.random() - 1)
            indeps[key] = newVal
        mod.independentVariable = indeps


class SeparateEffectsSuiteBuilder(SuiteBuilder):
    """Varies each degree of freedom in isolation."""

    def addDegreeOfFreedom(self, inputModifiers):
        """
        Add a degree of freedom to the SuiteBuilder.

        Adds a case for each modifier supplied.

        For example::

            class SettingModifier(InputModifier):

                def __init__(self, settingName, value):
                    self.settingName = settingName
                    self.value = value

                def __call__(self, cs, bp, geom):
                    cs[settignName] = value

            builder = SeparateEffectsSuiteBuilder(someCase)
            builder.addDegreeOfFreedom(SettingsModifier('settingName1', value) for value in (1,2))
            builder.addDegreeOfFreedom(SettingsModifier('settingName2', value) for value in (3,4,5))

        would result in 5 cases:

        | Index | ``settingName1`` | ``settingName2`` |
        | ----- | ---------------- | ---------------- |
        | 0     | 1                | default          |
        | 1     | 2                | default          |
        | 2     | default          | 3                |
        | 3     | default          | 4                |
        | 4     | default          | 5                |

        See Also
        --------
        SuiteBuilder.addDegreeOfFreedom
        """
        self.modifierSets.extend((modifier,) for modifier in inputModifiers)


class InputModifier(object):
    """
    Object that modifies input definitions in some well-defined way.

    (This class is abstract.)

    Subclasses must implement a ``__call__`` method accepting a ``CaseSettings``,
    ``Blueprints``, and ``SystemLayoutInput``.

    The class attribute ``FAIL_IF_AFTER`` should be a tuple defining what, if any,
    modifications this should fail if performed after. For example, one should not
    adjust the smear density (a function of Cladding ID) before adjusting the Cladding
    ID.

    Some subclasses are provided, but you are expected to make your own design-specific
    modifiers in most cases.
    """

    FAIL_IF_AFTER = ()

    def __init__(self, independentVariable=None):
        """
        Constuctor.

        Parameters
        ----------
        independentVariable : dict or None, optional
            Name/value pairs to associate with the independent variable being modified
            by this object.  Will be analyzed and plotted against other modifiers with
            the same name.
        """
        if independentVariable is None:
            independentVariable = {}
        self.independentVariable = independentVariable

    def __call__(self, cs, blueprints, geom):
        """Perform the desired modifications to input objects."""
        raise NotImplementedError


class NeutronicMeshsSizeModifier(InputModifier):
    """
    Adjust the neutronics mesh in all assemblies by a multiplication factor.

    This can be useful when switching between nodal and finite difference
    approximations, or when doing mesh convergence sensitivity studies.

    Attributes
    ----------
    multFactor : int
        Factor to multiply the number of axial mesh points per block by.
    """

    def __init__(self, multFactor):
        InputModifier.__init__(self, {self.__class__.__name__: multFactor})
        if not isinstance(multFactor, int):
            raise TypeError(
                "multFactor must be an integer, but got {}".format(multFactor)
            )
        self.multFactor = multFactor

    def __call__(self, cs, blueprints, geom):
        for assemDesign in blueprints.assemDesigns:
            assemDesign.axialMeshPoints = [
                ax * self.multFactor for ax in assemDesign.axialMeshPoints
            ]


class FullCoreModifier(InputModifier):
    """
    Grow the SystemLayoutInput to from a symmetric core to a full core.
    """

    def __call__(self, cs, blueprints, geom):
        geom.growToFullCore()


class _PinTypeAssemblyModifier(InputModifier):
    """
    Abstract class for modifying something about a pin, within a block.

    This will construct blocks, determine if the block should be modified by checking
    the ``_getBlockTypesToModify``, and then run ``_adjustBlock(b)``. The ``Blueprints``
    are then updated based on the modification assuming that dimension names match
    exactly to ComponenBlueprint attributes (which is true, because ComponentBlueprint
    attributes are programmatically derived from Component constructors).
    """

    def __init__(self, value):
        InputModifier.__init__(self, {self.__class__.__name__: value})
        self.value = value

    def __call__(self, cs, blueprints, geom):
        for bDesign in blueprints.blockDesigns:
            # bDesign construct requires lots of arguments, many of which have no impact.
            # The following can safely be defaulted to meaningless inputs:
            # axialIndex: a block can be reused at any axial index, modifications made
            #     dependent on will not translate back to the input in a  meaningful
            #     fashion
            # axialMeshPoints: similar to above, this is specified by the assembly, and
            #     a block can be within any section of an assembly.
            # height: similar to above. a block can have any height specified by an
            #     assembly. if height-specific modifications are required, then a new
            #     block definition should be created in the input
            # xsType: similar to above. a block can have any xsType specified through
            #     the assembly definition assembly. if xsType-specific modifications are
            #     required, then a new block definition should be created in the input
            # materialInput: this is the materialModifications from the assembly
            #     definition. if material modifications are required on a block-specific
            #     basis, they should be edited directly
            b = bDesign.construct(
                cs,
                blueprints,
                axialIndex=1,
                axialMeshPoints=1,
                height=1,
                xsType="A",
                materialInput={},
            )

            if not b.hasFlags(self._getBlockTypesToModify()):
                continue

            self._adjustBlock(b)

            for cDesign, c in zip(bDesign, b):
                for dimName in c.DIMENSION_NAMES:
                    inpDim = getattr(cDesign, dimName)
                    newDim = getattr(c.p, dimName)
                    if isinstance(newDim, tuple):
                        # map linked component dimension
                        link = component._DimensionLink(newDim)
                        newDim = str(link)
                    if inpDim != newDim:
                        setattr(cDesign, dimName, newDim)

    def _getBlockTypesToModify(self):
        """Hook method to determine blocks that should be modified."""
        raise NotImplementedError

    def _adjustBlock(self, b):
        """Hook method for `__call__` template method."""
        raise NotImplementedError


class SmearDensityModifier(_PinTypeAssemblyModifier):
    """
    Adjust the smeared density to the specified value.

    This is effectively how much of the space inside the cladding tube is occupied by
    fuel at fabrication.

    See Also
    --------
    armi.reactor.blocks.Block.adjustSmearDensity
        Actually adjusts the smeared density
    """

    def _getBlockTypesToModify(self):
        """Hook method to determine blocks that should be modified."""
        return flags.Flags.FUEL

    def _adjustBlock(self, b):
        """Hook method for `__call__` template method."""
        b.adjustSmearDensity(self.value)


class CladThicknessByODModifier(_PinTypeAssemblyModifier):
    """
    Adjust the cladding thickness by adjusting the inner diameter of all cladding components.
    """

    FAIL_IF_AFTER = (SmearDensityModifier,)

    def _getBlockTypesToModify(self):
        """Hook method to determine blocks that should be modified."""
        return ""

    def _adjustBlock(self, b):
        b.adjustCladThicknessByOD(self.value)


class CladThicknessByIDModifier(_PinTypeAssemblyModifier):
    """
    Adjust the cladding thickness by adjusting the outer diameter of the cladding component.
    """

    FAIL_IF_AFTER = (SmearDensityModifier,)

    def _getBlockTypesToModify(self):
        """Hook method to determine blocks that should be modified."""
        return ""

    def _adjustBlock(self, b):
        b.adjustCladThicknessByID(self.value)


class NeutronicConvergenceModifier(InputModifier):
    """
    Adjust the neutronics convergence parameters ``epsEig``, ``epsFSAvg``, and ``epsFSPoint``.

    The supplied value is used for ``epsEig``. ``epsFSAvg`` and ``epsFSPoint`` are set
    to 100 times the supplied value.

    This can be used to perform sensitivity studies on convergence criteria.
    """

    def __init__(self, value):
        InputModifier.__init__(self, {self.__class__.__name__: value})
        self.value = value
        if value > 1e-2 or value <= 0.0:
            raise ValueError(
                "Neutronic convergence modifier value must be greater than 0 and less "
                "than 1e-2 (got {})".format(value)
            )

    def __call__(self, cs, blueprints, geom):
        cs["epsFSAvg"] = self.value * 100
        cs["epsFSPoint"] = self.value * 100
        cs["epsEig"] = self.value


class SettingsModifier(InputModifier):
    """
    Adjust settings to specified values.
    """

    bad_setting_names = {
        "epsEig": NeutronicConvergenceModifier,
        "epsFSAvg": NeutronicConvergenceModifier,
        "epsFSPoint": NeutronicConvergenceModifier,
    }

    def __init__(self, settingName, value):
        InputModifier.__init__(self, independentVariable={settingName: value})
        self.settingName = settingName
        self.value = value
        if settingName in self.bad_setting_names:
            raise ValueError(
                "An alternate modifier exists for adjusting the setting `{}`, use {}".format(
                    settingName, self.bad_setting_names[settingName]
                )
            )

    def __call__(self, cs, blueprints, geom):
        cs[self.settingName] = self.value
