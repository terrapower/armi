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
Base migration classes.

A classic migration takes a file name, read the files, migrates the data, and re-writes the file. Some migrations need
to happen live on a stream. For example, if an old/invalid input file is being read in from an old database. The
migration class defined here chooses this behavior based on whether the ``stream`` or ``path`` variables are given in
the constructor.
"""

import abc
import io
import os
import shutil

from armi import runLog
from armi.settings import caseSettings
from armi.settings.settingsValidation import versionToNumber


class Migration:
    """Generic migration.

    To implement a concrete Migration, you must implement the ``_applyToStream`` method. You must also define the
    abstract properties ``fromVersion`` and ``toVersion``. These are the ARMI versions you are migrating from and to.
    The ``toVersion`` must be higher than the ``fromVersion``.
    """

    __metaclass__ = abc.ABCMeta

    def __init__(self, stream=None, path=None):
        if not (bool(stream) ^ bool(path)):  # XOR
            raise RuntimeError("Only a stream or a path may be used as migration input. Choose exactly one.")
        elif versionToNumber(self.toVersion) <= versionToNumber(self.fromVersion):
            raise ValueError(f"{self.toVersion} is not higher than {self.fromVersion}.")

        self.stream = stream
        self.path = path

    @abc.abstractproperty
    def fromVersion(self):
        """ARMI version string, must be smaller than toVersion."""
        pass

    @abc.abstractproperty
    def toVersion(self):
        """ARMI version string, must be larger than fromVersion."""
        pass

    @abc.abstractmethod
    def _applyToStream(self):
        """Add actual migration code here in a subclass."""
        pass

    def __repr__(self):
        return f"<Migration from {self.fromVersion}: {self.__doc__[:40]}..."

    def apply(self, version: str = None):
        """
        Apply migration.

        This is generally called from a subclass.

        Parameters
        ----------
        version : str
            Optional DB version string, for example: 1.2.3
        """
        skip = False
        # Compare self.toVersion to the version of the DB.
        if version is not None and version != "uncontrolled":
            if versionToNumber(version) >= versionToNumber(self.toVersion):
                # this migration is not necessary, because the DB is newer than that.
                skip = True

        if self.path:
            self._loadStreamFromPath()

        if not skip:
            runLog.info(f"Applying {self}")
            newStream = self._applyToStream()

            if self.path:
                self._backupOriginal()
                self._writeNewFile(newStream)
        else:
            newStream = io.StringIO(self.stream.read())

        return newStream

    def _loadStreamFromPath(self):
        """Common stream-loading code. Must be extended to actually load.

        The operative subclasses implementing this method are below.
        """
        if not os.path.exists(self.path):
            raise ValueError(f"File {self.path} does not exist")

    def _backupOriginal(self):
        # must be called after _loadStreamFromPath
        self.stream.close()
        shutil.move(self.path, self.path + "-migrated")

    def _writeNewFile(self, newStream):
        i = 0
        while os.path.exists(self.path):
            # Do not overwrite files (they could be blueprints).
            name, ext = os.path.splitext(self.path)
            self.path = name + f"{i}" + ext
            i += 1

        with open(self.path, "w") as f:
            f.write(newStream.read())


class BlueprintsMigration(Migration):
    """Migration for blueprints input."""

    def _loadStreamFromPath(self):
        from armi.physics.neutronics.settings import CONF_LOADING_FILE

        super()._loadStreamFromPath()
        cs = caseSettings.Settings(fName=self.path)
        self.path = cs[CONF_LOADING_FILE]
        self.stream = open(self.path)


class SettingsMigration(Migration):
    """Migration for settings input."""

    def _loadStreamFromPath(self):
        super()._loadStreamFromPath()
        self.stream = open(self.path)


class DatabaseMigration(Migration):
    """Migration for db output."""

    pass
