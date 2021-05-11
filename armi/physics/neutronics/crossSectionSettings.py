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

from typing import Dict, Union

import voluptuous as vol

from armi import runLog
from armi.settings import Setting

from armi.physics.neutronics.crossSectionGroupManager import BLOCK_COLLECTIONS

CONF_XSID = "xsID"
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

# These may be used as arguments to ``latticePhysicsInterface._getGeomDependentWriters``.
# This could be an ENUM later.
XS_GEOM_TYPES = {
    "0D",
    "1D slab",
    "1D cylinder",
    "2D hex",
}

# This dictionary defines the valid set of inputs based on
# the geometry type within the ``XSModelingOptions``
_VALID_INPUTS_BY_GEOMETRY_TYPE = {
    "0D": {
        CONF_XSID,
        CONF_GEOM,
        CONF_BUCKLING,
        CONF_DRIVER,
        CONF_BLOCKTYPES,
        CONF_BLOCK_REPRESENTATION,
    },
    "1D slab": {
        CONF_XSID,
        CONF_GEOM,
        CONF_MESH_PER_CM,
        CONF_BLOCKTYPES,
        CONF_BLOCK_REPRESENTATION,
    },
    "1D cylinder": {
        CONF_XSID,
        CONF_GEOM,
        CONF_MERGE_INTO_CLAD,
        CONF_DRIVER,
        CONF_HOMOGBLOCK,
        CONF_INTERNAL_RINGS,
        CONF_EXTERNAL_RINGS,
        CONF_MESH_PER_CM,
        CONF_BLOCKTYPES,
        CONF_BLOCK_REPRESENTATION,
    },
    "2D hex": {
        CONF_XSID,
        CONF_GEOM,
        CONF_BUCKLING,
        CONF_EXTERNAL_DRIVER,
        CONF_DRIVER,
        CONF_REACTION_DRIVER,
        CONF_EXTERNAL_RINGS,
        CONF_BLOCK_REPRESENTATION,
    },
}

_SINGLE_XS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_GEOM): vol.All(str, vol.In(XS_GEOM_TYPES)),
        vol.Optional(CONF_BLOCK_REPRESENTATION): vol.All(
            str,
            vol.In(
                set(BLOCK_COLLECTIONS.keys()),
            ),
        ),
        vol.Optional(CONF_DRIVER): str,
        vol.Optional(CONF_BUCKLING): bool,
        vol.Optional(CONF_REACTION_DRIVER): str,
        vol.Optional(CONF_BLOCKTYPES): [str],
        vol.Optional(CONF_HOMOGBLOCK): bool,
        vol.Optional(CONF_EXTERNAL_DRIVER): bool,
        vol.Optional(CONF_INTERNAL_RINGS): vol.Coerce(int),
        vol.Optional(CONF_EXTERNAL_RINGS): vol.Coerce(int),
        vol.Optional(CONF_MERGE_INTO_CLAD): [str],
        vol.Optional(CONF_FILE_LOCATION): [str],
        vol.Optional(CONF_MESH_PER_CM): vol.Coerce(float),
    }
)

_XS_SCHEMA = vol.Schema({vol.All(str, vol.Length(min=1, max=2)): _SINGLE_XS_SCHEMA})


class XSSettings(dict):
    """
    Container for holding multiple cross section settings based on their XSID.

    This is intended to be stored as part of a case settings and to be
    used for cross section modeling within a run.

    Notes
    -----
    This is a specialized dictionary that functions in a similar manner as a
    defaultdict where if a key (i.e., XSID) is missing then a default will
    be set. If a missing key is being added before the ``setDefaults`` method
    is called then this will produce an error.

    This cannot just be a defaultdict because the creation of new cross
    section settings are dependent on user settings.
    """

    def __init__(self, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)
        self._blockRepresentation = None
        self._validBlockTypes = None

    def __repr__(self):
        return f"<{self.__class__.__name__} with XS IDs {self.keys()}>"

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

    def setDefaults(self, blockRepresentation, validBlockTypes):
        """
        Set defaults for current and future xsIDs based user settings.

        This must be delayed past read-time since the settings that effect this
        may not be loaded yet and could still be at their own defaults when
        this input is being processed. Thus, defaults are set at a later time.

        Parameters
        ----------
        blockRepresentation : str
            Valid options are provided in ``CrossSectionGroupManager.BLOCK_COLLECTIONS``

        validBlockTypes : list of str or bool
           This configures which blocks (by their type) that the cross section
           group manager will merge together to create a representative block. If
           set to ``None`` or ``True`` then all block types in the XS ID will be
           considered. If this is set to ``False`` then a default of ["fuel"] will
           be used. If this is set to a list of strings then the specific list will
           be used. A typical input may be ["fuel"] to just consider the fuel blocks.

        See Also
        --------
        armi.physics.neutronics.crossSectionGroupManager.CrossSectionGroupManager.interactBOL : calls this
        """
        self._blockRepresentation = blockRepresentation
        self._validBlockTypes = validBlockTypes
        for _xsId, xsOpt in self.items():
            xsOpt.setDefaults(
                blockRepresentation,
                validBlockTypes,
            )
            xsOpt.validate()

    def _getDefault(self, xsID):
        """
        Process the optional ``crossSectionControl`` setting.

        This input allows users to override global defaults for specific cross section IDs (xsID).

        To simplify downstream handling of the various XS controls, we build a full data structure here
        that should fully define the settings for each individual cross section ID.
        """
        if self._blockRepresentation is None:
            raise ValueError(
                f"The defaults of {self} have not been set. Call ``setDefaults`` first "
                "before attempting to add a new XS ID."
            )

        xsOpt = XSModelingOptions(xsID, geometry="0D")
        xsOpt.setDefaults(self._blockRepresentation, self._validBlockTypes)
        xsOpt.validate()
        return xsOpt


