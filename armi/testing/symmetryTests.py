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
from copy import deepcopy
from typing import Iterable

import numpy as np

from armi.reactor import blockParameters, reactorParameters
from armi.reactor.components import componentParameters
from armi.testing import loadTestReactor


class SymmetryFactorTester:
    """
    A test helper for symmetry factors.

    Structured as a class so it can be imported with a list of expected parameters. The individual tests then check
    which parameters are altered by symmetry-aware operations and if there are any parameters that change but are not in
    the "expected" list an error is raised.
    """

    def __init__(self):
        self.o, self.r = loadTestReactor()
        # there is exactly one assembly with 3-symmetry in the test core
        self.partialAssembly = [a for a in self.r.core.getAssemblies() if a.getSymmetryFactor() == 3][0]
        # get default armi parameters for each object type here
        self._getDefaultParameters()

    # Need a method to set the defaults for parameters by inspecting the type of the parameter and initializing
    # appropriately

    @staticmethod
    def _getParameters(obj: object, paramList: Iterable[str]):
        # test if the deepcopy is necessary
        return deepcopy({param: obj.p[param] for param in paramList})

    def _getDefaultParameters(self):
        self.defaultReactorParamNames = [p.name for p in reactorParameters.defineReactorParameters()]
        self.defaultCoreParamNames = [p.name for p in reactorParameters.defineCoreParameters()]
        self.defaultBlockParameterNames = [p.name for p in blockParameters.getBlockParameterDefinitions()]
        tempComponentParams = []
        for _name, func in inspect.getmembers(componentParameters, inspect.isfunction):
            if inspect.signature(func) == "()":
                tempComponentParams.append(func())
        self.defaultComponentParameterNames = [p.name for item in tempComponentParams for p in item]
        # self.defaultComponentParameters = componentParameters.getCircleParameterDefinitions()
        # self.defaultComponentParameters = componentParameters.getComponentParameterDefinitions()
        # self.defaultComponentParameters = componentParameters.getCubeParameterDefinitions()
        # self.defaultComponentParameters = componentParameters.getFilletedHexagonParameterDefinitions()
        # self.defaultComponentParameters = componentParameters.getUnshapedParameterDefinitions()
        # self.defaultComponentParameters = componentParameters.getHexagonParameterDefinitions()

    def initializeParameter(self, parameterName, obj):
        paramType = type(parameterName)
        if paramType.isinstance(np.ndarray):
            obj.p = np.array([2.0, 2.0, 2.0])
        else:
            obj.p = paramType(2.0)

    def symmetryFactorBlockTest(self, paramDict: dict):
        """
        Runs a test of how symmetry factors apply to parameters during partial-to-full core coversions and vice-versa.

        This helper provides a convenient way for plugins to test that symmetry factors are applied correctly to flagged
        parameters when the core is converted.

        Parameters
        ----------
        paramDict : dict, optional
            Dictionary of {parameter: value} pairs. If provided, the values will be assigned to the corresponding
            parameter on the blocks
        """
        for parameter, value in paramDict.items():
            self.partialAssembly.p[parameter] = value

        # temporarily use b to get the outline, iterate over the blocks later or get all blocks
        b = self.partialAssembly.getBlocks()[0]

        refParams = self._getParameters(b, paramDict.keys())

        # context manager trick here
        self.r.core.growToFullCore(self.o.cs)

        resultParams = self._getParameters(b, paramDict.keys())

        ratios = dict()
        for parameter in resultParams.keys():
            ratios[parameter] = resultParams[parameter] / refParams[parameter]

        return ratios, resultParams
