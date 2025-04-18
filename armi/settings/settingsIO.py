# Copyright 2020 TerraPower, LLC
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

"""This module contains classes and methods for reading and writing
:py:class:`~armi.settings.caseSettings.Settings`, and the contained
:py:class:`~armi.settings.setting.Setting`.
"""
import collections
import datetime
import os
import sys
from typing import Dict, Set, Tuple

import ruamel.yaml.comments
from ruamel.yaml import YAML

from armi import context, runLog
from armi.meta import __version__ as version
from armi.settings.setting import Setting
from armi.utils.customExceptions import (
    InvalidSettingsFileError,
    InvalidSettingsStopProcess,
    SettingException,
)

# Constants defining valid output styles
WRITE_SHORT = "short"
WRITE_MEDIUM = "medium"
WRITE_FULL = "full"


class Roots:
    """XML tree root node common strings."""

    CUSTOM = "settings"
    VERSION = "version"


class SettingRenamer:
    """
    Utility class to help with setting rename migrations.

    This class stores a cache of renaming maps, derived from the ``Setting.oldNames`` values of the
    passed ``settings``. Expired renames are retained, so that meaningful warning messages can be
    generated if one attempts to use one of them. The renaming logic follows the rules described in
    :py:meth:`renameSetting`.
    """

    def __init__(self, settings: Dict[str, Setting]):
        self._currentNames: Set[str] = set()
        self._activeRenames: Dict[str, str] = dict()
        self._expiredRenames: Set[Tuple[str, str, datetime.date]] = set()

        today = datetime.date.today()

        for name, s in settings.items():
            self._currentNames.add(name)
            for oldName, expiry in s.oldNames:
                if expiry is not None:
                    expired = expiry <= today
                else:
                    expired = False
                if expired:
                    self._expiredRenames.add((oldName, name, expiry))
                else:
                    if oldName in self._activeRenames:
                        raise SettingException(
                            "The setting rename from {0}->{1} collides with another "
                            "rename {0}->{2}".format(
                                oldName, name, self._activeRenames[oldName]
                            )
                        )
                    self._activeRenames[oldName] = name

    def renameSetting(self, name) -> Tuple[str, bool]:
        """
        Attempt to rename a candidate setting.

        Renaming follows these rules:
         - If the ``name`` corresponds to a current setting name, do not attempt to rename it.
         - If the ``name`` does not correspond to a current setting name, but is one of the active
           renames, return the corresponding active rename.
         - If the ``name`` does not correspond to a current setting name, but is one of the expired
           renames, produce a warning and do not rename it.

        Parameters
        ----------
        name : str
            The candidate setting name to potentially rename.

        Returns
        -------
        name : str
            The potentially-renamed setting
        renamed : bool
            Whether the setting was actually renamed
        """
        if name in self._currentNames:
            return name, False

        activeRename = self._activeRenames.get(name, None)
        if activeRename is not None:
            runLog.warning(f"Invalid setting {name} found. Renaming to {activeRename}.")
            return activeRename, True

        expiredCandidates = {
            val[1]: val[2] for val in self._expiredRenames if val[0] == name
        }

        if expiredCandidates:
            msg = "\n".join(
                [
                    "   {}: {}".format(expiredRename, date)
                    for expiredRename, date in expiredCandidates.items()
                ]
            )
            runLog.warning(
                f"Encountered an invalid setting `{name}`. There are expired renames to newer "
                f"setting names:\n{msg}"
            )

        return name, False