class XSModelingOptions:
    """
    Cross section modeling options for a particular XS ID.

    Attributes
    ----------
    xsID : str
        Cross section ID that is two characters maximum (i.e., AA).

    geometry: str
        The geometry modeling approximation for regions of the core with
        this assigned xsID. This is required if the ``fileLocation``
        attribute is not provided. This cannot be set if the ``fileLocation``
        is provided.

    fileLocation: list of str
        This should be a list of paths where the cross sections for this
        xsID can be copied from. This is required if the ``geometry``
        attribute is not provided. This cannot be set if the ``geometry``
        is provided.

    validBlockTypes: str or None
        This is a configuration option for how the cross section group manager
        determines which blocks/regions to manage as part of the same collection
        for the current xsID. If this is set to ``None`` then all blocks/regions
        with the current xsID will be considered.

    blockRepresentation : str
        This is a configuration option for how the cross section group manager
        will select how to create a representative block based on the collection
        within the same xsID. See: ``crossSectionGroupManager.BLOCK_COLLECTIONS``.

    driverID : str
        This is a lattice physics configuration option used to determine which
        representative block can be used as a "fixed source" driver for another
        composition. This is particularly useful for non-fuel or highly subcritical
        regions.

    criticalBuckling : bool
        This is a lattice physics configuration option used to enable or disable
        the critical buckling search option.

    nuclideReactionDriver : str
        This is a lattice physics configuration option that is similar to the
        ``driverID``, but rather than applying the source from a specific
        representative block, the neutron source is taken from a single
        nuclides fission spectrum (i.e., U235). This is particularly useful
        for configuring SERPENT 2 lattice physics calculations.

    externalDriver : bool
        This is a lattice physics configuration option that can be used
        to determine if the fixed source problem is internally driven
        or externally driven by the ``driverID`` region. Externally
        driven means that the region will be placed on the outside of the
        current xsID block/region. If this is False then the driver
        region will be "inside" (i.e., an inner ring in a cylindrical
        model).

    useHomogenizedBlockComposition : bool
        This is a lattice physics configuration option that is useful for
        modeling spatially dependent problems (i.e., 1D/2D). If this is
        True then the representative block for the current xsID will be
        be a homogenized region. If this is False then the block will be
        represented in the geometry type selected. This is mainly used for
        1D cylindrical problems.

    numInternalRings : int
        This is a lattice physics configuration option that is used to
        specify the number of grid-based rings for the representative block.

    numExternalRings : int
        This is a lattice physics configuration option that is used to
        specify the number of grid-based rings for the driver block.

    mergeIntoClad : list of str
        This is a lattice physics configuration option that is a list of component
        names to merge into a "clad" component. This is highly-design specific
        and is sometimes used to merge a "gap" or low-density region into
        a "clad" region to avoid numerical issues.

    meshSubdivisionsPerCm : float
        This is a lattice physics configuration option that can be used to control
        subregion meshing of the representative block in 1D problems.

    Notes
    -----
    Not all default attributes may be useful for your specific application and you may
    require other types of configuration options. These are provided as examples since
    the base ``latticePhysicsInterface`` does not implement models that use these. For
    additional options, consider subclassing the base ``Setting`` object and using this
    model as a template.
    """

    def __init__(
        self,
        xsID,
        geometry=None,
        fileLocation=None,
        validBlockTypes=None,
        blockRepresentation=None,
        driverID=None,
        criticalBuckling=None,
        nuclideReactionDriver=None,
        externalDriver=None,
        useHomogenizedBlockComposition=None,
        numInternalRings=None,
        numExternalRings=None,
        mergeIntoClad=None,
        meshSubdivisionsPerCm=None,
    ):
        self.xsID = xsID
        self.geometry = geometry
        self.fileLocation = fileLocation
        self.validBlockTypes = validBlockTypes
        self.blockRepresentation = blockRepresentation

        # These are application specific, feel free use them
        # in your own lattice physics plugin(s).
        self.driverID = driverID
        self.criticalBuckling = criticalBuckling
        self.nuclideReactionDriver = nuclideReactionDriver
        self.externalDriver = externalDriver
        self.useHomogenizedBlockComposition = useHomogenizedBlockComposition
        self.numInternalRings = numInternalRings
        self.numExternalRings = numExternalRings
        self.mergeIntoClad = mergeIntoClad
        self.meshSubdivisionsPerCm = meshSubdivisionsPerCm

    def __repr__(self):
        if self.isPregenerated:
            suffix = f"Pregenerated: {self.isPregenerated}"
        else:
            suffix = f"Geometry Model: {self.geometry}"
        return f"<{self.__class__.__name__}, XSID: {self.xsID}, {suffix}>"

    def __iter__(self):
        return iter(self.__dict__.items())

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

    def serialize(self):
        """Return as a dictionary without ``xsID`` and with ``None`` values excluded."""
        doNotSerialize = ["xsID"]
        return {
            key: val
            for key, val in self
            if key not in doNotSerialize and val is not None
        }

    def validate(self):
        """
        Performs validation checks on the inputs and provides warnings for option inconsistencies.

        Raises
        ------
        ValueError
            When the mutually exclusive ``fileLocation`` and ``geometry`` attributes
            are provided or when neither are provided.
        """
        # Check for valid inputs when the file location is supplied.
        if self.fileLocation is None and self.geometry is None:
            raise ValueError(f"{self} is missing a geometry input or a file location.")

        if self.fileLocation is not None and self.geometry is not None:
            raise ValueError(
                f"Either file location or geometry inputs in {self} must be given, but not both. "
                "Remove one or the other."
            )

        invalids = []
        if self.fileLocation is not None:
            for var, val in self:
                # Skip these attributes since they are valid options
                # when the ``fileLocation`` attribute`` is set.
                if var in [CONF_XSID, CONF_FILE_LOCATION, CONF_BLOCK_REPRESENTATION]:
                    continue
                if val is not None:
                    invalids.append((var, val))

        if invalids:
            runLog.debug(
                f"The following inputs in {self} are not valid when the file location is set:"
            )
            for var, val in invalids:
                runLog.debug(f"\tAttribute: {var}, Value: {val}")

        # Check for valid inputs when the geometry is supplied.
        invalids = []
        if self.geometry is not None:
            validOptions = _VALID_INPUTS_BY_GEOMETRY_TYPE[self.geometry]
            for var, val in self:
                if var not in validOptions and val is not None:
                    invalids.append((var, val))

        if invalids:
            runLog.debug(
                f"The following inputs in {self} are not valid when `{self.geometry}` geometry type is set:"
            )
            for var, val in invalids:
                runLog.debug(f"\tAttribute: {var}, Value: {val}")
            runLog.debug(
                f"The valid options for the `{self.geometry}` geometry are: {validOptions}"
            )

    def setDefaults(self, blockRepresentation, validBlockTypes):
        """
        This sets the defaults based on some recommended values based on the geometry type.

        Parameters
        ----------
        blockRepresentation : str
            Valid options are provided in ``CrossSectionGroupManager.BLOCK_COLLECTIONS``

        validBlockTypes : list of str or bool
           This configures which blocks (by their type) that the cross section
           group manager will merge together to create a representative block. If
           set to ``None`` or ``True`` then all block types in the XS ID will be
           considered. If this is set to ``False`` then a default of ["fuel"] will
           be used. If this is set to a list of strings then the specific list will
           be used. A typical input may be ["fuel"] to just consider the fuel blocks.

        Notes
        -----
        These defaults are application-specific and design specific. They are included
        to provide an example and are tuned to fit the internal needs of TerraPower. Consider
        a separate implementation/subclass if you would like different behavior.
        """
        if type(validBlockTypes) == bool:
            validBlockTypes = None if validBlockTypes else ["fuel"]
        else:
            validBlockTypes = validBlockTypes

        defaults = {}
        if self.isPregenerated:
            defaults = {
                CONF_FILE_LOCATION: self.fileLocation,
                CONF_BLOCK_REPRESENTATION: blockRepresentation,
            }

        elif self.geometry == "0D":
            defaults = {
                CONF_GEOM: "0D",
                CONF_BUCKLING: True,
                CONF_DRIVER: "",
                CONF_BLOCK_REPRESENTATION: blockRepresentation,
                CONF_BLOCKTYPES: validBlockTypes,
            }
        elif self.geometry == "1D slab":
            defaults = {
                CONF_GEOM: "1D slab",
                CONF_MESH_PER_CM: 1.0,
                CONF_BLOCK_REPRESENTATION: blockRepresentation,
                CONF_BLOCKTYPES: validBlockTypes,
            }
        elif self.geometry == "1D cylinder":
            defaults = {
                CONF_GEOM: "1D cylinder",
                CONF_DRIVER: "",
                CONF_MERGE_INTO_CLAD: ["gap"],
                CONF_MESH_PER_CM: 1.0,
                CONF_INTERNAL_RINGS: 0,
                CONF_EXTERNAL_RINGS: 1,
                CONF_HOMOGBLOCK: False,
                CONF_BLOCK_REPRESENTATION: blockRepresentation,
                CONF_BLOCKTYPES: validBlockTypes,
            }
        elif self.geometry == "2D hex":
            defaults = {
                CONF_GEOM: "2D hex",
                CONF_BUCKLING: False,
                CONF_EXTERNAL_DRIVER: True,
                CONF_DRIVER: "",
                CONF_REACTION_DRIVER: None,
                CONF_EXTERNAL_RINGS: 1,
                CONF_BLOCK_REPRESENTATION: blockRepresentation,
            }

        for attrName, defaultValue in defaults.items():
            currentValue = getattr(self, attrName)
            if currentValue is None:
                setattr(self, attrName, defaultValue)

        self.validate()


