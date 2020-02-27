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
Metadata describing an ARMI distribution.
"""

# duplicating with setup.py for now. This is because in order to import meta.py, we
# need to run armi.__init__, which does a whole heck of a lot of stuff that setup.py
# shouldn't need. We should clean this up in the future.
__version__ = "0.1.4"
