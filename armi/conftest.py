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
Per-directory pytest plugin configuration used only during development/testing.

This is a used to manipulate the environment under which pytest runs the unit tests. This
can act as a one-stop-shop for manipulating the sys.path. This can be used to set paths
when using the ARMI framework as a submodule in a larger project.

Tests must be invoked via pytest for this to have any affect, for example::

    $ pytest -n 6 armi

"""

import os

import matplotlib

from armi import apps, configure, context
from armi.settings import caseSettings
from armi.tests import TEST_ROOT


def pytest_sessionstart(session):
    print("Initializing generic ARMI Framework application")
    configure(apps.App())
    bootstrapArmiTestEnv()


def bootstrapArmiTestEnv():
    """
    Perform ARMI config appropriate for running unit tests.

    .. tip:: This can be imported and run from other ARMI applications
        for test support.
    """
    from armi.nucDirectory import nuclideBases

    cs = caseSettings.Settings()

    context.Mode.setMode(context.Mode.BATCH)
    # Need to init burnChain.
    # see armi.cases.case.Case._initBurnChain
    with open(cs["burnChainFileName"]) as burnChainStream:
        nuclideBases.imposeBurnChain(burnChainStream)

    # turn on a non-interactive mpl backend to minimize errors related to
    # initializing Tcl in parallel tests
    matplotlib.use("agg")

    # set and create a test-specific FAST_PATH for parallel unit testing
    # Not all unit tests have operators, and operators are usually
    # responsible for making FAST_PATH, so we make it here.
    # It will be deleted by the atexit hook.
    context.activateLocalFastPath()
    if not os.path.exists(context.getFastPath()):
        os.makedirs(context.getFastPath())

    # some tests need to find the TEST_ROOT via an env variable when they're
    # filling in templates with ``$ARMITESTBASE`` in them or opening
    # input files use the variable in an `!include` tag. Thus
    # we provide it here.
    os.environ["ARMITESTBASE"] = TEST_ROOT