class SettingsReader:
    """Abstract class for processing settings files.

    .. impl:: The setting use a human-readable, plain text file as input.
        :id: I_ARMI_SETTINGS_IO_TXT
        :implements: R_ARMI_SETTINGS_IO_TXT

        ARMI uses the YAML standard for settings files. ARMI uses industry-standard ``ruamel.yaml``
        Python library to read these files. ARMI does not bend or change the YAML file format
        standard in any way.

    Parameters
    ----------
    cs : Settings
        The settings object to read into
    """

    def __init__(self, cs):
        self.cs = cs
        self.inputPath = "<stream>"
        self.invalidSettings = set()
        self.settingsAlreadyRead = set()
        self._renamer = SettingRenamer(dict(self.cs.items()))

        # The input version will be overwritten if explicitly stated in input file. Otherwise, it's
        # assumed to precede the version inclusion change and should be treated as alright.
        self.inputVersion = version
        self.liveVersion = version

    def __getitem__(self, key):
        return self.cs[key]

    def __getattr__(self, attr):
        return getattr(self.cs, attr)

    def __repr__(self):
        return f"<{self.__class__.__name__} {self.inputPath}>"

    def readFromFile(self, path, handleInvalids=True):
        """Load file and read it."""
        with open(path, "r") as f:
            ext = os.path.splitext(path)[1].lower()
            assert ext.lower() in (".yaml", ".yml"), f"{ext} is the wrong extension"
            self.inputPath = path
            try:
                self.readFromStream(f, handleInvalids)
            except Exception as ee:
                raise InvalidSettingsFileError(path, str(ee))

    def readFromStream(self, stream, handleInvalids=True):
        """Read from a file-like stream."""
        self._readYaml(stream)
        if handleInvalids:
            self._checkInvalidSettings()

    def _readYaml(self, stream):
        """Read settings from a YAML stream."""
        from armi.physics.thermalHydraulics import const  # avoid circular import
        from armi.settings.fwSettings.globalSettings import CONF_VERSIONS

        yaml = YAML(typ="rt")
        yaml.allow_duplicate_keys = False
        tree = yaml.load(stream)
        if "settings" not in tree:
            raise InvalidSettingsFileError(
                self.inputPath,
                "Missing the `settings:` header required in YAML settings",
            )

        if const.ORIFICE_SETTING_ZONE_MAP in tree:
            raise InvalidSettingsFileError(
                self.inputPath, "Appears to be an orifice_settings file"
            )

        caseSettings = tree[Roots.CUSTOM]
        setts = tree["settings"]
        if CONF_VERSIONS in setts and "armi" in setts[CONF_VERSIONS]:
            self.inputVersion = setts[CONF_VERSIONS]["armi"]
        else:
            runLog.warning(
                "Versions setting section not found. Continuing with uncontrolled versions."
            )
            self.inputVersion = "uncontrolled"

        for settingName, settingVal in caseSettings.items():
            self._applySettings(settingName, settingVal)

    def _checkInvalidSettings(self):
        if not self.invalidSettings:
            return
        try:
            invalidNames = "\n\t".join(self.invalidSettings)
            proceed = prompt(
                "Found {} invalid settings in {}.\n\n {} \n\t".format(
                    len(self.invalidSettings), self.inputPath, invalidNames
                ),
                "Invalid settings will be ignored. Continue running the case?",
                "YES_NO",
            )
        except RunLogPromptUnresolvable:
            # proceed with invalid settings (they'll be ignored).
            proceed = True
        if not proceed:
            raise InvalidSettingsStopProcess(self)
        else:
            runLog.warning(f"Ignoring invalid settings: {invalidNames}")

    def _applySettings(self, name, val):
        """Add a setting, if it is valid. Capture invalid settings."""
        _nameToSet, _wasRenamed = self._renamer.renameSetting(name)

        if name not in self.cs:
            self.invalidSettings.add(name)
        else:
            # apply validations
            _settingObj = self.cs.getSetting(name)

            # The val is automatically coerced into the expected type when set using either the
            # default or user-defined schema
            self.cs[name] = val


