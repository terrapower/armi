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
The data structures and schema of the cross section modeling options.

These are advanced/compound settings that are carried along in the normal cs
object but aren't simple key/value pairs. 

The cs object could either hold the base data (dicts) and create instances
of these data structure objects as needed, or the settings system could actually
hold instances of these data structures. It is most convenient to let the cs
object hold actual instances of these data.

See detailed docs in `:doc: Lattice Physics <reference/physics/neutronics/latticePhysics/latticePhysics>`.
"""
import voluptuous as vol

from armi.settings.setting2 import Setting

from armi.physics.neutronics.crossSectionGroupManager import (
    BLOCK_COLLECTIONS,
    HOMOGENEOUS_BLOCK_COLLECTIONS,
)

# define conf and schema here since this is closest to where the objects live
XS_GEOM_TYPES = {"0D", "2D hex", "1D slab", "1D cylinder", None}

CONF_GEOM = "geometry"
CONF_BLOCK_REPRESENTATION = "blockRepresentation"
CONF_DRIVER = "driverID"
CONF_BUCKLING = "criticalBuckling"
CONF_REACTION_DRIVER = "nuclideReactionDriver"
CONF_BLOCKTYPES = "validBlockTypes"
CONF_EXTERNAL_DRIVER = "externalDriver"
CONF_HOMOGBLOCK = "useHomogenizedBlockComposition"
CONF_INTERNAL_RINGS = "numInternalRings"
CONF_EXTERNAL_RINGS = "numExternalRings"
CONF_MERGE_INTO_CLAD = "mergeIntoClad"
CONF_FILE_LOCATION = "fileLocation"
CONF_MESH_PER_CM = "meshSubdivisionsPerCm"

SINGLE_XS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_GEOM, default="0D"): vol.All(str, vol.In(XS_GEOM_TYPES)),
        vol.Optional(CONF_BLOCK_REPRESENTATION): vol.All(
            str,
            vol.In(set(BLOCK_COLLECTIONS.keys()) | set(HOMOGENEOUS_BLOCK_COLLECTIONS)),
        ),
        vol.Optional(CONF_DRIVER): str,
        vol.Optional(CONF_BUCKLING): bool,
        vol.Optional(CONF_REACTION_DRIVER): str,
        vol.Optional(CONF_BLOCKTYPES): [str],
        vol.Optional(CONF_HOMOGBLOCK): bool,
        vol.Optional(CONF_EXTERNAL_DRIVER, default=True): bool,
        vol.Optional(CONF_INTERNAL_RINGS): vol.Coerce(int),
        vol.Optional(CONF_EXTERNAL_RINGS): vol.Coerce(int),
        vol.Optional(CONF_MERGE_INTO_CLAD): [str],
        vol.Optional(CONF_FILE_LOCATION): [str],
        vol.Optional(CONF_MESH_PER_CM): vol.Coerce(float),
    }
)

XS_SCHEMA = vol.Schema({vol.All(str, vol.Length(min=1, max=2)): SINGLE_XS_SCHEMA})


class XSModelingOptions:
    """Advanced cross section modeling options for a particular XS ID."""

    def __init__(
        self,
        xsID,
        geometry=None,
        blockRepresentation=None,
        driverID=None,
        criticalBuckling=None,
        nuclideReactionDriver=None,
        validBlockTypes=None,
        externalDriver=True,
        useHomogenizedBlockComposition=False,
        numInternalRings=1,
        numExternalRings=1,
        mergeIntoClad=None,
        fileLocation=None,
        meshSubdivisionsPerCm=None,
    ):
        self.xsID = xsID
        self.geometry = geometry
        self.blockRepresentation = blockRepresentation
        self.driverID = driverID
        self.criticalBuckling = criticalBuckling
        self.nuclideReactionDriver = nuclideReactionDriver
        self.validBlockTypes = validBlockTypes
        self.externalDriver = externalDriver
        self.useHomogenizedBlockComposition = useHomogenizedBlockComposition
        self.numInternalRings = numInternalRings
        self.numExternalRings = numExternalRings
        self.mergeIntoClad = mergeIntoClad
        self.fileLocation = fileLocation
        self.meshSubdivisionsPerCm = meshSubdivisionsPerCm

    @property
    def xsType(self):
        """Return the single-char cross section type indicator."""
        return self.xsID[0]

    @property
    def buGroup(self):
        """Return the single-char burnup group indicator."""
        return self.xsID[1]

    @property
    def isPregenerated(self):
        """True if this points to a pre-generated XS file."""
        return self.fileLocation is not None

    def setDefaults(self, blockRepresentation, validBlockTypes):
        # TODO: explain this logic
        validBlockTypes = None if validBlockTypes else ["fuel"]
        if self.geometry == "0D":
            defaults = dict(
                criticalBuckling=True,
                numExternalRings=None,
                blockRepresentation=blockRepresentation,
                validBlockTypes=validBlockTypes,
            )
        elif self.geometry == "1D slab":
            defaults = dict(
                criticalBuckling=False,
                mergeIntoClad=[],
                blockRepresentation=blockRepresentation,
                validBlockTypes=validBlockTypes,
            )
        elif self.geometry == "1D cylinder":
            defaults = dict(
                criticalBuckling=False,
                mergeIntoClad=[],
                blockRepresentation=blockRepresentation,
                numExternalRings=1,
                validBlockTypes=validBlockTypes,
            )
        elif self.geometry == "2D hex":
            defaults = dict(
                blockRepresentation=blockRepresentation,
                numExternalRings=1,
                externalDriver=True,
            )
        else:
            defaults = dict(
                blockRepresentation=blockRepresentation, validBlockTypes=validBlockTypes
            )

        for attrName, defaultValue in defaults.items():
            currentValue = getattr(self, attrName)
            if currentValue is None:
                setattr(self, attrName, defaultValue)

        self._checkSettings()

    def _checkSettings(self):
        """Fail fast if cross section settings will cause lattice physics to fail."""
        geomsThatNeedMeshSize = ("1D slab", "1D cylinder")
        if self.geometry in geomsThatNeedMeshSize:
            if self.meshSubdivisionsPerCm is None:
                raise ValueError(
                    "{} geometry requires `mesh points per cm` to be defined in cross sections.".format(
                        self.geometry
                    )
                )
            if self.criticalBuckling != False:
                raise ValueError(
                    "{} geometry cannot model critical buckling. Please disable".format(
                        self.geometry
                    )
                )


class XSSettingDef(Setting):
    """
    The setting object with custom serialization.

    Note that the VALUE of the setting will be a XSSettingValue object.
    """

    def _load(self, inputVal):
        """Read a dict of input, validate it, and populate this with new instances."""
        inputVal = XS_SCHEMA(inputVal)
        for xsID, inputParams in inputVal.items():
            self._value[xsID] = XSModelingOptions(xsID, **inputParams)
        return self._value

    def dump(self):
        """
        Dump serialized XSModelingOptions.

        This is used when saving settings to a file. Conveniently,
        YAML libs can load/dump simple objects like this out of the box.

        We massage the data on its way out for user convenience, leaving None values out
        and leaving the special ``xsID`` value out.
        """
        output = self._serialize(self._value)
        output = XS_SCHEMA(output)  # validate on the way out too
        return output

    def setValue(self, val):
        """
        Set value of setting to val.
        
        Since this is a custom serializable setting, we allow users
        to pass in either a ``XSModelingOptions`` object itself
        or a dictionary representation of one. 
        """
        try:
            if isinstance(list(val.values())[0], XSModelingOptions):
                val = self._serialize(val)
        except TypeError:
            # value is not a dict, may be a CommentedMapValuesView or related; serialization
            # not required
            pass

        Setting.setValue(self, val)

    @staticmethod
    def _serialize(value):
        output = {}
        for xsID, val in value.items():
            xsIDVals = {
                config: confVal
                for config, confVal in val.__dict__.items()
                if config != "xsID" and confVal is not None
            }
            output[xsID] = xsIDVals
        return output


class XSSettings(dict):
    """
    The container that holds the multiple individual XS settings for different ids.

    This is what the value of the cs setting is set to. It handles reading/writing the settings
    to file as well as some other special behavior.
    """

    def __getitem__(self, xsID):
        """
        Return the stored settings of the same xs type and the lowest burnup group if they exist.

        Notes
        -----
        1. If `AA` and `AB` exist, but `AC` is created, then the intended behavior is that `AC`
           settings will be set to the settings in `AA`.

        2. If only `YZ' exists and `YA` is created, then the intended behavior is that
           `YA` settings will NOT be set to the settings in `YZ`.

        3. Requirements for using the existing cross section settings:
           a.  The existing XS ID must match the current XS ID.
           b.  The current xs burnup group must be larger than the lowest burnup group for the
                existing XS ID
           c.  If 3a. and 3b. are not met, then the default cross section settings will be
               set for the current XS ID
        """
        if xsID in self:
            return dict.__getitem__(self, xsID)

        xsType = xsID[0]
        buGroup = xsID[1]
        existingXsOpts = [
            xsOpt
            for xsOpt in self.values()
            if xsOpt.xsType == xsType and xsOpt.buGroup < buGroup
        ]

        if not any(existingXsOpts):
            return self._getDefault(xsID)

        else:
            return sorted(existingXsOpts, key=lambda xsOpt: xsOpt.buGroup)[0]

    def setDefaults(self, cs):
        """
        Set defaults for current and future xsIDs based on cs.

        This must be delayed past read-time since the settings that effect this
        may not be loaded yet and could still be at their own defaults when
        this input is being processed. Thus, defaults are set at a later time.

        See Also
        --------
        armi.physics.neutronics.crossSectionGroupManager.CrossSectionGroupManager.interactBOL : calls this
        """
        self._xsBlockRepresentation = cs["xsBlockRepresentation"]
        self._disableBlockTypeExclusionInXsGeneration = cs[
            "disableBlockTypeExclusionInXsGeneration"
        ]
        for xsId, xsOpt in self.items():
            xsOpt.setDefaults(
                cs["xsBlockRepresentation"],
                cs["disableBlockTypeExclusionInXsGeneration"],
            )

    def _getDefault(self, xsID):
        """
        Process the optional 'cross section' input field.

        This input allows users to override global defaults for specific cross section IDs (xsID).

        To simplify downstream handling of the various XS controls, we build a full data structure here
        that should fully define the settings for each individual cross section ID.
        """
        xsOpt = XSModelingOptions(xsID, geometry="0D")
        xsOpt.setDefaults(
            self._xsBlockRepresentation, self._disableBlockTypeExclusionInXsGeneration
        )
        return xsOpt
