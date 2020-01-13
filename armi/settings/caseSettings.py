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
import os
import sys
import copy
import collections

import armi
from armi import runLog
from armi.localization import exceptions
from armi.settings import fwSettings
from armi.settings import setting
from armi.settings import settingsIO
from armi.utils import pathTools
from armi.settings import setting2


class Settings:
    """
    A container for global settings, such as case title, power level, and many run options.

    It is accessible to most ARMI objects through self.cs (for 'Case Settings').
    It acts largely as a dictionary, and setting values are accessed by keys.

    The settings object has a 1-to-1 correspondence with the ARMI settings input file.
    This file may be created by hand or by the GUI in submitter.py.
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

        self.settings = {}
        self.loadAllDefaults()
        self._loadPluginSettings()
        if not Settings.instance:
            Settings.instance = self
        self._backedup = {}

        if fName:
            self.loadFromInputFile(fName)

    def _loadPluginSettings(self):
        # The optionsCache stores options that may have come from a plugin before the
        # setting to which they apply. Whenever a new setting is added, we check to see
        # if there are any options in the cache, popping them out and adding them to the
        # setting.  If all plugins' settings have been processed and the cache is not
        # empty, that's an error, because a plugin must have provided options to a
        # setting that doesn't exist.
        optionsCache = collections.defaultdict(list)
        defaultsCache = {}

        pm = armi.getPluginManager()
        if pm is None:
            runLog.warning("no plugin manager defined when settings were made")
            return

        for pluginSettings in pm.hook.defineSettings():
            for pluginSetting in pluginSettings:
                if isinstance(pluginSetting, setting2.Setting):
                    name = pluginSetting.name
                    if name in self.settings:
                        raise ValueError(
                            f"The setting {pluginSetting.name} "
                            "already exists and cannot be redefined."
                        )
                    self.settings[name] = pluginSetting
                    # handle when new setting has modifier in the cache (modifier loaded first)
                    if name in optionsCache:
                        self.settings[name].addOptions(optionsCache.pop(name))
                    if name in defaultsCache:
                        self.settings[name].changeDefault(defaultsCache.pop(name))
                elif isinstance(pluginSetting, setting2.Option):
                    if pluginSetting.settingName in self.settings:
                        # modifier loaded after setting, so just apply it (no cache needed)
                        self.settings[pluginSetting.settingName].addOption(
                            pluginSetting
                        )
                    else:
                        # no setting yet, cache it and apply when it arrives
                        optionsCache[pluginSetting.settingName].append(pluginSetting)
                elif isinstance(pluginSetting, setting2.Default):
                    if pluginSetting.settingName in self.settings:
                        # modifier loaded after setting, so just apply it (no cache needed)
                        self.settings[pluginSetting.settingName].changeDefault(
                            pluginSetting
                        )
                    else:
                        # no setting yet, cache it and apply when it arrives
                        defaultsCache[pluginSetting.settingName] = pluginSetting
                else:
                    raise TypeError(
                        f"Invalid setting definition found: {pluginSetting}"
                    )

        if optionsCache:
            raise ValueError(
                "The following options were provided for settings that do "
                "not exist. Make sure that the set of active plugins is "
                "consistent.\n{}".format(optionsCache)
            )

        if defaultsCache:
            raise ValueError(
                "The following defaults were provided for settings that do "
                "not exist. Make sure that the set of active plugins is "
                "consistent.\n{}".format(defaultsCache)
            )

    @property
    def inputDirectory(self):
        if self.path is None:
            return os.getcwd()
        else:
            return os.path.dirname(self.path)

    @property
    def caseTitle(self):
        if self.path is None:
            return self.defaultCaseTitle
        else:
            return os.path.splitext(os.path.basename(self.path))[0]

    @caseTitle.setter
    def caseTitle(self, value):
        self.path = os.path.join(self.inputDirectory, value + ".yaml")

    @property
    def environmentSettings(self):
        return [
            setting.name for setting in self.settings.values() if setting.isEnvironment
        ]

    def __repr__(self):
        total = len(self.settings.keys())
        isAltered = lambda setting: 1 if setting.value != setting.default else 0
        altered = sum([isAltered(setting) for setting in self.settings.values()])

        return "<{} name:{} total:{} altered:{}>".format(
            self.__class__.__name__, self.caseTitle, total, altered
        )

    def __getitem__(self, key):
        if key in self.settings:
            return self.settings[key].value
        else:
            raise exceptions.NonexistentSetting(key)

    def __setitem__(self, key, val):
        if key in self.settings:
            self.settings[key].setValue(val)
        else:
            raise exceptions.NonexistentSetting(key)

    def __setstate__(self, state):
        """
        Rebuild schema upon unpickling since schema is unpickleable.

        Pickling happens during mpi broadcasts and also
        during testing where the test reactor is cached.

        See Also
        --------
        armi.settings.setting2.Setting.__getstate__ : removes schema
        """
        self.settings = {}
        self.loadAllDefaults()
        self._loadPluginSettings()

        # restore non-setting instance attrs
        for key, val in state.items():
            if key != "settings":
                setattr(self, key, val)
        # with schema restored, restore all setting values
        for name, settingState in state["settings"].items():
            if isinstance(settingState, setting.Setting):
                # old style. fully pickleable, restore entire setting object
                self.settings[name] = settingState
            else:
                # new style, just restore value from dict.
                # sorry about this being ugly.
                self.settings[
                    name
                ]._value = settingState.value  # pylint: disable=protected-access

    def keys(self):
        return self.settings.keys()

    def update(self, values):
        for key, val in values.items():
            self[key] = val

    def clear(self):
        self.settings.clear()

    def duplicate(self):
        cs = copy.deepcopy(self)
        cs._failOnLoad = False  # pylint: disable=protected-access
        # it's not really protected access since it is a new Settings object.
        # _failOnLoad is set to false, because this new settings object should be independent of the command line
        return cs

    def revertToDefaults(self):
        r"""Sets every setting back to its default value"""
        for setting in self.settings.values():
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
            raise exceptions.StateError(
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
            raise exceptions.StateError(
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

        if armi.MPI_RANK == 0:
            runLog.setVerbosity(self["verbosity"])
        else:
            runLog.setVerbosity(self["branchVerbosity"])

        return reader

    def loadAllDefaults(self):
        r"""Initializes all setting objects from the default files

        Crawls the res folder for all XML files, tries to load them as settings files
        and sets all default settings from there. (if there is a duplicate setting it
        will throw an error)

        Also grabs explicitly-defined Settings objects for framework settings.

        The formatting of the file name is important as it clues it in to what's valid.

        """
        for dirname, _dirnames, filenames in os.walk(armi.RES):
            for filename in filenames:
                if filename.lower().endswith("settings.xml"):
                    reader = settingsIO.SettingsDefinitionReader(self)
                    reader.readFromFile(os.path.join(dirname, filename))

        for fwSetting in fwSettings.getFrameworkSettings():
            self.settings[fwSetting.name] = fwSetting

    def _applyReadSettings(self, path=None):
        if armi.MPI_RANK == 0:
            runLog.setVerbosity(self["verbosity"])
        else:
            runLog.setVerbosity(self["branchVerbosity"])

        if path:
            self.path = path  # can't set this before a chance to fail occurs

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

    def setSettingsReport(self):
        """Puts settings into the report manager"""
        from armi.bookkeeping import report

        report.setData("caseTitle", self.caseTitle, report.RUN_META)
        report.setData(
            "outputFileExtension", self["outputFileExtension"], report.RUN_META
        )

        report.setData(
            "Total Core Power", "%8.5E MWt" % (self["power"] / 1.0e6), report.RUN_META
        )
        if not self["cycleLengths"]:
            report.setData(
                "Cycle Length", "%8.5f days" % self["cycleLength"], report.RUN_META
            )
        report.setData(
            "BU Groups", str(self["buGroups"]), report.RUN_META
        )  # str to keep the list together in the report

        for key in [
            "nCycles",
            "burnSteps",
            "skipCycles",
            "cycleLength",
            "numProcessors",
        ]:
            report.setData(key, self[key], report.CASE_PARAMETERS)

        for key in self.environmentSettings:
            report.setData(key, self[key], report.RUN_META, [report.ENVIRONMENT])

        for key in ["genXS", "neutronicsKernel"]:
            report.setData(key, self[key], report.CASE_CONTROLS, [report.ENVIRONMENT])

        for key in ["boundaries", "neutronicsKernel", "neutronicsType", "fpModel"]:
            report.setData(key, self[key], report.RUN_META, [report.NEUTRONICS])

        for key in ["reloadDBName", "startCycle", "startNode"]:
            report.setData(key, self[key], report.SNAPSHOT)

        for key in ["power", "Tin", "Tout"]:
            report.setData(key, self[key], report.REACTOR_PARAMS)

        for key in ["buGroups"]:
            report.setData(key, self[key], report.BURNUP_GROUPS)

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

    def temporarilySet(self, settingName, temporaryValue):
        """
        Change a setting that you will restore later.

        Useful to change settings before doing a certain run and then reverting them

        See Also
        --------
        unsetTemporarySettings : reverts this
        """
        runLog.debug(
            "Temporarily changing {} from {} to {}".format(
                settingName, self[settingName], temporaryValue
            )
        )
        self._backedup[settingName] = self[settingName]
        self[settingName] = temporaryValue

    def unsetTemporarySettings(self):
        for settingName, origValue in self._backedup.items():
            runLog.debug(
                "Reverting {} from {} back to its original value of {}".format(
                    settingName, self[settingName], origValue
                )
            )
            self[settingName] = origValue
