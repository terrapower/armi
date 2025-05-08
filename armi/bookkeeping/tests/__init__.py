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
Bookkeeping test package.

This may seem a little bit over-engineered, but the jupyter notebooks that get run by
the test_historyTracker are also used in the documentation system, so providing a list
of related files from this package is useful. Also, these are organized like this to
prevent having to import the world just to get something like a list of strings.
"""

from armi.bookkeeping.tests._constants import *  # noqa: F403
