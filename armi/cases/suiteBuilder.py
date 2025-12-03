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
Contains classes that build case suites from perturbing inputs.

The general use case is to create a :py:class:`~SuiteBuilder` with a base
:py:class:`~armi.cases.case.Case`, use :py:meth:`~SuiteBuilder.addDegreeOfFreedom` to
adjust inputs according to the supplied arguments, and finally use ``.buildSuite`` to
generate inputs. The case suite can then be discovered, submitted, and analyzed using
the standard ``CaseSuite`` objects.

This module contains a variety of ``InputModifier`` objects as well, which are examples
of how you can modify inputs for parameter sweeping. Power-users will generally make
their own ``Modifier``\ s that are design-specific.
"""

import copy
import os
import random
from collections import Counter
from typing import List

from pyDOE import lhs

from armi.cases import suite


def getInputModifiers(cls):
    return cls.__subclasses__() + [g for s in cls.__subclasses__() for g in getInputModifiers(s)]


class SuiteBuilder:
    """
    Class for constructing a CaseSuite from combinations of modifications on base inputs.

    .. impl:: A generic tool to modify user inputs on multiple cases.
        :id: I_ARMI_CASE_MOD0
        :implements: R_ARMI_CASE_MOD

        This class provides the capability to create a :py:class:`~armi.cases.suite.CaseSuite` based
        on programmatic perturbations/modifications to case settings. It works by being constructed
        with a base or nominal :py:class:`~armi.cases.case.Case` object. Children classes then
        append the ``self.modifierSets`` member. Each entry in ``self.modifierSets`` is a
        :py:class:`~armi.cases.inputModifiers.inputModifiers.InputModifier` representing a case to
        add to the suite by specifying modifications to the settings of the base case.
        :py:meth:`SuiteBuilder.buildSuite` is then invoked, returning an instance of the
        :py:class:`~armi.cases.suite.CaseSuite` containing all the cases with modified settings.

    Attributes
    ----------
    baseCase : armi.cases.case.Case
        A Case object to perturb

    modifierSets : list(tuple(InputModifier))
        Contains a list of tuples of ``InputModifier`` instances. A single case is constructed by
        running a series (the tuple) of InputModifiers on the case.

    Notes
    -----
    This is public such that someone could pop an item out of the list if it is known to not work,
    or be unnecessary.
    """

    def __init__(self, baseCase):
        self.baseCase = baseCase
        self.modifierSets = []

        from armi.cases.inputModifiers import inputModifiers

        # use an instance variable instead of global lookup. this could allow someone to add their own
        # modifiers, and also prevents it memory usage / discovery from simply loading the module.
        self._modifierLookup = {k.__name__: k for k in getInputModifiers(inputModifiers.InputModifier)}

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
        inputModifiers : list(callable(Settings, Blueprints, SystemLayoutInput))
            A list of callable objects with the signature
            ``(Settings, Blueprints, SystemLayoutInput)``. When these objects are called they should
            perturb the settings or blueprints by some amount determined by their construction.
        """
        raise NotImplementedError

    def addModifierSet(self, inputModifierSet: List):
        """
        Add a single input modifier set to the suite.

        Used to add modifications that are not necessarily another degree of freedom.
        """
        self.modifierSets.append(inputModifierSet)

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

            The function should return a string specifying the path of the ``Settings``, this
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

            def namingFunc(index, _case, _mods):
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
            case.bp._prepConstruction(case.cs)
            for mod in modList:
                # it may seem late to figure this out, but since we are doing it now, someone could
                # filter these conditions out before the buildSuite. optionally, we could have a
                # flag for "skipInvalidModficationCombos=False"
                shouldHaveBeenBefore = [fail for fail in getattr(mod, "FAIL_IF_AFTER", ()) if fail in previousMods]

                if any(shouldHaveBeenBefore):
                    raise RuntimeError(
                        "{} must occur before {}".format(mod, ",".join(repr(m) for m in shouldHaveBeenBefore))
                    )

                previousMods.append(type(mod))
                case.cs, case.bp = mod(case.cs, case.bp)
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

                def __call__(self, cs, bp):
                    cs = cs.modified(newSettings={self.settingName: self.value})
                    return cs, bp


            builder = FullFactorialSuiteBuilder(someCase)
            builder.addDegreeOfFreedom(SettingModifier("settingName1", value) for value in (1, 2))
            builder.addDegreeOfFreedom(SettingModifier("settingName2", value) for value in (3, 4, 5))

        would result in 6 cases:

        +-------+------------------+------------------+
        | Index | ``settingName1`` | ``settingName2`` |
        +=======+==================+==================+
        | 0     | 1                | 3                |
        +-------+------------------+------------------+
        | 1     | 2                | 3                |
        +-------+------------------+------------------+
        | 2     | 1                | 4                |
        +-------+------------------+------------------+
        | 3     | 2                | 4                |
        +-------+------------------+------------------+
        | 4     | 1                | 5                |
        +-------+------------------+------------------+
        | 5     | 2                | 5                |
        +-------+------------------+------------------+

        See Also
        --------
        SuiteBuilder.addDegreeOfFreedom
        """
        # Cartesian product. Append a new modifier to the end of a chain of previously defined.
        new = [
            existingModSet + (newModifier,) for newModifier in inputModifiers for existingModSet in self.modifierSets
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

                def __call__(self, cs, bp):
                    cs = cs.modified(newSettings={self.settignName: self.value})
                    return cs, bp


            builder = SeparateEffectsSuiteBuilder(someCase)
            builder.addDegreeOfFreedom(SettingModifier("settingName1", value) for value in (1, 2))
            builder.addDegreeOfFreedom(SettingModifier("settingName2", value) for value in (3, 4, 5))

        would result in 5 cases:

        +-------+------------------+------------------+
        | Index | ``settingName1`` | ``settingName2`` |
        +=======+==================+==================+
        | 0     | 1                | default          |
        +-------+------------------+------------------+
        | 1     | 2                | default          |
        +-------+------------------+------------------+
        | 2     | default          | 3                |
        +-------+------------------+------------------+
        | 3     | default          | 4                |
        +-------+------------------+------------------+
        | 4     | default          | 5                |
        +-------+------------------+------------------+

        See Also
        --------
        SuiteBuilder.addDegreeOfFreedom
        """
        self.modifierSets.extend((modifier,) for modifier in inputModifiers)


