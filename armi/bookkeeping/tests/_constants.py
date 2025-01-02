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
Plain old data for the bookkeeping tests.

These are stored here so that they can be accessed from within this test package, but
also re-exported by `__init__.py`, so that other things (like the documentation system)
can use it without having to import the rest of ARMI.
"""
import os

from armi.tests import TEST_ROOT

# These files are needed to run the data_model ipython notebook, which is done in
# test_historyTracker, and when building the docs.
TUTORIAL_FILES = [
    os.path.join(TEST_ROOT, "anl-afci-177", "anl-afci-177-blueprints.yaml"),
    os.path.join(TEST_ROOT, "anl-afci-177", "anl-afci-177-coreMap.yaml"),
    os.path.join(TEST_ROOT, "anl-afci-177", "anl-afci-177-fuelManagement.py"),
    os.path.join(TEST_ROOT, "anl-afci-177", "anl-afci-177.yaml"),
    os.path.join(TEST_ROOT, "tutorials", "data_model.ipynb"),
]