def serializeXSSettings(xsSettingsDict: Union[XSSettings, Dict]) -> Dict[str, Dict]:
    """
    Return a serialized form of the ``XSSettings`` as a dictionary.

    Notes
    -----
    Attributes that are not set (i.e., set to None) will be skipped.
    """
    if not isinstance(xsSettingsDict, dict):
        raise TypeError(f"Expected a dictionary for {xsSettingsDict}")

    output = {}
    for xsID, xsOpts in xsSettingsDict.items():

        # Setting the value to an empty dictionary
        # if it is set to a None or an empty
        # dictionary.
        if not xsOpts:
            continue

        if isinstance(xsOpts, XSModelingOptions):
            xsIDVals = xsOpts.serialize()

        elif isinstance(xsOpts, dict):
            xsIDVals = {
                config: confVal
                for config, confVal in xsOpts.items()
                if config != "xsID" and confVal is not None
            }
        else:
            raise TypeError(
                f"{xsOpts} was expected to be a ``dict`` or "
                f"``XSModelingOptions`` options type but is type {type(xsOpts)}"
            )

        output[str(xsID)] = xsIDVals
    return output


class XSSettingDef(Setting):
    """
    Custom setting object to manage the cross section dictionary-like inputs.

    Notes
    -----
    This uses the ``xsSettingsValidator`` schema to validate the inputs
    and will automatically coerce the value into a ``XSSettings`` dictionary.
    """

    def __init__(self, name):
        description = "Data structure defining how cross sections are created"
        label = "Cross section control"
        default = XSSettings()
        options = None
        schema = xsSettingsValidator
        enforcedOptions = False
        subLabels = None
        isEnvironment = False
        oldNames = None
        Setting.__init__(
            self,
            name,
            default,
            description,
            label,
            options,
            schema,
            enforcedOptions,
            subLabels,
            isEnvironment,
            oldNames,
        )

    def dump(self):
        """Return a serialized version of the ``XSSetting`` object."""
        return serializeXSSettings(self._value)


def xsSettingsValidator(xsSettingsDict: Dict[str, Dict]) -> XSSettings:
    """
    Returns a ``XSSettings`` object if validation is successful.

    Notes
    -----
    This provides two levels of checks. The first check is that the attributes
    provided as user input contains the correct key/values and the values are
    of the correct type. The second check uses the ``XSModelingOptions.validate``
    method to check for input inconsistencies and provides warnings if there
    are any issues.
    """
    xsSettingsDict = serializeXSSettings(xsSettingsDict)
    xsSettingsDict = _XS_SCHEMA(xsSettingsDict)
    vals = XSSettings()
    for xsID, inputParams in xsSettingsDict.items():
        if not inputParams:
            continue
        xsOpt = XSModelingOptions(xsID, **inputParams)
        xsOpt.validate()
        vals[xsID] = xsOpt
    return vals
