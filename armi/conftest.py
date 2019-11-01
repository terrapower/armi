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

from armi import settings
from armi.settings import caseSettings


def pytest_sessionstart(session):
    import armi
    from armi import apps

    print("Initializing generic ARMI Framework application")
    armi.configure(apps.App())
    cs = caseSettings.Settings()
    settings.setMasterCs(cs)
