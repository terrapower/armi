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

This is a very limited set of ARMI testing tools, meant to be importable as part of the ARMI API.
The goal is to provide a small set of high quality tools to help downstream ARMI developers write
tests.

Notes
-----
This will not be a catch-all for random unit test functions. Be very sparing here.
"""

import os
import pickle

from armi import operators, runLog, settings
from armi.reactor import reactors
from armi.tests import ARMI_RUN_PATH, TEST_ROOT

_THIS_DIR = os.path.dirname(__file__)
_TEST_REACTOR = None  # pickled string of test reactor (for fast caching)


def loadTestReactor(
    inputFilePath=TEST_ROOT,
    customSettings=None,
    inputFileName="armiRun.yaml",
):
    """
    Loads a test reactor. Can be used in other test modules.

    Parameters
    ----------
    inputFilePath : str, default=TEST_ROOT
        Path to the directory of the input file.

    customSettings : dict with str keys and values of any type, default=None
        For each key in customSettings, the cs which is loaded from the armiRun.yaml will be
        overwritten to the value given in customSettings for that key.

    inputFileName : str, default="armiRun.yaml"
        Name of the input file to run.

    Notes
    -----
    If the armiRun.yaml test reactor 3 rings instead of 9, most unit tests that use it go 4 times
    faster (based on testing). The problem is it would breat a LOT of downstream tests that import
    this method. It is still worth it though.

    Returns
    -------
    o : Operator
    r : Reactor
    """
    global _TEST_REACTOR
    fName = os.path.join(inputFilePath, inputFileName)
    customSettings = customSettings or {}
    isPickeledReactor = fName == ARMI_RUN_PATH and customSettings == {}

    if isPickeledReactor and _TEST_REACTOR:
        # return test reactor only if no custom settings are needed.
        o, r, assemNum = pickle.loads(_TEST_REACTOR)
        o.reattach(r, o.cs)
        return o, r

    cs = settings.Settings(fName=fName)

    # Overwrite settings if desired
    if customSettings:
        cs = cs.modified(newSettings=customSettings)

    if "verbosity" not in customSettings:
        runLog.setVerbosity("error")

    cs = cs.modified(newSettings={})
    o = operators.factory(cs)
    r = reactors.loadFromCs(cs)

    o.initializeInterfaces(r)
    o.r.core.regenAssemblyLists()

    if isPickeledReactor:
        # cache it for fast load for other future tests protocol=2 allows for classes with __slots__
        # but not __getstate__ to be pickled
        _TEST_REACTOR = pickle.dumps((o, o.r, o.r.p.maxAssemNum), protocol=2)

    return o, o.r


def reduceTestReactorRings(r, cs, maxNumRings):
    """Helper method for the test reactor above.

    The goal is to reduce the size of the reactor for tests that don't need such a large reactor,
    and would run much faster with a smaller one.
    """
    maxRings = r.core.getNumRings()
    if maxNumRings > maxRings:
        runLog.info("The test reactor has a maximum of {} rings.".format(maxRings))
        return
    elif maxNumRings <= 1:
        raise ValueError("The test reactor must have multiple rings.")

    # reducing the size of the test reactor, by removing the outer rings
    for ring in range(maxRings, maxNumRings, -1):
        r.core.removeAssembliesInRing(ring, cs)
