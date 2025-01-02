# Copyright 2021 TerraPower, LLC
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

"""Migrate ARMI settings that have alphanumeric location labels to new numeric mode."""
import io
import re

from armi import runLog
from armi.migration.base import SettingsMigration
from armi.settings import caseSettings, settingsIO
from armi.utils.units import ASCII_LETTER_A, ASCII_ZERO

AXIAL_CHARS = [
    chr(asciiCode)
    for asciiCode in (
        list(range(ASCII_LETTER_A, ASCII_LETTER_A + 26))
        + list(range(ASCII_ZERO, ASCII_ZERO + 10))
        + list(range(ASCII_LETTER_A + 26, ASCII_LETTER_A + 32 + 26))
    )
]


class ConvertAlphanumLocationSettingsToNum(SettingsMigration):
    """Convert old location label values to new style."""

    fromVersion = "0.1.6"
    toVersion = "0.1.7"

    def _applyToStream(self):
        cs = caseSettings.Settings()
        reader = settingsIO.SettingsReader(cs)
        reader.readFromStream(self.stream)

        if reader.invalidSettings:
            runLog.info(
                "The following deprecated settings will be deleted:\n  * {}"
                "".format("\n  * ".join(list(reader.invalidSettings)))
            )

        cs = _modify_settings(cs)
        writer = settingsIO.SettingsWriter(cs)
        newStream = io.StringIO()
        writer.writeYaml(newStream)
        newStream.seek(0)
        return newStream


def _modify_settings(cs):
    if cs["detailAssemLocationsBOL"]:
        newLocs = []
        for loc in cs["detailAssemLocationsBOL"]:
            if "-" not in loc:
                # assume it is old style assem location.
                i, j, _k = getIndicesFromDIF3DStyleLocatorLabel(loc)
                newLoc = f"{i:03d}-{j:03d}"
                runLog.info(
                    f"Converting old-style location label `{loc}` to `{newLoc}`, assuming hex geom"
                )
                loc = newLoc
            newLocs.append(loc)

        cs = cs.modified(newSettings={"detailAssemLocationsBOL": newLocs})

    return cs


def getIndicesFromDIF3DStyleLocatorLabel(label):
    """Convert a ring-based label like A2003B into 1-based ring, location indices."""
    locMatch = re.search(r"([A-Z]\d)(\d\d\d)([A-Z]?)", label)
    if locMatch:
        # we have a valid location label. Process it and set parameters
        # convert A4 to 04, B2 to 12, etc.
        ring = locMatch.group(1)
        posLabel = locMatch.group(2)
        axLabel = locMatch.group(3)
        firstDigit = ord(ring[0]) - ASCII_LETTER_A
        if firstDigit < 10:
            i = int("{0}{1}".format(firstDigit, ring[1]))
        else:
            raise RuntimeError(
                "invalid label {0}. 1st character too large.".format(label)
            )
        j = int(posLabel)
        if axLabel:
            k = AXIAL_CHARS.index(axLabel)
        else:
            k = None
        return i, j, k

    raise RuntimeError("No Indices found for DIF3D-style label: {0}".format(label))
