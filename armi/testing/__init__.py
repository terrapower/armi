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

import os
import pickle

from armi import runLog
from armi.reactor import geometry, grids, reactors

TEST_ROOT = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests"))
TESTING_ROOT = os.path.dirname(os.path.abspath(__file__))
ARMI_RUN_PATH = os.path.join(TEST_ROOT, "armiRun.yaml")
COMPXS_PATH = os.path.join(TEST_ROOT, "COMPXS.ascii")
ISOAA_PATH = os.path.join(TEST_ROOT, "ISOAA")
_TEST_REACTORS = {}  # dictionary of pickled string of test reactors (for fast caching)


def loadTestReactor(inputFilePath=TEST_ROOT, customSettings=None, inputFileName="armiRun.yaml", useCache=True):
    """
    Loads a test reactor. Can be used in other test modules.

    Parameters
    ----------
    inputFilePath : str, default=TEST_ROOT
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
        return o, r

    # Overwrite settings if desired
    cs = settings.Settings(fName=fName)
    if customSettings:
        cs = cs.modified(newSettings=customSettings)

    if "verbosity" not in customSettings:
        runLog.setVerbosity("error")

    o = operators.factory(cs)
    r = reactors.loadFromCs(cs)

    o.initializeInterfaces(r)
    o.r.core.regenAssemblyLists()

    if useCache:
        # cache it for fast load for other future tests protocol=2 allows for classes with __slots__ but not
        # __getstate__ to be pickled
        _TEST_REACTORS[reactorHash] = pickle.dumps((o, o.r), protocol=2)

    return o, o.r


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
    """Make an empty hex reactor used in some tests."""
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


def getEmptyCartesianReactor(pitch=(10.0, 16.0)):
    """Return an empty Cartesian reactor used in some tests."""
    from armi.reactor import blueprints

    bp = blueprints.Blueprints()
    reactor = reactors.Reactor("Reactor", bp)
    reactor.add(reactors.Core("Core"))
    reactor.core.spatialGrid = grids.CartesianGrid.fromRectangle(*pitch)
    reactor.core.spatialGrid.symmetry = geometry.SymmetryType(
        geometry.DomainType.QUARTER_CORE,
        geometry.BoundaryType.REFLECTIVE,
        throughCenterAssembly=True,
    )
    reactor.core.spatialGrid.geomType = geometry.CARTESIAN
    reactor.core.spatialGrid.armiObject = reactor.core

    return reactor
