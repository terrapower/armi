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

"""This module contains classes and methods for reading and writing
:py:class:`~armi.settings.caseSettings.Settings`, and the contained
:py:class:`~armi.settings.setting.Setting`.
"""
import re
import collections
import warnings
import os
import enum
import ast

from ruamel.yaml import YAML
import ruamel.yaml.comments
import xml.etree.ElementTree as ET

import armi
from armi import runLog
from armi.physics.thermalHydraulics import const
from armi.localization import exceptions
from armi.settings import setting
from armi.settings import setting2
from armi.settings import settingsRules
from armi.reactor import geometry


class Roots(object):
    """XML tree root node common strings"""

    CUSTOM = "settings"
    DEFINITION = "settings-definitions"
    VERSION = "version"


class _SettingsReader(object):
    """Abstract class for processing settings files.

    Parameters
    ----------
    cs : CaseSettings
        The settings object to read into

    See Also
    --------
    SettingsReader
    SettingsDefinitionReader
    """

    class SettingsInputFormat(enum.Enum):
        XML = enum.auto()
        YAML = enum.auto()

    FORMAT_FROM_EXT = {
        ".xml": SettingsInputFormat.XML,
        ".yaml": SettingsInputFormat.YAML,
    }

    def __init__(self, cs, rootTag):
        self.cs = cs
        self.rootTag = rootTag
        self.format = self.SettingsInputFormat.YAML
        self.inputPath = "<stream>"

        self.invalidSettings = set()
        self.settingsAlreadyRead = set()
        self.liveVersion = armi.__version__
        self.inputVersion = armi.__version__
        # the input version will be overwritten if explicitly stated in input file
        # otherwise it's assumed to precede the version inclusion change and should be treated as alright

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
        ext = os.path.splitext(path)[1].lower()
        self.format = self.FORMAT_FROM_EXT[ext]
        self.inputPath = path
        with open(path, "r") as f:
            self.readFromStream(f, handleInvalids, self.format)

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
            if settingRoot.tag == geometry.SystemLayoutInput.ROOT_TAG:
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
            self._interpretSetting(settingElement)

        if handleInvalids:
            self._resolveProblems()

    def _readYaml(self, stream, handleInvalids=True):
        """
        Read settings from a YAML stream.

        Notes
        -----
        This is intended to replace the XML stuff as we converge on consistent input formats.
        """
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

    def _resolveProblems(self):
        raise NotImplementedError

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

    def _interpretSetting(self, settingElement):
        raise NotImplementedError()

    def applyConversions(self, name, value):
        """
        Applies conversion rules to give special behavior to certain named settings.

        Intended to be applied on setting names and attributes as soon as they're read in
        keep in mind everything in the attributes dictionary is still a string even if it's intended to be
        something else later, that happens at a later stage.

        """
        # general needs to come first for things like renaming.
        settingsToApply = {}
        for func in settingsRules.GENERAL_CONVERSIONS:
            settingsToApply.update(func(self.cs, name, value))

        func = settingsRules.TARGETED_CONVERSIONS.get(name, None)
        if func is not None:
            settingsToApply.update(func(self.cs, name, value))

        return settingsToApply


class SettingsReader(_SettingsReader):
    """A specialized _SettingsReader which only assigns values to existing settings."""

    def __init__(self, cs):
        _SettingsReader.__init__(self, cs, Roots.CUSTOM)

    def _interpretSetting(self, settingElement):
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
        settingsToApply = self.applyConversions(name, val)
        for settingName, value in settingsToApply.items():
            if settingName not in self.cs.settings:
                self.invalidSettings.add(settingName)
            else:
                # apply validations
                settingObj = self.cs.settings[settingName]
                if value:
                    value = applyTypeConversions(settingObj, value)
                try:
                    value = settingObj.schema(value)
                except:
                    runLog.error(
                        f"Validation error with setting: {settingName} = {repr(value)}"
                    )
                    raise
                self.cs[settingName] = value

    def _resolveProblems(self):
        self._checkInvalidSettings()


