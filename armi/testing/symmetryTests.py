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
from armi.reactor.parameters import Parameter
from armi.reactor.parameters.exceptions import ParameterError
from armi.testing import loadTestReactor

if TYPE_CHECKING:
    from unittest import TestCase

    from armi.reactor import Core
    from armi.reactor.assemblies import Assembly
    from armi.reactor.blocks import Block

# Some parameters change because of symmetry but are not "volume integrated"
# so this marks them for skipping in the compare.
PARAMS_TO_IGNORE = ["maxAssemNum"]


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
        self.defaultParameterValue = 2
        # load default armi parameters for each object type
        self._loadDefaultParameters()

    @staticmethod
    def _getParameters(obj: object, paramList: Iterable[str]):
        # test if the deepcopy is necessary
        return deepcopy({param: obj.p[param] for param in paramList})

    @staticmethod
    def _getParamNamesFromDefs(pdefs: parameters.ParameterDefinitionCollection):
        return set([p.name for p in pdefs])

    def _loadDefaultParameters(self):
        self.defaultCoreParameterDefs = set(reactorParameters.defineCoreParameters())
        self.defaultAssemblyParameterDefs = set(assemblyParameters.getAssemblyParameterDefinitions())
        self.defaultBlockParameterDefs = set(blockParameters.getBlockParameterDefinitions())

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
            if name == "xsType":
                obj.p[name] = ["A"]
            elif name == "xsTypeNum":
                obj.p[name] = 65
            elif name == "notes":
                obj.p[name] = ""
            else:
                obj.p[name] = self.defaultParameterValue

    def _initializeCore(self, coreParams):
        paramDefNames = [pdef.name for pdef in self.defaultCoreParameterDefs]
        self.allCoreParameterKeys = set([p if isinstance(p, str) else p.name for p in self.core.p]).union(paramDefNames)
        self._initializeParameters(self.allCoreParameterKeys, self.core)

    def _initializeAssembly(self, assemblyParams):
        paramDefNames = [pdef.name for pdef in self.defaultAssemblyParameterDefs]
        self.allAssemblyParameterKeys = set(
            [p if isinstance(p, str) else p.name for p in self.partialAssembly.p]
        ).union(paramDefNames)
        self._initializeParameters(self.allAssemblyParameterKeys, self.partialAssembly)

    def _initializeBlock(self, blockParams):
        paramDefNames = [pdef.name for pdef in self.defaultBlockParameterDefs]
        self.allBlockParameterKeys = set([p if isinstance(p, str) else p.name for p in self.partialBlock.p]).union(
            paramDefNames
        )
        self._initializeParameters(self.allBlockParameterKeys, self.partialBlock)

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
            if referenceValue != perturbedValue and paramName not in PARAMS_TO_IGNORE:
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
    def _checkCore(self, userParams: Iterable[str]):
        coreReferenceParameters = self._getParameters(self.core, self.allCoreParameterKeys)
        yield  # yield to allow the core to be expanded
        corePerturbedParameters = self._getParameters(self.core, self.allCoreParameterKeys)
        self._compareParameters(coreReferenceParameters, corePerturbedParameters, userParams, "core")

    @contextmanager
    def _checkAssembly(self, userParams: Iterable[str]):
        assemblyReferenceParameters = self._getParameters(self.partialAssembly, self.allAssemblyParameterKeys)
        yield  # yield to allow the core to be expanded
        assemblyPerturbedParameters = self._getParameters(self.partialAssembly, self.allAssemblyParameterKeys)
        self._compareParameters(assemblyReferenceParameters, assemblyPerturbedParameters, userParams, "assembly")

    @contextmanager
    def _checkBlock(self, userParams: Iterable[str]):
        blockReferenceParameters = self._getParameters(self.partialBlock, self.allBlockParameterKeys)
        yield  # yield to allow the core to be expanded
        blockPerturbedParameters = self._getParameters(self.partialBlock, self.allBlockParameterKeys)
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
        self._initializeCore(coreParams)
        self._initializeAssembly(assemblyParams)
        self._initializeBlock(blockParams)

        with self._checkCore(coreParams), self._checkAssembly(assemblyParams), self._checkBlock(blockParams):
            self.r.core.growToFullCore(self.o.cs)