class LatinHyperCubeSuiteBuilder(SuiteBuilder):
    """Implements a Latin Hypercube Sampling suite builder.

    This method is used to provide a more efficient sampling of the design space.
    LHS more efficiently samples the space evenly across dimensions compared to
    random sampling. It requires fewer points than a full factorial since it samples
    quasi-randomly into nonoverlapping partitions. It is recommended to use a surrogate
    model with the sampled data to get the full benefit.

    Attributes
    ----------
    modifierSets: An array of InputModifiers specifying input parameters.
    """

    def __init__(self, baseCase, size):
        SuiteBuilder.__init__(self, baseCase)
        self.size = size
        self.modifierSets = []

    def addDegreeOfFreedom(self, inputModifiers):
        """
        Add a degree of freedom to the SuiteBuilder.

        Unlike other types of suite builders, only one instance of a modifier class should be added.
        This is because the Latin Hypercube Sampling will automatically perturb the values and
        produce modifier sets internally. A settings modifier class passed to this method need
        include bounds by which the LHS algorithm can perturb the input parameters.

        For example::

            class InputParameterModifier(SamplingInputModifier):
                def __init__(
                    self,
                    name: str,
                    pararmType: str,  # either 'continuous' or 'discrete'
                    bounds: Optional[Tuple, List],
                ):
                    super().__init__(name, paramType, bounds)

                def __call__(self, cs, bp): ...

        If the modifier is discrete then bounds specifies a list of options the values can take. If
        continuous, then bounds specifies a range of values.
        """
        names = [mod.name for mod in self.modifierSets + inputModifiers]

        if len(names) != len(set(names)):
            counts = Counter(names)
            duplicateNames = []
            for key in counts.keys():
                if counts[key] > 1:
                    duplicateNames.append(key)

            raise ValueError(
                "Only a single input parameter should be inserted as an input modifier since cases "
                + "are added through Latin Hypercube Sampling.\nEach inputModifier adds a "
                + "a dimension to the Latin Hypercube and represents a single input variable.\n"
                + f"{duplicateNames} have duplicates. "
            )

        self.modifierSets.extend(inputModifiers)

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

            The function should return a string specifying the path of the ``Settings``, this
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
        original_modifiers = copy.deepcopy(self.modifierSets)
        del self.modifierSets[:]

        samples = lhs(
            len(original_modifiers),
            samples=self.size,
            criterion="maximin",
            iterations=100,
        )

        # Normalizing samples to modifier bounds and creating modifier objects.
        for i in range(len(samples)):
            modSet = []
            for j, mod in enumerate(original_modifiers):
                new_mod = copy.deepcopy(mod)
                if mod.paramType == "continuous":
                    value = (mod.bounds[1] - mod.bounds[0]) * samples[i][j] + mod.bounds[0]
                    new_mod.value = value
                elif mod.paramType == "discrete":
                    index = round(samples[i][j] * (len(mod.bounds) - 1))
                    value = mod.bounds[index]
                    new_mod.value = value

                modSet.append(new_mod)
            self.modifierSets.append(modSet)

        return super().buildSuite(namingFunc=namingFunc)
