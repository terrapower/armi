# Copyright 2024 TerraPower, LLC
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
Importable testing utilities.

This is a very limited set of ARMI testing tools, meant to be importable as part of the ARMI API. The goal is to provide
a small set of high quality tools to help downstream ARMI developers write tests.

Notes
-----
This will not be a catch-all for random unit test functions. Be very sparing here.
"""

import itertools
import os
import pickle
import unittest
from typing import Optional

import yamlize

from armi import getPluginManagerOrFail, interfaces, materials, operators, plugins, runLog, settings
from armi.materials import uZr
from armi.reactor import assemblies, blocks, geometry, grids, reactors
from armi.reactor.components import Hexagon, Rectangle
from armi.testing.singleAssemblies import (  # noqa: F401
    BLOCK_DEFINITIONS_2PIN,
    BLOCK_DEFINITIONS_3PIN,
    GRID_DEFINITION,
    REGULAR_ASSEMBLY_DEF,
    buildEmptyHexAssembly,
    buildHexAssemblyFiveUZrUTh,
    buildHexAssemblyFourUZrUTh,
    buildHexAssemblySingleUZr,
    buildHexAssemblySingleUZrUTh,
    buildMixedPinAssembly,
    buildMixedThreePinAssembly,
)
from armi.testing.singleBlocks import (  # noqa: F401
    NUM_PINS_IN_COMPLEX_HEX_BLOCK,
    applyDummyData,
    buildComplexHexBlock,
    buildLinkedFuelHexBlock,
    buildLinkedFuelHexBlockNegativeArea,
    buildSimpleFuelHexBlock,
    buildSimpleFuelHexBlockNegativeArea,
)

TEST_ROOT = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests"))
TESTING_ROOT = os.path.dirname(os.path.abspath(__file__))
_ARMI_RUN_DIR = os.path.join(TESTING_ROOT, "reactors", "sodiumHexReactor")
ARMI_RUN_PATH = os.path.join(_ARMI_RUN_DIR, "armiRun.yaml")
COMPXS_PATH = os.path.join(TESTING_ROOT, "resources", "COMPXS.ascii")
ISOAA_PATH = os.path.join(TESTING_ROOT, "resources", "ISOAA")
_TEST_REACTORS = {}  # dictionary of pickled string of test reactors (for fast caching)


def loadTestReactor(inputFilePath=_ARMI_RUN_DIR, customSettings=None, inputFileName="armiRun.yaml", useCache=True):
    """
    Loads a test reactor. Can be used in other test modules.

    Parameters
    ----------
    inputFilePath : str, default=armi/testing/reactors/sodiumHexReactor
        Path to the directory of the input file.
    customSettings : dict with str keys and values of any type, default=None
        For each key in customSettings, the cs which is loaded from the armiRun.yaml will be overwritten to the value
        given in customSettings for that key.
    inputFileName : str, default="armiRun.yaml"
        Name of the input file to run.
    useCache : bool, default=True
        Look for a copy of this Reactor in the cache, if not in the cache, put it there. (Set to False when you are
        sure there will only be one test using this test reactor.)

    Notes
    -----
    If the armiRun.yaml test reactor 3 rings instead of 9, most unit tests that use it go ~4 times faster. The problem
    is it would breat a LOT of downstream tests that import this method. It is still worth it though.

    Returns
    -------
    o : Operator
    r : Reactor
    """
    from armi import operators, settings

    global _TEST_REACTORS
    fName = os.path.abspath(os.path.join(inputFilePath, inputFileName))
    customSettings = customSettings or {}
    reactorHash = hash(fName + str(customSettings))

    if useCache and reactorHash in _TEST_REACTORS:
        # return test reactor from cache
        o, r = pickle.loads(_TEST_REACTORS[reactorHash])
        o.reattach(r, o.cs)
        if not o.cs["materialNamespaceOrder"] and materials.getMaterialNamespaceOrder != ["armi.materials"]:
            materials.setMaterialNamespaceOrder(["armi.materials"])
        elif o.cs["materialNamespaceOrder"] != materials.getMaterialNamespaceOrder():
            # Reload materials if the current global namespace order doesn't match the case settings namespace order
            materials.setMaterialNamespaceOrder(o.cs["materialNamespaceOrder"])
        return o, r

    # Overwrite settings if desired
    cs = settings.Settings(fName=fName)
    if customSettings:
        cs = cs.modified(newSettings=customSettings)

    if "verbosity" not in customSettings:
        runLog.setVerbosity("error")

    # Always want to reset this hook if the namespace has changed unit tests have varying namespace settings
    if cs["materialNamespaceOrder"] != materials.getMaterialNamespaceOrder():
        _resetBeforeReactorConstructionHook()
    o = operators.factory(cs)
    r = reactors.loadFromCs(cs)

    o.initializeInterfaces(r)
    o.r.core.regenAssemblyLists()

    if useCache:
        # cache it for fast load for other future tests protocol=2 allows for classes with __slots__ but not
        # __getstate__ to be pickled
        _TEST_REACTORS[reactorHash] = pickle.dumps((o, o.r), protocol=2)

    return o, o.r


def _resetBeforeReactorConstructionHook():
    """
    Helper function that gathers all the plugins with a `beforeReactorConstruction` hook and resets the `onlyRunOnce`
    decorator. This is important to do for unit tests because different plugins may have a different namespace order
    and we need the materials accurate to the test to load.
    """
    pm = getPluginManagerOrFail()
    hook = pm.hook.beforeReactorConstruction

    for hookimpl in hook.get_hookimpls():
        func = hookimpl.function
        reset = getattr(func, "reset_onlyRunOnce", None)
        if callable(reset):
            reset()


def reduceTestReactorRings(r, cs, maxNumRings):
    """Helper method for the test reactor above.

    The goal is to reduce the size of the reactor for tests that don't need such a large reactor, and would run much
    faster with a smaller one.
    """
    maxRings = r.core.getNumRings()
    if maxNumRings > maxRings:
        runLog.info(f"The test reactor has a maximum of {maxRings} rings.")
        return
    elif maxNumRings <= 1:
        raise ValueError("The test reactor must have multiple rings.")

    # reducing the size of the test reactor, by removing the outer rings
    for ring in range(maxRings, maxNumRings, -1):
        r.core.removeAssembliesInRing(ring, cs)


def getEmptyHexReactor():
    """Make an empty hex reactor for use in tests."""
    from armi.reactor import blueprints

    bp = blueprints.Blueprints()
    reactor = reactors.Reactor("Reactor", bp)
    reactor.add(reactors.Core("Core"))
    reactor.core.spatialGrid = grids.HexGrid.fromPitch(1.0)
    reactor.core.spatialGrid.symmetry = geometry.SymmetryType(
        geometry.DomainType.THIRD_CORE, geometry.BoundaryType.PERIODIC
    )
    reactor.core.spatialGrid.geomType = geometry.HEX
    reactor.core.spatialGrid.armiObject = reactor.core

    return reactor


def getEmptyCartesianReactor(pitch=(10.0, 16.0), throughCenterAssembly=True):
    """Return an empty Cartesian reactor for use in tests."""
    from armi.reactor import blueprints

    bp = blueprints.Blueprints()
    reactor = reactors.Reactor("Reactor", bp)
    reactor.add(reactors.Core("Core"))
    reactor.core.spatialGrid = grids.CartesianGrid.fromRectangle(*pitch)
    reactor.core.spatialGrid.symmetry = geometry.SymmetryType(
        geometry.DomainType.QUARTER_CORE,
        geometry.BoundaryType.REFLECTIVE,
        throughCenterAssembly=throughCenterAssembly,
    )
    reactor.core.spatialGrid.geomType = geometry.CARTESIAN
    reactor.core.spatialGrid.armiObject = reactor.core

    return reactor


def buildOperatorOfEmptyHexBlocks(customSettings=None):
    """
    Builds a operator w/ a reactor object with some hex assemblies and blocks, but all are empty.

    Doesn't depend on inputs and loads quickly.

    Parameters
    ----------
    customSettings : dict
        Dictionary of off-default settings to update
    """
    cs = settings.Settings()  # fetch new
    if customSettings is None:
        customSettings = {}

    customSettings["db"] = False  # stop use of database
    cs = cs.modified(newSettings=customSettings)

    r = getEmptyHexReactor()
    r.core.setOptionsFromCs(cs)
    o = operators.Operator(cs)
    o.initializeInterfaces(r)

    a = assemblies.HexAssembly("fuel")
    a.spatialGrid = grids.AxialGrid.fromNCells(1)
    b = blocks.HexBlock("TestBlock")
    b.setType("fuel")
    dims = {"Tinput": 600, "Thot": 600, "op": 16.0, "ip": 1, "mult": 1}
    c = Hexagon("fuel", uZr.UZr(), **dims)
    b.add(c)
    a.add(b)
    a.spatialLocator = r.core.spatialGrid[1, 0, 0]
    o.r.core.add(a)
    o.r.sort()
    return o


def buildOperatorOfEmptyCartesianBlocks(customSettings=None):
    """
    Builds a operator w/ a reactor object with some Cartesian assemblies and blocks, but all are empty.

    Doesn't depend on inputs and loads quickly.

    Parameters
    ----------
    customSettings : dict
        Off-default settings to update
    """
    cs = settings.Settings()  # fetch new
    if customSettings is None:
        customSettings = {}

    customSettings["db"] = False  # stop use of database
    cs = cs.modified(newSettings=customSettings)

    r = getEmptyCartesianReactor()
    r.core.setOptionsFromCs(cs)
    o = operators.Operator(cs)
    o.initializeInterfaces(r)

    a = assemblies.CartesianAssembly("fuel")
    a.spatialGrid = grids.AxialGrid.fromNCells(1)
    b = blocks.CartesianBlock("TestBlock")
    b.setType("fuel")
    dims = {
        "Tinput": 600,
        "Thot": 600,
        "widthOuter": 16.0,
        "lengthOuter": 10.0,
        "widthInner": 1,
        "lengthInner": 1,
        "mult": 1,
    }
    c = Rectangle("fuel", uZr.UZr(), **dims)
    b.add(c)
    a.add(b)
    a.spatialLocator = r.core.spatialGrid[1, 0, 0]
    o.r.core.add(a)
    o.r.sort()
    return o


class ArmiTestHelper(unittest.TestCase):
    """Class containing common testing methods shared by many tests."""

    def compareFilesLineByLine(self, expectedFilePath, actualFilePath, falseNegList=None, eps=None):
        """
        Compare the contents of two files line by line.

        .. warning:: The file located at actualFilePath will be deleted if they do match.

        Some tests write text files that should be compared line-by-line with reference files. This method performs the
        comparison.

        This class of test is not ideal but does cover a lot of functionality quickly. To assist in the maintenance
        burden, the following standards are expected and enforced:

        * The reference file compared against will be called either ``[name]-ref.[ext]`` or ``[name].expected``.
        * The file that the test creates will be called ``[name]-test.[ext]`` or ``[name]``.

        Parameters
        ----------
        expectedFilePath: str
            Path to the reference or expected file
        actualFilePath: str
            Path to the file that will be compared to ``expectedFilePath``
        falseNegList: None or Iterable
            Optional argument. If two lines are not equal, then check if any values from ``falseNegList`` are in this
            line. If so, do not fail the test.
        eps: float, optional
            If provided, try to determine if the only difference between compared lines is in the value of something
            that can be parsed into a float, and the relative difference between the two floats is below the passed eps.
        """
        if falseNegList is None:
            falseNegList = []
        elif isinstance(falseNegList, str):
            falseNegList = [falseNegList]

        with open(expectedFilePath, "r") as expected, open(actualFilePath, "r") as actual:
            for lineIndex, (expectedLine, actualLine) in enumerate(itertools.zip_longest(expected, actual)):
                if expectedLine is None:
                    raise AssertionError("The test-generated file is longer than expected file")
                if actualLine is None:
                    raise AssertionError("The test-generated file is shorter than expected file")

                if not self.compareLines(actualLine, expectedLine, eps):
                    if any(falseNeg in line for falseNeg in falseNegList for line in (actualLine, expectedLine)):
                        pass
                    else:
                        raise AssertionError(
                            "Error on line {}:\nE>{}\nA<{}".format(
                                lineIndex, expectedLine.rstrip(), actualLine.rstrip()
                            )
                        )

        os.remove(actualFilePath)

    @staticmethod
    def compareLines(actual: str, expected: str, eps: Optional[float] = None):
        """
        Impl of line comparison for compareFilesLineByLine.

        If rstripped lines are equal -> Good. Otherwise, split on whitespace and try to parse element pairs as floats.
        If they are both parsable, compare with relative eps, if provided. A side effect of the epsilon comparison is
        that differing whitespace between words is treated as irrelevant.
        """
        actual = actual.rstrip()
        expected = expected.rstrip()

        if actual == expected:
            return True

        if eps is None:
            # no more in-depth comparison is allowed
            return False

        actualWords = actual.split()
        expectedWords = expected.split()

        if len(actualWords) != len(expectedWords):
            # different number of words can't possibly be the same enough
            return False

        for actualWord, expectedWord in zip(actualWords, expectedWords):
            actualVal = ArmiTestHelper._tryFloat(actualWord)
            expectedVal = ArmiTestHelper._tryFloat(expectedWord)

            if (actualVal is None) ^ (expectedVal is None):
                # could not coerce both words into a float, so they cannot possibly match
                return False

            if actualVal is not None:
                # we have two floats and can compare them
                if actualVal == expectedVal == 0:
                    continue
                elif abs(actualVal - expectedVal) / expectedVal > eps:
                    return False
            else:
                # strings, compare directly
                if actualWord != expectedWord:
                    return False

        # The lines should match.
        return True

    @staticmethod
    def _tryFloat(val: str) -> Optional[float]:
        try:
            return float(val)

        except ValueError:
            return None


class TestPlugin(unittest.TestCase):
    """Some sanity tests that can be used by implementing plugins."""

    plugin: Optional[plugins.ArmiPlugin] = None

    def test_defineBlueprintsSections(self):
        """Make sure that the defineBlueprintsSections hook is properly implemented."""
        if self.plugin is None:
            return
        if not hasattr(self.plugin, "defineBlueprintsSections"):
            return

        results = self.plugin.defineBlueprintsSections()
        if results is None:
            return

        # each plugin should return a list
        self.assertIsInstance(results, (list, type(None)))

        for result in results:
            self.assertIsInstance(result, tuple)
            self.assertEqual(len(result), 3)
            self.assertIsInstance(result[0], str)
            self.assertIsInstance(result[1], yamlize.Attribute)
            self.assertTrue(callable(result[2]))

    def test_exposeInterfaces(self):
        """Make sure that the exposeInterfaces hook is properly implemented."""
        if self.plugin is None:
            return

        cs = settings.Settings()
        results = self.plugin.exposeInterfaces(cs)
        if results is None or not results:
            return

        # each plugin should return a list
        self.assertIsInstance(results, list)
        for result in results:
            # Make sure all elements in the list satisfy the constraints of the hookspec
            self.assertIsInstance(result, tuple)
            self.assertEqual(len(result), 3)

            order, interface, kwargs = result

            self.assertIsInstance(order, (int, float))
            self.assertTrue(issubclass(interface, interfaces.Interface))
            self.assertIsInstance(kwargs, dict)
