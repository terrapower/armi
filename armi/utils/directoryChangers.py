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
import random
import shutil
import string

import armi
from armi import runLog
from armi.utils import pathTools


def _changeDirectory(destination):
    if os.path.exists(destination):
        os.chdir(destination)
    else:
        raise IOError(
            "Cannot change directory to non-existent location: {}".format(destination)
        )


class DirectoryChanger(object):
    r"""
    Utility class to change directory

    Use with 'with' statements to execute code in a different dir, guaranteeing a clean
    return to the original directory

    >>> with DirectoryChanger(r'C:\whatever')
    ...     pass

    """

    def __init__(self, destination, filesToMove=None, filesToRetrieve=None):
        """Establish the new and return directories"""
        self.initial = pathTools.armiAbsPath(os.getcwd())
        self.destination = None
        if destination is not None:
            self.destination = pathTools.armiAbsPath(destination)
        self._filesToMove = filesToMove or []
        self._filesToRetrieve = filesToRetrieve or []

    def __enter__(self):
        """At the inception of a with command, navigate to a new directory if one is supplied."""
        runLog.debug("Changing directory to {}".format(self.destination))
        self.moveFiles()
        self.open()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """At the termination of a with command, navigate back to the original directory."""
        runLog.debug("Returning to directory {}".format(self.initial))
        self.retrieveFiles()
        self.close()

    def __repr__(self):
        """Print the initial and destination paths"""
        return "<{} {} to {}>".format(
            self.__class__.__name__, self.initial, self.destination
        )

    def open(self):
        """
        User requested open, used to stalling the close from a with statement.

        This method has been made for old uses of :code:`os.chdir()` and is not
        recommended.  Please use the with statements
        """
        if self.destination:
            _changeDirectory(self.destination)

    def close(self):
        """User requested close."""
        if self.initial != os.getcwd():
            _changeDirectory(self.initial)

    def moveFiles(self):
        initialPath = self.initial
        destinationPath = self.destination
        self._transferFiles(initialPath, destinationPath, self._filesToMove)

    def retrieveFiles(self):
        """Retrieve any desired files."""
        initialPath = self.destination
        destinationPath = self.initial
        self._transferFiles(initialPath, destinationPath, self._filesToRetrieve)

    def _transferFiles(self, initialPath, destinationPath, fileList):
        if not fileList:
            return
        if not os.path.exists(destinationPath):
            os.mkdir(destinationPath)
        for ff in fileList:
            fromPath = os.path.join(initialPath, ff)
            toPath = os.path.join(destinationPath, ff)
            runLog.extra("Moving {} to {}".format(fromPath, toPath))
            shutil.move(fromPath, toPath)


class TemporaryDirectoryChanger(DirectoryChanger):
    """
    Create temporary directory, changes into it, and if there is no error/exception
    generated when using a :code:`with` statement, it deletes the directory.

    Notes
    -----
    If there is an error/exception generated while in a :code:`with` statement, the
    temporary directory contents will be copied to the original directory and then the
    temporary directory will be deleted.
    """

    _home = armi.context.FAST_PATH

    def __init__(self, root=None, filesToMove=None, filesToRetrieve=None):
        DirectoryChanger.__init__(self, root, filesToMove, filesToRetrieve)
        root = root or TemporaryDirectoryChanger._home
        if not os.path.exists(root):
            os.makedirs(root)
        self.initial = os.path.abspath(os.getcwd())
        self.destination = TemporaryDirectoryChanger.GetRandomDirectory(root)
        while os.path.exists(self.destination):
            self.destination = TemporaryDirectoryChanger.GetRandomDirectory(root)

    @classmethod
    def GetRandomDirectory(cls, root):
        return os.path.join(
            root,
            "temp-"
            + "".join(
                random.choice(string.ascii_letters + string.digits) for _ in range(10)
            ),
        )

    def __enter__(self):
        os.mkdir(self.destination)
        self.moveFiles()
        os.chdir(self.destination)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        os.chdir(self.initial)
        self.retrieveFiles()
        shutil.rmtree(self.destination)


class ForcedCreationDirectoryChanger(DirectoryChanger):
    """
    Creates the directory tree necessary to reach your desired destination

    Attributes
    ----------
    clean : bool
        if True and the directory exists, clear all contents on entry.
    """

    def __init__(
        self, destination, filesToMove=None, filesToRetrieve=None, clean=False
    ):
        DirectoryChanger.__init__(self, destination, filesToMove, filesToRetrieve)
        self.clean = clean

    def __enter__(self):
        if not os.path.exists(self.destination):
            try:
                os.makedirs(self.destination)
            except OSError:
                pass  # to avoid race conditions on worker nodes
        self.moveFiles()
        os.chdir(self.destination)
        if self.clean:
            shutil.rmtree(".", ignore_errors=True)
        return self


def directoryChangerFactory():
    if armi.MPI_SIZE > 1:
        from .directoryChangersMpi import MpiDirectoryChanger

        return MpiDirectoryChanger
    else:
        return DirectoryChanger
