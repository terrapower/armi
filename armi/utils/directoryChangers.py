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

import glob
import os
import pathlib
import random
import shutil
import string

from armi import context
from armi import runLog
from armi.utils import pathTools


def _changeDirectory(destination):
    if os.path.exists(destination):
        os.chdir(destination)
    else:
        raise IOError(
            "Cannot change directory to non-existent location: {}".format(destination)
        )


class DirectoryChanger:
    """
    Utility to change directory.

    Use with 'with' statements to execute code in a different dir, guaranteeing a clean
    return to the original directory

    >>> with DirectoryChanger('C:\\whatever')
    ...     pass

    Parameters
    ----------
    destination : str
        Path of directory to change into
    filesToMove : list of str, optional
        Filenames to bring from the CWD into the destination
    filesToRetrieve : list of str, optional
        Filenames to bring back from the destination to the cwd. Note that if any of these
        files do not exist then the file will be skipped and a warning will be provided.
    dumpOnException : bool, optional
        Flag to tell system to retrieve the entire directory if an exception
        is raised within a the context manager.
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
        """
        Copy ``filesToMove`` into the destination directory on entry.
        """
        initialPath = self.initial
        destinationPath = self.destination
        self._transferFiles(initialPath, destinationPath, self._filesToMove)

    def retrieveFiles(self):
        """
        Copy ``filesToRetrieve`` back into the initial directory on exit.
        """
        initialPath = self.destination
        destinationPath = self.initial
        fileList = self._filesToRetrieve
        self._transferFiles(initialPath, destinationPath, fileList)

    def _retrieveEntireFolder(self):
        """
        Retrieve all files to a dump directory.

        This is used when an exception is caught by the DirectoryChanger to rescue the
        entire directory to aid in debugging. Typically this is only called if
        ``dumpOnException`` is True.
        """
        initialPath = self.destination
        folderName = os.path.split(self.destination)[1]
        recoveryPath = os.path.join(self.initial, f"dump-{folderName}")
        fileList = os.listdir(self.destination)
        shutil.copytree(self.destination, recoveryPath)

    @staticmethod
    def _transferFiles(initialPath, destinationPath, fileList):
        """
        Transfer files into or out of the directory.

        This is used in ``moveFiles`` and ``retrieveFiles`` to shuffle files about when
        creating a target directory or when coming back, respectively. Beware that this
        uses ``shutil.copy()`` under the hood, which doesn't play nicely with
        directories. Future revisions should improve this.

        Parameters
        ----------
        initialPath : str
            Path to the folder to find files in.
        destinationPath: str
            Path to the folder to move file to.
        fileList : list of str or list of tuple
            File names to move from initial to destination. If this is a
            simple list of strings, the files will be transferred. Alternatively
            tuples of (initialName, finalName) are allowed if you want the file
            renamed during transit. In the non-tuple option, globs/wildcards
            are allowed.

        .. warning:: On Windows the max number of characters in a path is 260.
            If you exceed this you will see FileNotFound errors here.

        """
        if not fileList:
            return
        if not os.path.exists(destinationPath):
            os.mkdir(destinationPath)
        for pattern in fileList:
            if isinstance(pattern, tuple):
                # allow renames in transit
                fromName, destName = pattern
                copies = [(fromName, destName)]
            else:
                # expand globs if they're given
                copies = []
                for ff in glob.glob(pattern):
                    # renaming not allowed with globs
                    copies.append((ff, ff))

            for fromName, destName in copies:
                fromPath = os.path.join(initialPath, fromName)
                if not os.path.exists(fromPath):
                    runLog.warning(f"{fromPath} does not exist and will not be copied.")
                    continue

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

    def __init__(
        self, root=None, filesToMove=None, filesToRetrieve=None, dumpOnException=True
    ):
        DirectoryChanger.__init__(
            self, root, filesToMove, filesToRetrieve, dumpOnException
        )

        # If no root dir is given, the default path comes from context.getFastPath, which
        # *might* be relative to the cwd, making it possible to delete unintended files.
        # So this check is here to ensure that if we grab a path from context, it is a
        # proper temp dir.
        # That said, since the TemporaryDirectoryChanger *always* responsible for
        # creating its destination directory, it may always be safe to delete it
        # regardless of location.
        if root is None:
            root = context.getFastPath()
            # ARMIs temp dirs are in an context.APP_DATA directory: validate this is a temp dir.
            if pathlib.Path(context.APP_DATA) not in pathlib.Path(root).parents:
                raise ValueError(
                    "Temporary directory not in a safe location for deletion."
                )

        # make the tmp dir, if necessary
        if not os.path.exists(root):
            try:
                os.makedirs(root)
            except FileExistsError:
                # ignore the obvious race condition
                pass

        # init the important path attributes
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
        pathTools.cleanPath(self.destination)


class ForcedCreationDirectoryChanger(DirectoryChanger):
    """
    Creates the directory tree necessary to reach your desired destination
    """

    def __init__(
        self,
        destination,
        filesToMove=None,
        filesToRetrieve=None,
        dumpOnException=True,
    ):
        if not destination:
            raise ValueError("A destination directory must be provided.")
        DirectoryChanger.__init__(
            self, destination, filesToMove, filesToRetrieve, dumpOnException
        )

    def __enter__(self):
        if not os.path.exists(self.destination):
            runLog.extra(f"Creating destination folder: {self.destination}")
            try:
                os.makedirs(self.destination)
            except OSError as ee:
                # even though we checked exists, this still fails
                # sometimes when multiple MPI nodes try
                # to make the dirs due to I/O delays
                runLog.error(
                    f"Failed to make destination folder: {self.destination}. "
                    f"Exception: {ee}"
                )
        else:
            runLog.extra(f"Destination folder already exists: {self.destination}")
        DirectoryChanger.__enter__(self)

        return self


def directoryChangerFactory():
    if context.MPI_SIZE > 1:
        from .directoryChangersMpi import MpiDirectoryChanger

        return MpiDirectoryChanger
    else:
        return DirectoryChanger
