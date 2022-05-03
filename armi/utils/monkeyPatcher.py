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
A module for monkeypatching ARMI at various times during execution.

Monkeypatching is the act of altering or extending the functionality of 
software at runtime. This module allows the user to introduce arbitrary 
code while ARMI is running, with hooks at specific locations in the ARMI
codebase. This allows testing of new ARMI functionality or modification of
reactor parameters on the fly from a centralized file. Centralization of the
file aids in checking and configuration control for exploratory work.

Use
---
This module is activated when the user sets the "patchFilePath" parameter
in the ARMI input yaml to a valid file path. The following hooks are then 
active and will pull in the custom code as specified in the patch file:
  - hook1
  - hook2
  - etc (update these)

Input
-----
The module requires a valid input file located at "patchFilePath" that 
contains at least one function named:
  - validname1
  - validname2
  - etc (update these)

These functions are called in armi.cases.case.py and 
armi.bookkeeping.mainInterface.py. In the event that no patch file path was
specified, the functions in this module will return immediately. The logic
was handled here in order to keep changes to the main armi workflow low.
"""
import os
import importlib.util

from armi.settings import caseSettings
from armi.utils import getFileSHA1Hash
# from unittest.mock import patch

class Patcher:
    """
    A controller object for patching ARMI at runtime.
    """

    def __init__(self, cs: caseSettings):
        self.patchPath = cs["patchFilePath"]
        if self.patchPath == "":
            print("No custom patch file provided.")
            return
        if not os.path.isfile(self.patchPath):
            raise IOError("The provided path to the patch file is invalid.")
        self.hash = getFileSHA1Hash(self.patchPath)
        #TODO: log the hash somewhere.
        spec = importlib.util.spec_from_file_location("userPatch", self.patchPath)
        self.userPatch = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.userPatch) 

    def applyPreOpPatch(self):
        """
        Attempt to apply the pre-operator patch specified in the user patch file.
        """
        # Short circuit calls to the patcher here to keep the ARMI codebase clean
        if self.patchPath == "":
            return
        try:
            self.userPatch.preOpPatch()
        except Exception as err:
            print("Error while applying preOpPatch.")
            raise err

    def applyPostOpPatch(self):
        """
        Attempt to apply the post-operator patch specified in the user patch file.
        """
        # Short circuit calls to the patcher here to keep the ARMI codebase clean
        if self.patchPath == "":
            return
        try:
            self.userPatch.postOpPatch()
        except Exception as err:
            print("Error while applying postOpPatch.")
            raise err

    def applyPostInterfacePatch(self):
        """
        Attempt to apply the post-interface patch specified in the user patch file.
        """
        # Short circuit calls to the patcher here to keep the ARMI codebase clean
        if self.patchPath == "":
            return
        try:
            self.userPatch.postInterfacePatch()
        except Exception as err:
            print("Error while applying postInterfacePatch.")
            raise err

    def applyPostRestartLoadPatch(self):
        """
        Attempt to apply the post-restart-load patch specified in the user patch file.
        """
        # Short circuit calls to the patcher here to keep the ARMI codebase clean
        if self.patchPath == "":
            return
        try:
            self.userPatch.postRestartLoadPatch()
        except Exception as err:
            print("Error while applying postRestartLoadPatch.")
            raise err

if __name__ == "__main__":
    patcher = Patcher({"patchFilePath":"C:\\Users\\bsculac\\codes\\testpatch\\testpatch.py"})
    patcher.applyPreOpPatch()
    patcher.applyPostOpPatch()
    patcher.applyPostInterfacePatch()
    patcher.applyPostRestartLoadPatch()