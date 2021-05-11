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
import ast
import collections
import datetime
import enum
import os
import re
from typing import Dict, Tuple, List, Set, Optional
import warnings
import xml.etree.ElementTree as ET

from ruamel.yaml import YAML
import ruamel.yaml.comments

import armi
from armi import runLog
from armi.localization import exceptions
from armi.settings.setting import Setting
from armi.settings import settingsRules
from armi.reactor import geometry
from armi.reactor import systemLayoutInput


class Roots:
    """XML tree root node common strings"""

    CUSTOM = "settings"
    VERSION = "version"


class SettingRenamer:
    """
    Utility class to help with setting rename migrations.

    This class stores a cache of renaming maps, derived from the ``Setting.oldNames``
    values of the passed ``settings``. Expired renames are retained, so that meaningful
    warning messages can be generated if one attempts to use one of them. The renaming
    logic follows the rules described in :py:meth:`renameSetting`.
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
                        raise exceptions.SettingException(
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
         - If the ``name`` corresponds to a current setting name, do not attempt to
           rename it.
         - If the ``name`` does not correspond to a current setting name, but is one of
           the active renames, return the corresponding active rename.
         - If the ``name`` does not correspond to a current setting name, but is one of
           the expired renames, produce a warning and do not rename it.

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
            runLog.warning(
                "Invalid setting {} found. Renaming to {}.".format(name, activeRename)
            )
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
                "Encountered an invalid setting `{}`. There are expired "
                "renames to newer setting names:\n{}".format(name, msg)
            )

        return name, False


class SettingsReader:
    """Abstract class for processing settings files.

    Parameters
    ----------
    cs : CaseSettings
        The settings object to read into
    """

    class SettingsInputFormat(enum.Enum):
        XML = enum.auto()
        YAML = enum.auto()

        @classmethod
        def fromExt(cls, ext):
            return {".xml": cls.XML, ".yaml": cls.YAML}[ext]

    def __init__(self, cs):
        self.cs = cs
        self.rootTag = Roots.CUSTOM
        self.format = self.SettingsInputFormat.YAML
        self.inputPath = "<stream>"

        self.invalidSettings = set()
        self.settingsAlreadyRead = set()
        self.liveVersion = armi.__version__
        self.inputVersion = armi.__version__

        self._renamer = SettingRenamer(self.cs.settings)

        # the input version will be overwritten if explicitly stated in input file.
        # otherwise, it's assumed to precede the version inclusion change and should be
        # treated as alright

    def __getitem__(self, key):
        return self.cs[key]

    def __getattr__(self, attr):
        return getattr(self.cs, attr)

    def __repr__(self):
        return "<{} {}>".format(self.__class__.__name__, self.inputPath)

    @property
    def isXmlFormat(self):
        """True if file read is in the old XML format."""
        return self.format == self.SettingsInputFormat.XML

    def readFromFile(self, path, handleInvalids=True):
        """Load file and read it."""

        with open(path, "r") as f:
            # make sure that we can actually open the file before trying to guess its
            # format. This will yield better error messages when things go awry.
            ext = os.path.splitext(path)[1].lower()
            self.format = self.SettingsInputFormat.fromExt(ext)
            self.inputPath = path
            try:
                self.readFromStream(f, handleInvalids, self.format)
            except Exception as ee:
                raise exceptions.InvalidSettingsFileError(path, str(ee))

    def readFromStream(self, stream, handleInvalids=True, fmt=SettingsInputFormat.YAML):
        """Read from a file-like stream."""
        self.format = fmt
        if self.format == self.SettingsInputFormat.YAML:
            try:
                self._readYaml(stream, handleInvalids=handleInvalids)
            except ruamel.yaml.scanner.ScannerError:
                # mediocre way to detect xml vs. yaml at the stream level
                runLog.info(
                    "Could not read stream in YAML format. Attempting XML format."
                )
                self.format = self.SettingsInputFormat.XML
                stream.seek(0)
        if self.format == self.SettingsInputFormat.XML:
            self._readXml(stream, handleInvalids=handleInvalids)

    def _readXml(self, stream, handleInvalids=True):
        """
        Read user settings from XML stream.
        """
        warnings.warn(
            "Loading from XML-format settings files is being deprecated.",
            DeprecationWarning,
        )
        tree = ET.parse(stream)
        settingRoot = tree.getroot()
        if Roots.VERSION in settingRoot.attrib:
            self.inputVersion = settingRoot.attrib[Roots.VERSION]

        if settingRoot.tag != self.rootTag:
            # checks to make sure the right kind of settings XML file
            # is being applied to the right class
            if settingRoot.tag == systemLayoutInput.SystemLayoutInput.ROOT_TAG:
                customMsg = (
                    "\nSettings file appears to be a reactor geometry file. "
                    "Please provide a valid settings file."
                )
            else:
                customMsg = '\nRoot tag "{}" does not match expected value "{}"'.format(
                    settingRoot.tag, self.rootTag
                )
            raise exceptions.InvalidSettingsFileError(
                self.inputPath, customMsgEnd=customMsg
            )

        for settingElement in list(settingRoot):
            self._interpretXmlSetting(settingElement)

        if handleInvalids:
            self._checkInvalidSettings()

    def _readYaml(self, stream, handleInvalids=True):
        """
        Read settings from a YAML stream.

        Notes
        -----
        This is intended to replace the XML stuff as we converge on consistent input formats.
        """
        from armi.physics.thermalHydraulics import const  # avoid circular import

        yaml = YAML()
        tree = yaml.load(stream)
        if "settings" not in tree:
            raise exceptions.InvalidSettingsFileError(
                self.inputPath,
                "Missing the `settings:` header required in YAML settings",
            )
        if const.ORIFICE_SETTING_ZONE_MAP in tree:
            raise exceptions.InvalidSettingsFileError(
                self.inputPath, "Appears to be an orifice_settings file"
            )
        caseSettings = tree[Roots.CUSTOM]
        self.inputVersion = tree["metadata"][Roots.VERSION]
        for settingName, settingVal in caseSettings.items():
            self._applySettings(settingName, settingVal)

    def _checkInvalidSettings(self):
        if not self.invalidSettings:
            return
        try:
            invalidNames = "\n\t".join(self.invalidSettings)
            proceed = runLog.prompt(
                "Found {} invalid settings in {}.\n\n {} \n\t".format(
                    len(self.invalidSettings), self.inputPath, invalidNames
                ),
                "Invalid settings will be ignored. Continue running the case?",
                "YES_NO",
            )
        except exceptions.RunLogPromptUnresolvable:
            # proceed with invalid settings (they'll be ignored).
            proceed = True
        if not proceed:
            raise exceptions.InvalidSettingsStopProcess(self)
        else:
            runLog.warning("Ignoring invalid settings: {}".format(invalidNames))

    def _interpretXmlSetting(self, settingElement):
        settingName = settingElement.tag
        attributes = settingElement.attrib
        if settingName in self.settingsAlreadyRead:
            raise exceptions.SettingException(
                "The setting {} has been specified more than once in {}. Adjust input."
                "".format(settingName, self.inputPath)
            )
        # add here, before it gets converted by name cleaning below.
        self.settingsAlreadyRead.add(settingName)
        if settingName in settingsRules.OLD_TAGS:
            # name cleaning
            settingName = settingElement.attrib["key"].replace(" ", "")
            values = list(settingElement)
            if not values:
                attributes = {"type": settingsRules.OLD_TAGS[settingElement.tag]}
                if "val" in settingElement.attrib:
                    attributes["value"] = settingElement.attrib["val"]
                else:
                    # means this item has no children and no value, no reason for it to exist.
                    return
            else:
                attributes["value"] = [
                    subElement.attrib["val"] for subElement in values
                ]
                attributes["containedType"] = settingsRules.OLD_TAGS[
                    settingElement.attrib["type"]
                ]

        elif "value" not in attributes:
            raise exceptions.SettingException(
                "No value supplied for the setting {} in {}".format(
                    settingName, self.inputPath
                )
            )

        self._applySettings(settingName, attributes["value"])

    def _applySettings(self, name, val):
        nameToSet, _wasRenamed = self._renamer.renameSetting(name)
        settingsToApply = self.applyConversions(nameToSet, val)
        for settingName, value in settingsToApply.items():
            if settingName not in self.cs.settings:
                self.invalidSettings.add(settingName)
            else:
                # apply validations
                settingObj = self.cs.settings[settingName]
                if value:
                    value = applyTypeConversions(settingObj, value)

                # The value is automatically coerced into the
                # expected type when set using either the default or
                # user-defined schema
                self.cs[settingName] = value

    def applyConversions(self, name, value):
        """
        Applies conversion rules to give special behavior to certain named settings.

        Intended to be applied on setting names and attributes as soon as they're read
        in keep in mind everything in the attributes dictionary is still a string even
        if it's intended to be something else later, that happens at a later stage.
        """
        # general needs to come first for things like renaming.
        settingsToApply = {}
        for func in settingsRules.GENERAL_CONVERSIONS:
            settingsToApply.update(func(self.cs, name, value))

        func = settingsRules.TARGETED_CONVERSIONS.get(name, None)
        if func is not None:
            settingsToApply.update(func(self.cs, name, value))

        return settingsToApply


def applyTypeConversions(settingObj, value):
    """
    Coerce value to proper type given a valid setting object.

    Useful in converting XML settings with no type info (all string) as well as
    in GUI operations.
    """
    if settingObj.underlyingType == list and not isinstance(value, list):
        return ast.literal_eval(value)
    return value


class SettingsWriter:
    """Writes settings out to files.

    This can write in two styles:

    short
        setting values that are not their defaults only
    full
        all setting values regardless of default status

    """

    class Styles:
        """Enumeration of valid output styles"""

        short = "short"
        full = "full"

    def __init__(self, settings_instance, style="short"):
        self.cs = settings_instance
        self.style = style
        if style not in {self.Styles.short, self.Styles.full}:
            raise ValueError("Invalid supplied setting writing style {}".format(style))

    @staticmethod
    def _getVersion():
        tag, attrib = Roots.CUSTOM, {Roots.VERSION: armi.__version__}
        return tag, attrib

    def writeXml(self, stream):
        """Write settings to XML file."""
        settingData = self._getSettingDataToWrite()
        tag, attrib = self._getVersion()
        root = ET.Element(tag, attrib=attrib)
        tree = ET.ElementTree(root)

        for settingObj, settingDatum in settingData.items():
            settingNode = ET.SubElement(root, settingObj.name)
            for attribName in settingDatum:
                settingNode.set(attribName, str(settingObj.dump()))

        stream.write('<?xml version="1.0" ?>\n')
        stream.write(self.prettyPrintXmlRecursively(tree.getroot(), spacing=False))

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
        Clean up the dict before dumping to yaml.

        If it has just a value attrib it flattens it for brevity.
        """
        tag, attrib = self._getVersion()
        yamlData = {"metadata": attrib}  # put version info in
        cleanedData = collections.OrderedDict()
        for settingObj, settingDatum in settingData.items():
            if "value" in settingDatum and len(settingDatum) == 1:
                # ok to flatten
                cleanedData[settingObj.name] = settingObj.dump()
            else:
                cleanedData[settingObj.name] = settingDatum

        # this gets rid of a !!omap associated with ordered dicts
        yamlData.update({tag: ruamel.yaml.comments.CommentedMap(cleanedData)})
        return yamlData

    def _getSettingDataToWrite(self):
        """
        Make an ordered dict with all settings slated for being written.

        This is general so it can be dumped to whatever file format.
        """
        settingData = collections.OrderedDict()
        for _settingName, settingObject in iter(
            sorted(self.cs.settings.items(), key=lambda name: name[0].lower())
        ):
            if self.style == self.Styles.short and not settingObject.offDefault:
                continue

            attribs = settingObject.getCustomAttributes().items()
            settingDatum = {}
            for (attribName, attribValue) in attribs:
                if isinstance(attribValue, type):
                    attribValue = attribValue.__name__
                settingDatum[attribName] = attribValue
            settingData[settingObject] = settingDatum
        return settingData

    def prettyPrintXmlRecursively(self, node, indentation=0, spacing=True):
        r"""Generates a pretty output string of an element tree better than the default .write()

        Uses helper cleanQuotesFromString to get everything both python and xml readable

        Parameters
        ----------
        node : ET.Element
            the element tree element to write the output for
        indentation : int,
            not for manual use, but for the recursion to nicely nest parts of the string
        spacing : bool
            used to flip the newline behavior for spacing out an xml file or keeping it compact
            primarily for the difference between a default settings and a custom settings file.

        """
        if spacing:
            spacing = 1
        else:
            spacing = 0

        cleanTag = self.cleanStringForXml(node.tag)
        cleanText = self.cleanStringForXml(node.text)
        cleanTail = self.cleanStringForXml(node.tail)

        # open the tag
        output = "\n" + "\t" * indentation + "<{tag}".format(tag=cleanTag)
        indentation += 1

        # fill in attributes
        for key, value in iter(sorted(node.attrib.items())):
            cleanKey = self.cleanStringForXml(key)
            cleanValue = self.cleanStringForXml(value)
            output += (
                "\n" * spacing
                + "\t" * indentation * spacing
                + " " * ((spacing - 1) * -1)
                + '{key}="{value}"'.format(key=cleanKey, value=cleanValue)
            )

        # if there are internal nodes, keep the tag open, otherwise close it immediately
        if not node.text and not list(node):  # no internal tags
            output += " />" + "\n" * spacing
        elif node.text and not list(node):  # internal text, no children
            output += (
                ">"
                + "\n" * spacing
                + "\t" * indentation
                + "{text}\n".format(text=cleanText)
            )
            indentation -= 1
            output += "\t" * indentation + "</{tag}>".format(tag=cleanTag)
        elif node.text and list(node):  # internal text, children
            output += (
                ">"
                + "\n" * spacing
                + "\t" * indentation
                + "{text}\n".format(text=cleanText)
            )
            for child in list(node):
                output += self.prettyPrintXmlRecursively(
                    child, indentation=indentation, spacing=spacing
                )
            indentation -= 1
            output += "\t" * indentation + "</{tag}>".format(tag=cleanTag)
        else:  # has children, no text
            output += ">" + "\n" * spacing
            for child in list(node):
                output += self.prettyPrintXmlRecursively(
                    child, indentation=indentation, spacing=spacing
                )
            indentation -= 1
            output += "\n" + "\t" * indentation + "</{tag}>".format(tag=cleanTag)

        # add on the tail
        if node.tail:
            output += "{tail}".format(tail=cleanTail)

        return output

    def cleanStringForXml(self, s):
        """Assures no XML entity issues will occur on parsing a string

        A helper function used to make strings xml friendly
        XML has some reserved characters, this should handle them.
        apostrophes aren't  being dealt with but seem to behave nicely as is.

        http://en.wikipedia.org/wiki/List_of_XML_and_HTML_character_entity_references
        """
        if not s:
            return ""

        s = (
            s.replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")
        )  # .replace("'",'&apos;')
        s = re.sub(
            "&(?!quot;|lt;|gt;|amp;|apos;)", "&amp;", s
        )  # protects against chaining &amp
        return s
