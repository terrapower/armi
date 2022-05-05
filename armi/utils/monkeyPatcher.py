# Copyright 2022 TerraPower, LLC
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
  - applyPreOpPatch
  - applyPostOpPatch
  - applyPostInterfacePatch
  - applyPostRestartLoadPatch

The easiest way to understand the hook locations is to grep the codebase for
the calls listed above.

If the patchFilePath parameter is not specified in the ARMI input yaml, the
hooks will return immediately.

The format of a patch file is almost entirely left to the end user, however
there are some examples in the test module for anticipated uses of this module.
Specifically, how to modify objects in higher levels of scope.

Input
-----
The module requires a valid input file located at "patchFilePath" that 
contains the functions:
  - preOpPatch
  - postOpPatch
  - postInterfacePatch
  - postRestartLoadPatch

Each of these functions MUST be defined in the patchfile, even if they simply
return on call.

These functions are called in armi.cases.case.py and 
armi.bookkeeping.mainInterface.py. In the event that no patch file path was
specified, the functions in this module will return immediately. The logic
was handled here in order to keep changes to the main armi workflow low.
"""
import os
import importlib.util

from armi.settings import caseSettings
from armi.utils import getFileSHA1Hash
from armi import runLog


def checkPatchFlag(f):
    """
    This checks if the patchFlag is True. This is used to build in a short-
    circuit for the patcher, where the patcher will return to the main ARMI
    process if no patchfile was provided.

    The reason for including this is to keep modifications to the main ARMI
    code to a minimum, so this effectively handles the check of whether there
    is a patch to apply or not. This is formatted as a decorator since the
    operation is applied to all the patch hooks.
    """

    def newfunc(*args, **kwargs):
        self_arg = args[0]
        if self_arg.patchFlag:
            return f(*args, **kwargs)
        else:
            return

    return newfunc


class Patcher:
    """
    A controller object for patching ARMI at runtime. See module docstring for
    instructions on usage and patch file formatting.

    Input
    -----
    cs : armi.settings.caseSettings
        The case settings for the ARMI job. The path to the patch file is stored
        in the case settings.
    """

    def __init__(self, cs: caseSettings):
        self.patchPath = cs["patchFilePath"]
        self.patchFlag = True
        if self.patchPath == "":
            runLog.info("No patch file provided.")
            self.patchFlag = False
            return
        if not os.path.isfile(self.patchPath):
            self.patchFlag = False
            runLog.error("The provided path to the patch file is invalid.")
            raise IOError("The provided path to the patch file is invalid.")
        self.hash = getFileSHA1Hash(self.patchPath)
        runLog.info(f"The patch file hash is: {self.hash}")
        spec = importlib.util.spec_from_file_location("userPatch", self.patchPath)
        self.userPatch = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.userPatch)

    @checkPatchFlag
    def applyPreOpPatch(self, upper_globals, upper_locals):
        """
        Attempt to apply the pre-operator patch specified in the user patch file.
        """
        try:
            self.userPatch.preOpPatch(upper_globals, upper_locals)
        except Exception as err:
            runLog.error(err)
            raise

    @checkPatchFlag
    def applyPostOpPatch(self, upper_globals, upper_locals):
        """
        Attempt to apply the post-operator patch specified in the user patch file.
        """
        try:
            self.userPatch.postOpPatch(upper_globals, upper_locals)
        except Exception as err:
            runLog.error(err)
            raise

    @checkPatchFlag
    def applyPostInterfacePatch(self, upper_globals, upper_locals):
        """
        Attempt to apply the post-interface patch specified in the user patch file.
        """
        try:
            self.userPatch.postInterfacePatch(upper_globals, upper_locals)
        except Exception as err:
            runLog.error(err)
            raise

    @checkPatchFlag
    def applyPostRestartLoadPatch(self, upper_globals, upper_locals):
        """
        Attempt to apply the post-restart-load patch specified in the user patch file.
        """
        try:
            self.userPatch.postRestartLoadPatch(upper_globals, upper_locals)
        except Exception as err:
            runLog.error(err)
            raise
