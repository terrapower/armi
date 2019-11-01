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

import os
import glob

import armi
from armi.cli.entryPoint import EntryPoint


class CleanTemps(EntryPoint):
    """
    Clear temp directories created by ARMI.
    """

    name = "clean-temps"

    def invoke(self):
        # get the case title.
        armi.cleanTempDirs(0)