def applyTypeConversions(settingObj, value):
    """
    Coerce value to proper type given a valid setting object.

    Useful in converting XML settings with no type info (all string) as well as
    in GUI operations.
    """
    if settingObj.underlyingType == list and not isinstance(value, list):
        return ast.literal_eval(value)
    return value


class SettingsDefinitionReader(_SettingsReader):
    """A specialized _SettingsReader which creates new setting instances."""

    def __init__(self, cs):
        _SettingsReader.__init__(self, cs, Roots.DEFINITION)
        self._occupied_names = set(cs.settings.keys())

    def _interpretSetting(self, settingElement):
        settingName = settingElement.tag
        attributes = settingElement.attrib

        if "type" not in attributes or "default" not in attributes:
            raise exceptions.InvalidSettingDefinition(settingName, attributes)

        default = attributes["default"]  # always a string at this point
        settingValues = self.applyConversions(settingName, default)
        # check for a new error conditions
        for correctedName, correctedDefault in settingValues.items():
            if correctedName != settingName:
                raise exceptions.SettingException(
                    "Settings definition file {} contained setting named {},\n"
                    "but it was changed to {}.".format(
                        self.inputPath, settingName, correctedName
                    )
                )
            if correctedDefault != default:
                # problem here when default is like, an string empty list '[]'
                # and it gets corrected to a real list. So hack:
                if default != "[]":
                    raise exceptions.SettingException(
                        "Settings definition file {} contained setting named {}, "
                        "but the value was changed from {} to {}. Change default "
                        "something that does not get auto-corrected.".format(
                            self.inputPath,
                            settingName,
                            repr(default),
                            repr(correctedDefault),
                        )
                    )
            if settingName.lower() in self._occupied_names:
                raise exceptions.SettingNameCollision(
                    'Duplicate definition for the setting "{}" found in {}.'.format(
                        settingName, self.inputPath
                    )
                )

        # everything is good, time to create an actual setting object
        self.cs.settings[settingName] = setting.Setting.factory(settingName, attributes)
        self._occupied_names.add(settingName.lower())

    def _resolveProblems(self):
        self._checkInvalidSettings()


class SettingsWriter(object):
    """Writes settings out to files.

    This can write in three styles:
    
    definition
        setting definitions listing, includes every setting
    short
        setting values that are not their defaults only
    full 
        all setting values regardless of default status

    """

    class Styles(object):
        """Collection of valid output styles"""

        definition = "definition"
        short = "short"
        full = "full"

    def __init__(self, settings_instance, style="short"):
        self.cs = settings_instance
        self.style = style
        if style not in {self.Styles.definition, self.Styles.short, self.Styles.full}:
            raise ValueError("Invalid supplied setting writing style {}".format(style))

    def _getVersion(self):
        if self.style == self.Styles.definition:
            tag, attrib = Roots.DEFINITION, {}
        else:
            tag, attrib = Roots.CUSTOM, {Roots.VERSION: armi.__version__}
        return tag, attrib

    def writeXml(self, stream):
        """Write settings to XML file."""
        settingData = self._getSettingDataToWrite()
        tag, attrib = self._getVersion()
        root = ET.Element(tag, attrib=attrib)
        tree = ET.ElementTree(root)

        for settingObj, settingDatum in settingData.items():
            if isinstance(settingObj, setting2.Setting):
                # do not write new-style settings to old-style XML. It fails on read.
                continue
            settingNode = ET.SubElement(root, settingObj.name)
            for attribName, attribValue in settingDatum.items():
                settingNode.set(attribName, str(attribValue))

        stream.write('<?xml version="1.0" ?>\n')
        stream.write(
            self.prettyPrintXmlRecursively(
                tree.getroot(), spacing=self.style == self.Styles.definition
            )
        )

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
                val = settingDatum["value"]
                if isinstance(settingObj, setting2.Setting):
                    val = settingObj.dump()
                cleanedData[settingObj.name] = val
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
            attribs = (
                settingObject.getDefaultAttributes().items()
                if self.style == self.Styles.definition
                else settingObject.getCustomAttributes().items()
            )
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
