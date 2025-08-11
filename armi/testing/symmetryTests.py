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

EXPLAIN HOW TO USE THE UTILITIES HERE
"""

import inspect
from contextlib import contextmanager
from copy import deepcopy
from typing import TYPE_CHECKING, Any, Iterable, Union

import numpy as np

from armi.reactor import assemblyParameters, blockParameters, parameters, reactorParameters
from armi.reactor.components import componentParameters
from armi.testing import loadTestReactor

if TYPE_CHECKING:
    from unittest import TestCase

    from armi.reactor import Core
    from armi.reactor.assemblies import Assembly
    from armi.reactor.blocks import Block


class SymmetryFactorTester:
    """
    A test helper for symmetry factors.

    Structured as a class so it can be imported with a list of expected parameters. The individual tests then check
    which parameters are altered by symmetry-aware operations and if there are any parameters that change but are not in
    the "expected" list an error is raised.
    """

    def __init__(self):
        self.o, self.r = loadTestReactor()
        self.core = self.r.core
        # there is exactly one assembly with 3-symmetry in the test core
        self.partialAssembly = [a for a in self.r.core.getAssemblies() if a.getSymmetryFactor() == 3][0]
        self.partialBlock = self.partialAssembly.getBlocks()[0]
        # expectedSymmetry describes the ratio of (post-expansion / pre-expansion) values
        self.expectedSymmetry = 3
        # load default armi parameters for each object type
        self._loadDefaultParameters()

    @staticmethod
    def _getParameters(obj: object, paramList: Iterable[str]):
        # test if the deepcopy is necessary
        return deepcopy({param: obj.p[param] for param in paramList})

    @staticmethod
    def _getParamNamesFromDefinitions(module):
        tempParams = []
        for _name, func in inspect.getmembers(module, inspect.isfunction):
            if inspect.signature(func) == "()":
                if isinstance(returned := func(), parameters.ParameterDefinitionCollection):
                    tempParams.append(returned)
        return set([p.name for item in tempParams for p in item])

    def _loadDefaultParameters(self):
        # reactor parameters include the core parameters
        self.defaultReactorParameterNames = self._getParamNamesFromDefinitions(reactorParameters)
        self.defaultAssemblyParameterNames = self._getParamNamesFromDefinitions(assemblyParameters)
        self.defaultBlockParameterNames = self._getParamNamesFromDefinitions(blockParameters)
        self.defaultComponentParameterNames = self._getParamNamesFromDefinitions(componentParameters)

    def _initializeParameters(self, parameterNames, obj: Union["Core", "Assembly", "Block"]):
        for parameterName in parameterNames:
            paramType = type(obj.p[parameterName])
            if isinstance(paramType, np.ndarray):
                obj.p[parameterName] = np.array([2.0, 2.0, 2.0])
            else:
                obj.p[parameterName] = paramType(2.0)

    def _compareParameters(
        self,
        referenceParameters: dict[str:Any],
        perturbedParameters: dict[str:Any],
        expectedParameters: Iterable[str],
        scopeName: str,
    ):
        """Do a thing."""
        for paramName, perturbedValue in perturbedParameters.items():
            referenceValue = referenceParameters[paramName]
            if referenceValue != perturbedValue:
                self.testObject.assertIn(
                    paramName,
                    expectedParameters,
                    f"The value of {paramName} on the {scopeName} changed but is not specified in the parameters "
                    "expected to change.",
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
    def _checkCore(self, userParams: Iterable[str]):
        allReactorParameters = self.defaultReactorParameterNames.union(userParams)
        coreReferenceParameters = self._getParameters(self.core, allReactorParameters)

        yield  # yield to allow the core to be expanded

        corePerturbedParameters = self._getParameters(self.core, allReactorParameters)
        self._compareParameters(coreReferenceParameters, corePerturbedParameters, userParams, "core")

    @contextmanager
    def _checkAssembly(self, userParams: Iterable[str]):
        allAssemblyParameters = self.defaultAssemblyParameterNames.union(userParams)
        assemblyReferenceParameters = self._getParameters(self.partialAssembly, allAssemblyParameters)

        yield  # yield to allow the core to be expanded

        assemblyPerturbedParameters = self._getParameters(self.partialAssembly, allAssemblyParameters)
        self._compareParameters(assemblyReferenceParameters, assemblyPerturbedParameters, userParams, "assembly")

    @contextmanager
    def _checkBlock(self, userParams: Iterable[str]):
        allBlockParameters = self.defaultBlockParameterNames.union(userParams)
        blockReferenceParameters = self._getParameters(self.partialBlock, allBlockParameters)

        yield  # yield to allow the core to be expanded

        blockPerturbedParameters = self._getParameters(self.partialBlock, allBlockParameters)
        self._compareParameters(blockReferenceParameters, blockPerturbedParameters, userParams, "block")

    def runSymmetryFactorTests(
        self,
        testObject: "TestCase",
        coreParams: Iterable[str] = [],
        assemblyParams: Iterable[str] = [],
        blockParams: Iterable[str] = [],
    ):
        """
        Runs tests on how symmetry factors apply to parameters during partial-to-full core coversions and vice-versa.

        This helper provides a convenient way for plugins to test that symmetry factors are applied correctly to flagged
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
        self.testObject = testObject
        self._initializeParameters(coreParams, self.core)
        self._initializeParameters(assemblyParams, self.partialAssembly)
        for b in self.partialAssembly:
            self._initializeParameters(blockParams, b)

        # temporarily use b to get the outline, iterate over the blocks later or get all blocks
        b = self.partialAssembly.getBlocks()[0]

        with self._checkCore(coreParams), self._checkAssembly(assemblyParams), self._checkBlock(blockParams):
            self.r.core.growToFullCore(self.o.cs)