class SettingsWriter:
    """Writes settings out to files.

    This can write in three styles:

    short
        setting values that are not their defaults only
    medium
        preserves all settings originally in file even if they match the default value
    full
        all setting values regardless of default status
    """

    def __init__(self, settings_instance, style="short", settingsSetByUser=[]):
        self.cs = settings_instance
        self.style = style
        if style not in {WRITE_SHORT, WRITE_MEDIUM, WRITE_FULL}:
            raise ValueError(f"Invalid supplied setting writing style {style}")
        # The writer should know about the old settings it is overwriting, but only sometimes (when
        # the style is medium)
        self.settingsSetByUser = settingsSetByUser

    @staticmethod
    def _getTag():
        tag, _attrib = Roots.CUSTOM, {Roots.VERSION: version}
        return tag

    def writeYaml(self, stream):
        """Write settings to YAML file."""
        settingData = self._getSettingDataToWrite()
        settingData = self._preprocessYaml(settingData)
        yaml = YAML()
        yaml.default_flow_style = False
        yaml.indent(mapping=2, sequence=4, offset=2)
        yaml.dump(settingData, stream)

    def _preprocessYaml(self, settingData):
        """
        Clean up the dict before dumping to YAML.

        If it has just a value attrib it flattens it for brevity.
        """
        from armi.settings.fwSettings.globalSettings import CONF_VERSIONS

        yamlData = {}
        cleanedData = collections.OrderedDict()
        for settingObj, settingDatum in settingData.items():
            if "value" in settingDatum and len(settingDatum) == 1:
                # ok to flatten
                cleanedData[settingObj.name] = settingObj.dump()
            else:
                cleanedData[settingObj.name] = settingDatum

        # add ARMI version to the settings YAML
        if CONF_VERSIONS not in cleanedData:
            cleanedData[CONF_VERSIONS] = {}
        cleanedData[CONF_VERSIONS]["armi"] = version

        # this gets rid of a !!omap associated with ordered dicts
        tag = self._getTag()
        yamlData.update({tag: ruamel.yaml.comments.CommentedMap(cleanedData)})
        return yamlData

    def _getSettingDataToWrite(self):
        """
        Make an ordered dict with all settings slated for being written.

        This is general so it can be dumped to whatever file format.
        """
        settingData = collections.OrderedDict()
        for settingName, settingObject in iter(
            sorted(self.cs.items(), key=lambda name: name[0].lower())
        ):
            if self.style == WRITE_SHORT and not settingObject.offDefault:
                continue

            if (
                self.style == WRITE_MEDIUM
                and not settingObject.offDefault
                and settingName not in self.settingsSetByUser
            ):
                continue

            attribs = settingObject.getCustomAttributes().items()
            settingDatum = {}
            for (attribName, attribValue) in attribs:
                if isinstance(attribValue, type):
                    attribValue = attribValue.__name__
                settingDatum[attribName] = attribValue
            settingData[settingObject] = settingDatum

        return settingData


def prompt(statement, question, *options):
    """Prompt the user for some information."""
    if context.CURRENT_MODE == context.Mode.GUI:
        # avoid hard dependency on wx
        import wx

        msg = statement + "\n\n\n" + question
        style = wx.CENTER
        for opt in options:
            style |= getattr(wx, opt)
        dlg = wx.MessageDialog(None, msg, style=style)

        response = dlg.ShowModal()
        dlg.Destroy()
        if response == wx.ID_CANCEL:
            raise RunLogPromptCancel("Manual cancellation of GUI prompt")
        return response in [wx.ID_OK, wx.ID_YES]

    elif context.CURRENT_MODE == context.Mode.INTERACTIVE:
        response = ""
        responses = [
            opt for opt in options if opt in ["YES_NO", "YES", "NO", "CANCEL", "OK"]
        ]

        if "YES_NO" in responses:
            index = responses.index("YES_NO")
            responses[index] = "NO"
            responses.insert(index, "YES")

        if not any(responses):
            raise RuntimeError(f"No suitable responses in {responses}")

        # highly requested shorthand responses
        if "YES" in responses:
            responses.append("Y")
        if "NO" in responses:
            responses.append("N")

        # Use the logger tools to handle user prompts (runLog supports this).
        while response not in responses:
            runLog.LOG.log("prompt", statement)
            runLog.LOG.log("prompt", "{} ({}): ".format(question, ", ".join(responses)))
            response = sys.stdin.readline().strip().upper()

        if response == "CANCEL":
            raise RunLogPromptCancel("Manual cancellation of interactive prompt")

        return response in ["YES", "Y", "OK"]

    else:
        raise RunLogPromptUnresolvable(
            f"Incorrect CURRENT_MODE for prompting user: {context.CURRENT_MODE}"
        )


class RunLogPromptCancel(Exception):
    """An error that occurs when the user submits a cancel on a runLog prompt which allows for cancellation."""

    pass


class RunLogPromptUnresolvable(Exception):
    """
    An error that occurs when the current mode enum in armi.__init__ suggests the user cannot be
    communicated with from the current process.
    """

    pass
