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
This defines a Settings object that acts mostly like a dictionary. It
is meant so that each ARMI run has one-and-only-one Settings object. It records
user settings like the core power level, the input file names, the number of cycles to
run, the run type, the environment setup, and hundreds of other things.

A Settings object can be saved as or loaded from an YAML file. The ARMI GUI is designed to
create this settings file, which is then loaded by an ARMI process on the cluster.
"""
import io
import logging
import os
from copy import copy, deepcopy

from ruamel.yaml import YAML

from armi import context, runLog
from armi.settings import settingsIO
from armi.settings.setting import Setting
from armi.utils import pathTools
from armi.utils.customExceptions import NonexistentSetting

SIMPLE_CYCLES_INPUTS = {
    "availabilityFactor",
    "availabilityFactors",
    "powerFractions",
    "burnSteps",
    "cycleLength",
    "cycleLengths",
}


class Settings:
    """
    A container for run settings, such as case title, power level, and many more.

    .. impl:: Settings are used to define an ARMI run.
        :id: I_ARMI_SETTING0
        :implements: R_ARMI_SETTING

        The Settings object is accessible to most ARMI objects through self.cs
        (for 'case settings'). It acts largely as a dictionary, and setting values
        are accessed by keys.

        The Settings object has a 1-to-1 correspondence with the ARMI settings
        input file. This file may be created by hand or by a GUI.

    Notes
    -----
    While it is possible to modify case settings during the course of a run, this
    is highly discouraged because there will be no record of this happening in your
    results or in the database produced from your run. There is no guarantee that
    doing so will not cause unexpected problems with your calculation.
    """

    defaultCaseTitle = "armi"

    def __init__(self, fName=None):
        """
        Instantiate a Settings object.

        Parameters
        ----------
        fName : str, optional
            Path to a valid yaml settings file that will be loaded
        """
        # if the "loadingFile" is not set, this better be True, or there are no blueprints at all
        self.filelessBP = False

        self._failOnLoad = False
        """This is state information.

        The command line can take settings, which override a value in the current
        settings file; however, if the settings file is listed after a setting value,
        the setting from the settings file will be used rather than the one explicitly
        provided by the user on the command line.  Therefore, _failOnLoad is used to
        prevent this from happening.
        """
        from armi import getApp

        self.path = ""

        app = getApp()
        assert app is not None
        self.__settings = app.getSettings()

        if fName:
            self.loadFromInputFile(fName)

    @property
    def inputDirectory(self):
        """Getter for settings file path."""
        if self.path is None:
            return os.getcwd()
        else:
            return os.path.dirname(self.path)

    @property
    def caseTitle(self):
        """Getter for settings case title.

        .. impl:: Define a case title to go with the settings.
            :id: I_ARMI_SETTINGS_META0
            :implements: R_ARMI_SETTINGS_META

            Every Settings object has a "case title"; a string for users to
            help identify their run. This case title is used in log file
            names, it is printed during a run, it is frequently used to
            name the settings file. It is designed to be an easy-to-use
            and easy-to-understand way to keep track of simulations. The
            general idea here is that the average analyst that is using
            ARMI will run many ARMI-based simulations, and there needs
            to be an easy to identify them all.
        """
        if not self.path:
            return self.defaultCaseTitle
        else:
            return os.path.splitext(os.path.basename(self.path))[0]

    @caseTitle.setter
    def caseTitle(self, value):
        """Setter for the case title."""
        self.path = os.path.join(self.inputDirectory, value + ".yaml")

    @property
    def environmentSettings(self):
        """Getter for environment settings."""
        return [
            setting.name
            for setting in self.__settings.values()
            if setting.isEnvironment
        ]

    def __contains__(self, key):
        return key in self.__settings

    def __repr__(self):
        total = len(self.__settings.keys())
        isAltered = lambda s: 1 if s.value != s.default else 0
        altered = sum([isAltered(setting) for setting in self.__settings.values()])

        return "<{} name:{} total:{} altered:{}>".format(
            self.__class__.__name__, self.caseTitle, total, altered
        )

    def _directAccessOfSettingAllowed(self, key):
        """
        A way to check if specific settings can be grabbed out of the case settings.

        Could be updated with other specific instances as necessary.

        Notes
        -----
        Checking the validity of grabbing specific settings at this point, as is done for the
        SIMPLE_CYCLES_INPUT's, feels a bit intrusive and out of place. In particular, the fact that
        the check is done every time that a setting is reached for, no matter if it is the setting
        in question, is quite clunky. In the future, it would be desirable if the settings system
        were more flexible to control this type of thing at a deeper level.
        """
        if key not in self.__settings:
            return False, NonexistentSetting(key)

        if key in SIMPLE_CYCLES_INPUTS and self.__settings["cycles"].value != []:
            err = ValueError(
                "Cannot grab simple cycles information from the case settings when detailed cycles "
                "information is also entered. In general cycles information should be pulled off "
                "the operator or parsed using the appropriate getter in the utils."
            )

            return False, err

        return True, None

    def __getitem__(self, key):
        settingIsOkayToGrab, err = self._directAccessOfSettingAllowed(key)
        if settingIsOkayToGrab:
            return self.__settings[key].value
        else:
            raise err

    def getSetting(self, key, default=None):
        """
        Return a copy of an actual Setting object, instead of just its value.

        Notes
        -----
        This is used very rarely, try to organize your code to only need a Setting value.
        """
        if key in self.__settings:
            return copy(self.__settings[key])
        elif default is not None:
            return default
        else:
            raise NonexistentSetting(key)

    def __setitem__(self, key, val):
        """
        Notes
        -----
        This potentially allows for invisible settings mutations.
        """
        if key in self.__settings:
            self.__settings[key].setValue(val)
        else:
            raise NonexistentSetting(key)

    def __setstate__(self, state):
        """
        Rebuild schema upon unpickling since schema is unpickleable.

        Pickling happens during mpi broadcasts and also during testing where the test reactor is
        cached.

        See Also
        --------
        armi.settings.setting.Setting.__getstate__ : removes schema
        """
        from armi import getApp

        self.__settings = getApp().getSettings()

        # restore non-setting instance attrs
        for key, val in state.items():
            if key != "_Settings__settings":
                setattr(self, key, val)

        # with schema restored, restore all setting values
        for name, settingState in state["_Settings__settings"].items():
            if name in self.__settings:
                self.__settings[name]._value = settingState.value
            elif isinstance(settingState, Setting):
                self.__settings[name] = copy(settingState)
            else:
                raise NonexistentSetting(name)

    def keys(self):
        return self.__settings.keys()

    def values(self):
        return self.__settings.values()

    def items(self):
        return self.__settings.items()

    def duplicate(self):
        """Return a duplicate copy of this settings object."""
        cs = deepcopy(self)
        cs._failOnLoad = False
        # It's not really protected access since it is a new Settings object. _failOnLoad is set to
        # false, because this new settings object should be independent of the command line
        return cs

    def revertToDefaults(self):
        """Sets every setting back to its default value."""
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
        Read in settings from an input YAML file.

        Passes the reader back out in case you want to know something about how the reading went
        like for knowing if a file contained deprecated settings, etc.
        """
        reader, path = self._prepToRead(fName)
        reader.readFromFile(fName, handleInvalids)
        self._applyReadSettings(path if setPath else None)
        self.registerUserPlugins()

        return reader

    def registerUserPlugins(self):
        """Add any ad-hoc 'user' plugins that are referenced in the settings file."""
        userPlugins = self["userPlugins"]
        if len(userPlugins):
            from armi import getApp

            app = getApp()
            app.registerUserPlugins(userPlugins)

    def _prepToRead(self, fName):
        if self._failOnLoad:
            raise RuntimeError(
                "Cannot load settings file after processing of command line options begins.\nYou "
                "may be able to fix this by reordering the command line arguments, and making sure "
                f"the settings file `{fName}` comes before any modified settings."
            )
        path = pathTools.armiAbsPath(fName)
        return settingsIO.SettingsReader(self), path

    def loadFromString(self, string, handleInvalids=True):
        """Read in settings from a YAML string.

        Passes the reader back out in case you want to know something about how the reading went
        like for knowing if a file contained deprecated settings, etc.
        """
        if self._failOnLoad:
            raise RuntimeError(
                "Cannot load settings after processing of command line options begins.\nYou may be "
                "able to fix this by reordering the command line arguments."
            )

        reader = settingsIO.SettingsReader(self)
        reader.readFromStream(io.StringIO(string), handleInvalids=handleInvalids)

        self.initLogVerbosity()

        return reader

    def _applyReadSettings(self, path=None):
        self.initLogVerbosity()

        if path:
            self.path = path  # can't set this before a chance to fail occurs

    def initLogVerbosity(self):
        """
        Central location to init logging verbosity.

        Notes
        -----
        This means that creating a Settings object sets the global logging level of the entire code
        base.
        """
        if context.MPI_RANK == 0:
            runLog.setVerbosity(self["verbosity"])
        else:
            runLog.setVerbosity(self["branchVerbosity"])

        self.setModuleVerbosities(force=True)

    def writeToYamlFile(self, fName, style="short", fromFile=None):
        """
        Write settings to a yaml file.

        Notes
        -----
        This resets the current CS's path to the newly written absolute path.

        Parameters
        ----------
        fName : str
            the file to write to
        style : str (optional)
            the method of output to be used when creating the file for the current state of settings
            (short, medium, or full)
        fromFile : str (optional)
            if the source file and destination file are different (i.e. for cloning) and the style
            argument is ``medium``, then this arg is used
        """
        self.path = pathTools.armiAbsPath(fName)
        if style == "medium":
            getSettingsPath = (
                self.path if fromFile is None else pathTools.armiAbsPath(fromFile)
            )
            settingsSetByUser = self.getSettingsSetByUser(getSettingsPath)
        else:
            settingsSetByUser = []
        with open(self.path, "w") as stream:
            writer = self.writeToYamlStream(stream, style, settingsSetByUser)

        return writer

    def getSettingsSetByUser(self, fPath):
        """
        Grabs the list of settings in the user-defined input file so that the settings can be
        tracked outside of a Settings object.

        Parameters
        ----------
        fPath : str
            The absolute file path of the settings file

        Returns
        -------
        userSettingsNames : list
            The settings names read in from a yaml settings file
        """
        # We do not want to load these as settings, but just grab the dictionary straight from the
        # settings file to know which settings are user-defined.
        with open(fPath, "r") as stream:
            yaml = YAML()
            yaml.allow_duplicate_keys = False
            tree = yaml.load(stream)
            userSettings = tree[settingsIO.Roots.CUSTOM]

        userSettingsNames = list(userSettings.keys())
        return userSettingsNames

    def writeToYamlStream(self, stream, style="short", settingsSetByUser=[]):
        """
        Write settings in yaml format to an arbitrary stream.

        Parameters
        ----------
        stream : file object
            Writable file stream
        style : str (optional)
            Writing style for settings file. Can be short, medium, or full.
        settingsSetByUser : list
            List of settings names in user-defined settings file

        Returns
        -------
        writer : SettingsWriter
        """
        writer = settingsIO.SettingsWriter(
            self, style=style, settingsSetByUser=settingsSetByUser
        )
        writer.writeYaml(stream)
        return writer

    def updateEnvironmentSettingsFrom(self, otherCs):
        """Updates the environment settings in this object based on some other cs (from the GUI,
        most likely).

        Parameters
        ----------
        otherCs : Settings
            A cs object that environment settings will be inherited from.

        This enables users to run tests with their environment rather than the reference environment
        """
        for replacement in self.environmentSettings:
            self[replacement] = otherCs[replacement]

    def modified(self, caseTitle=None, newSettings=None):
        """Return a new Settings object containing the provided modifications."""
        settings = self.duplicate()

        if caseTitle:
            settings.caseTitle = caseTitle

        if newSettings:
            for key, val in newSettings.items():
                if isinstance(val, Setting):
                    settings.__settings[key] = copy(val)
                elif key in settings.__settings:
                    settings.__settings[key].setValue(val)
                else:
                    settings.__settings[key] = Setting(
                        key, val, description="Description from cs.modified()"
                    )

        return settings

    def setModuleVerbosities(self, force=False):
        """Attempt to grab the module-level logger verbosities from the settings file,
        and then set their log levels (verbosities).

        Parameters
        ----------
        force : bool, optional
            If force is False, don't overwrite the log verbosities if the logger already exists.
            IF this needs to be used mid-run, force=False is safer.

        Notes
        -----
        This method is only meant to be called once per run.
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
