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
MPI Directory changers.

This is a separate module largely to minimize potential cyclic imports
because the mpi action stuff requires an import of the reactor framework.
"""

from armi import mpiActions
from armi.utils import directoryChangers


class MpiDirectoryChanger(directoryChangers.DirectoryChanger):
    """Change all nodes to specified directory.

    Notes
    -----
    `filesToMove` and `filesToRetrieve` do not get broadcasted to worker nodes. This is
    intended since this would cause a race condition between deleting and moving files.
    """

    def __init__(self, destination, outputPath=None):
        """Establish the new and return directories.

        Parameters
        ----------
        destination : str
            destination directory
        outputPath : str, optional
            directory for outputs
        """
        directoryChangers.DirectoryChanger.__init__(
            self, destination, outputPath=outputPath
        )

    def open(self):
        cdma = _ChangeDirectoryMpiAction(self.destination)
        # line below looks a little weird, but it returns the instance
        cdma = cdma.broadcast(cdma)
        cdma.invoke(None, None, None)

    def close(self):
        cdma = _ChangeDirectoryMpiAction(self.initial)
        cdma = cdma.broadcast(cdma)
        cdma.invoke(None, None, None)


class _ChangeDirectoryMpiAction(mpiActions.MpiAction):
    """Change directory action."""

    def __init__(self, destination):
        mpiActions.MpiAction.__init__(self)
        self._destination = destination

    def invokeHook(self):
        directoryChangers._changeDirectory(self._destination)
        return True
