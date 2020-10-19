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

    $ pytest -n6 framework/armi

"""
import os

import matplotlib

from armi import settings
from armi.settings import caseSettings


def pytest_sessionstart(session):
    import armi
    from armi import apps
    from armi import context
    from armi.nucDirectory import nuclideBases

    print("Initializing generic ARMI Framework application")
    armi.configure(apps.App())
    cs = caseSettings.Settings()
    settings.setMasterCs(cs)
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
    if not os.path.exists(context.FAST_PATH):
        os.makedirs(context.FAST_PATH)
