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

r"""
This defines a Settings object that acts mostly like a dictionary. It
is meant to be treated mostly like a singleton, where each custom ARMI
object has access to it. It contains global user settings like the core
power level, the input file names, the number of cycles to run, the run type,
the environment setup, and hundreds of other things.

A settings object can be saved as or loaded from an XML file. The ARMI GUI is designed to
create this settings file, which is then loaded by an ARMI process on the cluster.

A master case settings is created as ``masterCs``

"""
import io
import logging
import os
from copy import deepcopy

import armi
from armi import runLog
from armi.settings import settingsIO
from armi.settings.setting import Setting
from armi.utils import pathTools
from armi.utils.customExceptions import NonexistentSetting

DEP_WARNING = "Deprecation Warning: Settings will not be mutable mid-run: {}"


class Settings:
    """
    A container for global settings, such as case title, power level, and many run options.

    It is accessible to most ARMI objects through self.cs (for 'Case Settings').
    It acts largely as a dictionary, and setting values are accessed by keys.

    The settings object has a 1-to-1 correspondence with the ARMI settings input file.
    This file may be created by hand or by the GUI in submitter.py.

    NOTE: The actual settings in any instance of this class are immutable.
    """

    # Settings is not a singleton, but there is a globally
    # shared instance considered most germane to the current run
    instance = None

    defaultCaseTitle = "armi"

    def __init__(self, fName=None):
        """
        Instantiate a settings object

        Parameters
        ----------
        fName : str, optional
            Path to a valid yaml settings file that will be loaded
        """

        self._failOnLoad = False
        """This is state information.

        The command line can take settings, which override a value in the current
        settings file; however, if the settings file is listed after a setting value,
        the setting from the settings file will be used rather than the one explicitly
        provided by the user on the command line.  Therefore, _failOnLoad is used to
        prevent this from happening.
        """
        self.path = ""

        app = armi.getApp()
        assert app is not None
        self.__settings = app.getSettings()
        if not Settings.instance:
            Settings.instance = self

        if fName:
            self.loadFromInputFile(fName)

    @property
    def inputDirectory(self):
        """getter for settings file path"""
        if self.path is None:
            return os.getcwd()
        else:
            return os.path.dirname(self.path)

    @property
    def caseTitle(self):
        """getter for settings case title"""
        if not self.path:
            return self.defaultCaseTitle
        else:
            return os.path.splitext(os.path.basename(self.path))[0]

    @caseTitle.setter
    def caseTitle(self, value):
        """setter for the case title"""
        self.path = os.path.join(self.inputDirectory, value + ".yaml")

    @property
    def environmentSettings(self):
        """getter for environment settings"""
        return [
            setting.name
            for setting in self.__settings.values()
            if setting.isEnvironment
        ]

    def __contains__(self, key):
        return key in self.__settings

    def __repr__(self):
        total = len(self.__settings.keys())
        isAltered = lambda setting: 1 if setting.value != setting.default else 0
        altered = sum([isAltered(setting) for setting in self.__settings.values()])

        return "<{} name:{} total:{} altered:{}>".format(
            self.__class__.__name__, self.caseTitle, total, altered
        )

    def __getitem__(self, key):
        if key in self.__settings:
            return self.__settings[key].value
        else:
            raise NonexistentSetting(key)

    def getSetting(self, key):
        """
        Return a copy of an actual Setting object, instead of just its value.

        NOTE: This is used very rarely, try to organize your code to only need a Setting value.
        """
        if key in self.__settings:
            return deepcopy(self.__settings[key])
        else:
            raise NonexistentSetting(key)

    def __setitem__(self, key, val):
        # TODO: This potentially allows for invisible settings mutations and should be removed.
        if key in self.__settings:
            self.__settings[key].setValue(val)
        else:
            raise NonexistentSetting(key)

    def __setstate__(self, state):
        """
        Rebuild schema upon unpickling since schema is unpickleable.

        Pickling happens during mpi broadcasts and also
        during testing where the test reactor is cached.

        See Also
        --------
        armi.settings.setting.Setting.__getstate__ : removes schema
        """
        self.__settings = armi.getApp().getSettings()

        # restore non-setting instance attrs
        for key, val in state.items():
            if key != "_Settings__settings":
                setattr(self, key, val)

        # with schema restored, restore all setting values
        for name, settingState in state["_Settings__settings"].items():
            # pylint: disable=protected-access
            self.__settings[name]._value = settingState.value

    def keys(self):
        return self.__settings.keys()

    def values(self):
        return self.__settings.values()

    def items(self):
        return self.__settings.items()

    def duplicate(self):
        """return a duplicate copy of this settings object"""
        cs = deepcopy(self)
        cs._failOnLoad = False  # pylint: disable=protected-access
        # it's not really protected access since it is a new Settings object.
        # _failOnLoad is set to false, because this new settings object should be independent of the command line
        return cs

    def revertToDefaults(self):
        """Sets every setting back to its default value"""
        for setting in self.__settings.values():
            setting.revertToDefault()

    def failOnLoad(self):
        """This method is used to force loading a file to fail.

        After command line processing of settings has begun, the settings should be fully defined.
        If the settings are loaded
        """
        self._failOnLoad = True

    def loadFromInputFile(self, fName, handleInvalids=True, setPath=True):
        """
        Read in settings from an input file.

        Supports YAML and two XML formats, the newer (tags are the key, etc.)
        and the former (tags are the type, etc.). If the extension is ``xml``,
        it assumes XML format. Otherwise, YAML is assumed.

        Passes the reader back out in case you want to know something about how the reading went
        like for knowing if a file contained deprecated settings, etc.
        """
        reader, path = self._prepToRead(fName)
        reader.readFromFile(fName, handleInvalids)
        self._applyReadSettings(path if setPath else None)

        return reader

    def _prepToRead(self, fName):
        if self._failOnLoad:
            raise RuntimeError(
                "Cannot load settings file after processing of command "
                "line options begins.\nYou may be able to fix this by "
                "reordering the command line arguments, and making sure "
                "the settings file `{}` comes before any modified settings.".format(
                    fName
                )
            )
        path = pathTools.armiAbsPath(fName)
        return settingsIO.SettingsReader(self), path

    def loadFromString(self, string, handleInvalids=True):
        """Read in settings from a string.

        Supports two xml formats, the newer (tags are the key, etc.) and the former
        (tags are the type, etc.)

        Passes the reader back out in case you want to know something about how the
        reading went like for knowing if a file contained deprecated settings, etc.
        """
        if self._failOnLoad:
            raise RuntimeError(
                "Cannot load settings after processing of command "
                "line options begins.\nYou may be able to fix this by "
                "reordering the command line arguments."
            )

        reader = settingsIO.SettingsReader(self)
        fmt = reader.SettingsInputFormat.YAML
        if string.strip()[0] == "<":
            fmt = reader.SettingsInputFormat.XML
        reader.readFromStream(
            io.StringIO(string), handleInvalids=handleInvalids, fmt=fmt
        )

        self.initLogVerbosity()

        return reader

    def _applyReadSettings(self, path=None):
        self.initLogVerbosity()

        if path:
            self.path = path  # can't set this before a chance to fail occurs

    # TODO: At some point, much of the logging init will be moved to context, including this.
    def initLogVerbosity(self):
        """Central location to init logging verbosity"""
        if armi.MPI_RANK == 0:
            runLog.setVerbosity(self["verbosity"])
        else:
            runLog.setVerbosity(self["branchVerbosity"])

        self.setModuleVerbosities(force=True)

    def writeToXMLFile(self, fName, style="short"):
        """Write out settings to an xml file

        Parameters
        ----------
        fName : str
            the file to write to
        style : str
            the method of XML output to be used when creating the xml file for
            the current state of settings
        """
        self.path = pathTools.armiAbsPath(fName)
        writer = settingsIO.SettingsWriter(self, style=style)
        with open(self.path, "w") as stream:
            writer.writeXml(stream)
        return writer

    def writeToYamlFile(self, fName, style="short"):
        """
        Write settings to a yaml file.

        Notes
        -----
        This resets the current CS's path to the newly written path.

        Parameters
        ----------
        fName : str
            the file to write to
        style : str
            the method of output to be used when creating the file for
            the current state of settings
        """
        self.path = pathTools.armiAbsPath(fName)
        with open(self.path, "w") as stream:
            writer = self.writeToYamlStream(stream, style)
        return writer

    def writeToYamlStream(self, stream, style="short"):
        """Write settings in yaml format to an arbitrary stream."""
        writer = settingsIO.SettingsWriter(self, style=style)
        writer.writeYaml(stream)
        return writer

    def updateEnvironmentSettingsFrom(self, otherCs):
        r"""Updates the environment settings in this object based on some other cs
        (from the GUI, most likely)

        Parameters
        ----------
        otherCs : Settings object
            A cs object that environment settings will be inherited from.

        This enables users to run tests with their environment rather than the reference environment
        """
        for replacement in self.environmentSettings:
            self[replacement] = otherCs[replacement]

    def modified(self, caseTitle=None, newSettings=None):
        """Return a new Settings object containing the provided modifications."""
        # pylint: disable=protected-access
        settings = self.duplicate()

        if caseTitle:
            settings.caseTitle = caseTitle

        if newSettings:
            for key, val in newSettings.items():
                if isinstance(val, Setting):
                    settings.__settings[key] = val
                elif key in settings.__settings:
                    settings.__settings[key].setValue(val)
                else:
                    settings.__settings[key] = Setting(key, val)

        return settings

    def setModuleVerbosities(self, force=False):
        """Attempt to grab the module-level logger verbosities from the settings file,
        and then set their log levels (verbosities).

        NOTE: This method is only meant to be called once per run.

        Parameters
        ----------
        force : bool, optional
            If force is False, don't overwrite the log verbosities if the logger already exists.
            IF this needs to be used mid-run, force=False is safer.
        """
        # try to get the setting dict
        verbs = self["moduleVerbosity"]

        # set, but don't use, the module-level loggers
        for mName, mLvl in verbs.items():
            # by default, we init module-level logging, not change it mid-run
            if force or mName not in logging.Logger.manager.loggerDict:
                # cast verbosity to integer
                lvl = int(mLvl) if mLvl.isnumeric() else runLog.LOG.logLevels[mLvl][0]

                log = logging.getLogger(mName)
                log.setVerbosity(lvl)
