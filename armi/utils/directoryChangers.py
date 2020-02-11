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
    """
    Utility to change directory.

    Parameters
    ----------
    destination : str
        Path of directory to change into
    filesToMove : list of str, optional
        Filenames to bring from the CWD into the destination
    filesToRetrieve : list of str, optional
        Filenames to bring back from the destination to the cwd
    dumpOnException : bool, optional
        Flag to tell system to retrieve the entire directory if an exception
        is raised within a the context manager.

    Use with 'with' statements to execute code in a different dir, guaranteeing a clean
    return to the original directory

    >>> with DirectoryChanger('C:\\whatever')
    ...     pass

    """

    def __init__(
        self, destination, filesToMove=None, filesToRetrieve=None, dumpOnException=True
    ):
        """Establish the new and return directories"""
        self.initial = pathTools.armiAbsPath(os.getcwd())
        self.destination = None
        if destination is not None:
            self.destination = pathTools.armiAbsPath(destination)
        self._filesToMove = filesToMove or []
        self._filesToRetrieve = filesToRetrieve or []
        self._dumpOnException = dumpOnException

    def __enter__(self):
        """At the inception of a with command, navigate to a new directory if one is supplied."""
        runLog.debug("Changing directory to {}".format(self.destination))
        self.moveFiles()
        self.open()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """At the termination of a with command, navigate back to the original directory."""
        runLog.debug("Returning to directory {}".format(self.initial))
        if exc_type is not None and self._dumpOnException:
            runLog.info(
                "An exception was raised within a DirectoryChanger. "
                "Retrieving entire folder for debugging."
            )
            self._retrieveEntireFolder()
        else:
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
        fileList = self._filesToRetrieve
        self._transferFiles(initialPath, destinationPath, fileList)

    def _retrieveEntireFolder(self):
        """Retrieve all files."""
        initialPath = self.destination
        destinationPath = self.initial
        folderName = os.path.split(self.destination)[1]
        destinationPath = os.path.join(destinationPath, f"dump-{folderName}")
        fileList = os.listdir(self.destination)
        self._transferFiles(initialPath, destinationPath, fileList)

    @staticmethod
    def _transferFiles(initialPath, destinationPath, fileList):
        """
        Transfer files into or out of the directory.

        .. warning:: On Windows the max number of characters in a path is 260.
            If you exceed this you will see FileNotFound errors here.

        """
        if not fileList:
            return
        if not os.path.exists(destinationPath):
            os.mkdir(destinationPath)
        for ff in fileList:
            if isinstance(ff, tuple):
                # allow renames in transit
                fromName, destName = ff
            else:
                fromName, destName = ff, ff

            fromPath = os.path.join(initialPath, fromName)
            toPath = os.path.join(destinationPath, destName)
            runLog.extra("Copying {} to {}".format(fromPath, toPath))
            shutil.copy(fromPath, toPath)


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

    def __init__(
        self, root=None, filesToMove=None, filesToRetrieve=None, dumpOnException=True
    ):
        DirectoryChanger.__init__(
            self, root, filesToMove, filesToRetrieve, dumpOnException
        )
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
        return DirectoryChanger.__enter__(self)

    def __exit__(self, exc_type, exc_value, traceback):
        DirectoryChanger.__exit__(self, exc_type, exc_value, traceback)
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
        self,
        destination,
        filesToMove=None,
        filesToRetrieve=None,
        dumpOnException=True,
        clean=False,
    ):
        DirectoryChanger.__init__(
            self, destination, filesToMove, filesToRetrieve, dumpOnException
        )
        self.clean = clean

    def __enter__(self):
        if not os.path.exists(self.destination):
            runLog.debug(f"Creating destination folder {self.destination}")
            try:
                os.makedirs(self.destination)
            except OSError:
                # even though we checked exists, this still fails
                # sometimes when multiple MPI nodes try
                # to make the dirs due to I/O delays
                runLog.debug(f"Failed to make destination folder")
        else:
            runLog.debug(f"Destination folder already exists: {self.destination}")
        DirectoryChanger.__enter__(self)
        if self.clean:
            shutil.rmtree(".", ignore_errors=True)
        return self


def directoryChangerFactory():
    if armi.MPI_SIZE > 1:
        from .directoryChangersMpi import MpiDirectoryChanger

        return MpiDirectoryChanger
    else:
        return DirectoryChanger
