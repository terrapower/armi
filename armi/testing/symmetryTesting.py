# Copyright 2025 TerraPower, LLC
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
Testing utilities for symmetry.

Symmetry factor usage can be difficult to verify across multiple plugins, and plugins may write one-off fixes for
situations involving the symmetry factor. The utilities provided here are an attempt to catch symmetry factor issues
at the unit test level, rather than during integration tests.

The goal of this utility is to test symmetry intent, not functionality. This means individual implementations of
symmetry-aware operations are still responsible for testing the implemetation. This module serves as a check that the
parameters that are expected to change with symmetry do indeed change.

This might be obvious, but this test CANNOT detect errors where the parameter is not either:
    1) Labeled as a symmetry-aware parameter in the parameter definition.
    2) Labeled as a symmetry-aware parameter in the test.
Failing to do at least one of the above will result in passing symmetry tests.

The tests here use the `growToFullCore` since that should be one of the most mature symmetry-aware operations.

This module provides the `BasicArmiSymmetryTestHelper` which is meant to be inherited into a downstream unit test.
The test helper uses the `SymmetryFactorTester` to handle the bookkeeping tasks associated with testing symmetry.
"""

import unittest
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Iterable, Union

from armi.reactor import assemblyParameters, blockParameters, parameters, reactorParameters
from armi.testing import loadTestReactor

if TYPE_CHECKING:
    from armi.reactor import Core
    from armi.reactor.assemblies import Assembly
    from armi.reactor.blocks import Block


class BasicArmiSymmetryTestHelper(unittest.TestCase):
    """
    Customizable test runner for symmetry-intent audit.

    This class is meant to be customized in a plugin to check the plugin-specific symmetry-aware parameters.

    To use the test fixture, make a subclass test and assign the `*ParamsToTest` and `expectedSymmetric*` attributes in
    the `setUp` method of the subclass. The subclass must have `super.setUp()` in it's `setUp` method at some point
    after the necessary plugin attributes are assigned.

    Attributes
    ----------
    coreParamsToTest : Iterable[str] | armi.reactor.parameters.parameterDefinitionCollection, optional
        Core parameters that should be initialized and tested.
    assemblyParamsToTest : Iterable[str] | armi.reactor.parameters.parameterDefinitionCollection, optional
        Assembly parameters that should be initialized and tested.
    blockParamsToTest : Iterable[str] | armi.reactor.parameters.parameterDefinitionCollection, optional
        Block parameters that should be initialized and tested.
    expectedSymmetricCoreParams : Iterable[str], optional
        Core parameters that are expected to change with symmetry.
    expectedSymmetricAssemblyParams : Iterable[str], optional
        Assembly parameters that are expected to change with symmetry.
    expectedSymmetricBlockParams : Iterable[str], optional
        Block Parameters that are expected to change with symmetry.
    parameterOverrides : dict[str: Any], optional
        Dictionary of specific values to assign to a particular parameter. Useful for parameters that have validators.
    paramsToIgnore : Iterable[str], optional
        Parameter names to ignore the comparison results for.


    Example
    -------
    ```python
    class MySymmetryTest(symmetryTesting.BasicArmiSymmetryTestHelper):
        def setUp():
            # Tests are configured using attributes. Attributes must be set prior to calling super.setUp()
            # Note that it is not required to set any attributes, all have empty defaults

            # Repeat for self.coreParamsToTest and self.assemblyParamsToTest as necessary:
            self.blockParamsToTest = [p if isinstance(p, str) else p.name for p in getPluginBlockParameterDefinitions()]

            # Repeat for self.expectedSymmetricCoreParams and self.expectedSymmetricAssemblyParams as necessary:
            self.expectedSymmetricBlockParams = ["mySymmetricBlockParam1", "mySymmetricBlockParam2"]

            # Set specific parameter overrides if the parameters need a specific value (usually due to input validators)
            self.parameterOverrides = {"parameterName1": value1, "parameterName2": value2}

            # Set specific parameters to ignore in comparison.
            self.paramsToIgnore = ["myIgnoredParameter"]

            # Finish setting up the tests by calling the parent's `setUp` method.
            super.setUp()
    ```

    It should generally not be necessary for the plugin to implement any further unit tests, the parent class contains
    a test method that should adequately verify the the expected symmetric parameters are indeed expanded.
    """

    coreParamsToTest = []
    assemblyParamsToTest = []
    blockParamsToTest = []
    expectedSymmetricCoreParams = []
    expectedSymmetricAssemblyParams = []
    expectedSymmetricBlockParams = []
    parameterOverrides = {}
    paramsToIgnore = []

    def setUp(self):
        self._preprocessPluginParams()
        self.symTester = SymmetryFactorTester(
            self,
            expectedSymmetricCoreParams=self.coreParamsToTest,
            expectedSymmetricAssemblyParams=self.assemblyParamsToTest,
            expectedSymmetricBlockParams=self.blockParamsToTest,
            parameterOverrides=self.parameterOverrides,
            paramsToIgnore=self.paramsToIgnore,
        )

    def _preprocessPluginParams(self):
        """Parameters can be provided as string names or whole parameter objects, need to convert to string name."""
        self.coreParamsToTest = [p if isinstance(p, str) else p.name for p in self.coreParamsToTest]
        self.assemblyParamsToTest = [p if isinstance(p, str) else p.name for p in self.assemblyParamsToTest]
        self.blockParamsToTest = [p if isinstance(p, str) else p.name for p in self.blockParamsToTest]
        self.expectedSymmetricCoreParams = [
            p if isinstance(p, str) else p.name for p in self.expectedSymmetricCoreParams
        ]
        self.expectedSymmetricAssemblyParams = [
            p if isinstance(p, str) else p.name for p in self.expectedSymmetricAssemblyParams
        ]
        self.expectedSymmetricBlockParams = [
            p if isinstance(p, str) else p.name for p in self.expectedSymmetricBlockParams
        ]

    def test_defaultSymmetry(self):
        self.symTester.runSymmetryFactorTests(expectedBlockParams=self.expectedSymmetricBlockParams)


class SymmetryFactorTester:
    """
    A test runner for symmetry factors.

    This class does the actual symmetry testing, but there is a lot of bookkeeping that isn't important to expose in the
    test helper class so putting it here helps keep the BasicArmiSymmetryTestHelper clean.
    """

    def __init__(
        self,
        testObject: unittest.TestCase,
        expectedSymmetricCoreParams: list[str] = [],
        expectedSymmetricAssemblyParams: list[str] = [],
        expectedSymmetricBlockParams: list[str] = [],
        parameterOverrides: dict[str:Any] = {},
        paramsToIgnore: list[str] = [],
    ):
        self.o, self.r = loadTestReactor()
        self.core = self.r.core
        # there is exactly one assembly with 3-symmetry in the test core
        self.partialAssembly = [a for a in self.r.core.getAssemblies() if a.getSymmetryFactor() == 3][0]
        self.partialBlock = self.partialAssembly.getBlocks()[0]
        # expectedSymmetry describes the ratio of (post-expansion / pre-expansion) values
        self.expectedSymmetry = 3
        self.defaultParameterValue = 2
        # load default armi parameters for each object type
        self._loadDefaultParameters()
        # some parameters have validation on their inputs and need specific settings
        self.parameterOverrides = parameterOverrides

        self.testObject = testObject
        self.expectedSymmetricCoreParams = expectedSymmetricCoreParams
        self.expectedSymmetricAssemblyParams = expectedSymmetricAssemblyParams
        self.expectedSymmetricBlockParams = expectedSymmetricBlockParams
        self._initializeCore()
        self._initializeAssembly()
        self._initializeBlock()

        # Some parameters change because of symmetry but are not "volume integrated"
        # so this marks them for skipping in the compare.
        # Also allows plugins the flexibility to skip some parameters if needed.
        self.paramsToIgnore = paramsToIgnore

    @staticmethod
    def _getParameters(obj: object, paramList: Iterable[str]):
        return {param: obj.p[param] for param in paramList}

    @staticmethod
    def _getParamNamesFromDefs(pdefs: parameters.ParameterDefinitionCollection):
        return set([p.name for p in pdefs])

    def _loadDefaultParameters(self):
        self.defaultCoreParameterDefs = set(reactorParameters.defineCoreParameters())
        self.defaultAssemblyParameterDefs = set(assemblyParameters.getAssemblyParameterDefinitions())
        self.defaultBlockParameterDefs = set(blockParameters.getBlockParameterDefinitions())

    def _initializeCore(self):
        self._initializeParameters(self.expectedSymmetricCoreParams, self.core)

    def _initializeAssembly(self):
        self.allAssemblyParameterKeys = set([p if isinstance(p, str) else p.name for p in self.partialAssembly.p])
        self._initializeParameters(self.allAssemblyParameterKeys, self.partialAssembly)

    def _initializeBlock(self):
        self._initializeParameters(self.expectedSymmetricBlockParams, self.partialBlock)

    def _initializeParameters(self, parameterNames, obj: Union["Core", "Assembly", "Block"]):
        """
        Load values into each parameter.

        The values generally do not need to be the correct types (see Notes) because this test fixture is for auditing
        intent, not capability. The capability of the expansion functions to expand different types correctly should be
        part of the tests for those functions.

        Parameters
        ----------
        parameterNames : Iterable[str]
            Iterable of string parameter names to initialize on the object.
        obj : armi.reactor.Core | armi.reactor.assemblies.Assembly | armi.reactor.blocks.Block
            The object on which to initialize parameter values.

        Notes
        -----
        Some parameters are specifically adjusted here because inspecting their types does not yield usable results
        for setting the values. Current specific settings are:
        xsType: must be an iterable of strings.
        xsTypeNum: must be an integer corresponding to an ASCII character in the range of what is acceptable for xsType.
        notes: must be a string with length less than 1000 characters.
        """
        for p in parameterNames:
            name = str(p)
            if name in self.parameterOverrides.keys():
                obj.p[name] = self.parameterOverrides[name]
            else:
                obj.p[name] = self.defaultParameterValue

    def _compareParameters(
        self,
        referenceParameters: dict[str:Any],
        perturbedParameters: dict[str:Any],
        expectedParameters: Iterable[str],
        scopeName: str,
    ):
        """
        Run the comparison of reference parameters vs the perturbed parameters.

        Tests:
            1. Parameters that change after core expansion are in the list of parameters expected to change.
            2. All parameters in the list of parameters expected to change do indeed change by the expected ratio.
        """
        for paramName, perturbedValue in perturbedParameters.items():
            referenceValue = referenceParameters[paramName]
            if referenceValue != perturbedValue and paramName not in self.paramsToIgnore:
                self.testObject.assertIn(
                    paramName,
                    expectedParameters,
                    f"The value of {paramName} on the {scopeName} changed from {referenceValue} to {perturbedValue} but"
                    " is not specified in the parameters expected to change.",
                )
            if paramName in expectedParameters:
                ratio = perturbedParameters[paramName] / referenceParameters[paramName]
                self.testObject.assertEqual(
                    ratio,
                    self.expectedSymmetry,
                    f"The after-to-before expansion ratio of parameter '{paramName}' was expected to be "
                    f"{self.expectedSymmetry} but was instead {ratio} for the {scopeName}.",
                )

    @contextmanager
    def _checkCore(self, expectedParams: Iterable[str]):
        coreReferenceParameters = self._getParameters(self.core, self.expectedSymmetricCoreParams)
        yield  # yield to allow the core to be expanded
        corePerturbedParameters = self._getParameters(self.core, self.expectedSymmetricCoreParams)
        self._compareParameters(coreReferenceParameters, corePerturbedParameters, expectedParams, "core")

    @contextmanager
    def _checkAssembly(self, expectedParams: Iterable[str]):
        assemblyReferenceParameters = self._getParameters(self.partialAssembly, self.expectedSymmetricAssemblyParams)
        yield  # yield to allow the core to be expanded
        assemblyPerturbedParameters = self._getParameters(self.partialAssembly, self.expectedSymmetricAssemblyParams)
        self._compareParameters(assemblyReferenceParameters, assemblyPerturbedParameters, expectedParams, "assembly")

    @contextmanager
    def _checkBlock(self, expectedParams: Iterable[str]):
        blockReferenceParameters = self._getParameters(self.partialBlock, self.expectedSymmetricBlockParams)
        yield  # yield to allow the core to be expanded
        blockPerturbedParameters = self._getParameters(self.partialBlock, self.expectedSymmetricBlockParams)
        self._compareParameters(blockReferenceParameters, blockPerturbedParameters, expectedParams, "block")

    def runSymmetryFactorTests(
        self,
        expectedCoreParams: Iterable[str] = [],
        expectedAssemblyParams: Iterable[str] = [],
        expectedBlockParams: Iterable[str] = [],
    ):
        """
        Runs tests on how symmetry factors apply to parameters during partial-to-full core coversions and vice-versa.

        This method provides a convenient way for plugins to test that symmetry factors are applied correctly to flagged
        parameters when the core is converted.

        Parameters
        ----------
        testObject : unittest.TestCase
            The TestCase object is injected to give this fixture the ability to do unittest asserts without causing
            the fixture itself to be run as a unit test.
        coreParams : Iterable[str], optional
            Dictionary of core parameters that the user expects to be symmetry aware.
        assemblyParams : Iterable[str], optional
            Dictionary of assembly parameters that the user expects to be symmetry aware.
        blockParams : Iterable[str], optional
            Dictionary of block parameters that the user expects to be symmetry aware.
        """
        with (
            self._checkCore(expectedCoreParams),
            self._checkAssembly(expectedAssemblyParams),
            self._checkBlock(expectedBlockParams),
        ):
            self.r.core.growToFullCore(self.o.cs)
