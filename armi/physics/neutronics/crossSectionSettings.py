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

from enum import Enum
from typing import Dict, Union

import voluptuous as vol

from armi import context, runLog
from armi.physics.neutronics import crossSectionGroupManager
from armi.physics.neutronics.crossSectionGroupManager import BLOCK_COLLECTIONS
from armi.settings import Setting

CONF_BLOCK_REPRESENTATION = "blockRepresentation"
CONF_MEMORY_REQUIREMENT = "requiredRAM"
CONF_BLOCKTYPES = "validBlockTypes"
CONF_BUCKLING = "criticalBuckling"
CONF_DRIVER = "driverID"
CONF_EXTERNAL_DRIVER = "externalDriver"
CONF_EXTERNAL_RINGS = "numExternalRings"
CONF_XS_FILE_LOCATION = "xsFileLocation"
CONF_EXTERNAL_FLUX_FILE_LOCATION = "fluxFileLocation"
CONF_GEOM = "geometry"
CONF_HOMOGBLOCK = "useHomogenizedBlockComposition"
CONF_INTERNAL_RINGS = "numInternalRings"
CONF_MERGE_INTO_CLAD = "mergeIntoClad"
CONF_MERGE_INTO_FUEL = "mergeIntoFuel"
CONF_MESH_PER_CM = "meshSubdivisionsPerCm"
CONF_REACTION_DRIVER = "nuclideReactionDriver"
CONF_XSID = "xsID"
CONF_XS_EXECUTE_EXCLUSIVE = "xsExecuteExclusive"
CONF_XS_PRIORITY = "xsPriority"
CONF_COMPONENT_AVERAGING = "averageByComponent"
CONF_XS_MAX_ATOM_NUMBER = "xsMaxAtomNumber"
CONF_MIN_DRIVER_DENSITY = "minDriverDensity"
CONF_DUCT_HETEROGENEOUS = "ductHeterogeneous"
CONF_TRACE_ISOTOPE_THRESHOLD = "traceIsotopeThreshold"
CONF_XS_TEMP_ISOTOPE = "xsTempIsotope"


class XSGeometryTypes(Enum):
    """
    Data structure for storing the available geometry options
    within the framework.
    """

    ZERO_DIMENSIONAL = 1
    ONE_DIMENSIONAL_SLAB = 2
    ONE_DIMENSIONAL_CYLINDER = 4
    TWO_DIMENSIONAL_HEX = 8

    @classmethod
    def _mapping(cls):
        mapping = {
            cls.ZERO_DIMENSIONAL: "0D",
            cls.ONE_DIMENSIONAL_SLAB: "1D slab",
            cls.ONE_DIMENSIONAL_CYLINDER: "1D cylinder",
            cls.TWO_DIMENSIONAL_HEX: "2D hex",
        }
        return mapping

    @classmethod
    def getStr(cls, typeSpec: Enum):
        """
        Return a string representation of the given ``typeSpec``.

        Examples
        --------
            XSGeometryTypes.getStr(XSGeometryTypes.ZERO_DIMENSIONAL) == "0D"
            XSGeometryTypes.getStr(XSGeometryTypes.TWO_DIMENSIONAL_HEX) == "2D hex"
        """
        geometryTypes = list(cls)
        if typeSpec not in geometryTypes:
            raise TypeError(f"{typeSpec} not in {geometryTypes}")
        return cls._mapping()[cls[typeSpec.name]]


XS_GEOM_TYPES = {
    XSGeometryTypes.getStr(XSGeometryTypes.ZERO_DIMENSIONAL),
    XSGeometryTypes.getStr(XSGeometryTypes.ONE_DIMENSIONAL_SLAB),
    XSGeometryTypes.getStr(XSGeometryTypes.ONE_DIMENSIONAL_CYLINDER),
    XSGeometryTypes.getStr(XSGeometryTypes.TWO_DIMENSIONAL_HEX),
}

# This dictionary defines the valid set of inputs based on
# the geometry type within the ``XSModelingOptions``
_VALID_INPUTS_BY_GEOMETRY_TYPE = {
    XSGeometryTypes.getStr(XSGeometryTypes.ZERO_DIMENSIONAL): {
        CONF_XSID,
        CONF_GEOM,
        CONF_BUCKLING,
        CONF_DRIVER,
        CONF_BLOCKTYPES,
        CONF_BLOCK_REPRESENTATION,
        CONF_EXTERNAL_FLUX_FILE_LOCATION,
        CONF_COMPONENT_AVERAGING,
        CONF_XS_EXECUTE_EXCLUSIVE,
        CONF_XS_PRIORITY,
        CONF_XS_MAX_ATOM_NUMBER,
        CONF_XS_TEMP_ISOTOPE,
    },
    XSGeometryTypes.getStr(XSGeometryTypes.ONE_DIMENSIONAL_SLAB): {
        CONF_XSID,
        CONF_GEOM,
        CONF_MESH_PER_CM,
        CONF_BLOCKTYPES,
        CONF_BLOCK_REPRESENTATION,
        CONF_EXTERNAL_FLUX_FILE_LOCATION,
        CONF_COMPONENT_AVERAGING,
        CONF_XS_EXECUTE_EXCLUSIVE,
        CONF_XS_PRIORITY,
        CONF_XS_MAX_ATOM_NUMBER,
        CONF_MIN_DRIVER_DENSITY,
        CONF_XS_TEMP_ISOTOPE,
    },
    XSGeometryTypes.getStr(XSGeometryTypes.ONE_DIMENSIONAL_CYLINDER): {
        CONF_XSID,
        CONF_GEOM,
        CONF_MERGE_INTO_CLAD,
        CONF_MERGE_INTO_FUEL,
        CONF_DRIVER,
        CONF_HOMOGBLOCK,
        CONF_INTERNAL_RINGS,
        CONF_EXTERNAL_RINGS,
        CONF_MESH_PER_CM,
        CONF_BLOCKTYPES,
        CONF_BLOCK_REPRESENTATION,
        CONF_EXTERNAL_FLUX_FILE_LOCATION,
        CONF_COMPONENT_AVERAGING,
        CONF_XS_EXECUTE_EXCLUSIVE,
        CONF_XS_PRIORITY,
        CONF_XS_MAX_ATOM_NUMBER,
        CONF_MIN_DRIVER_DENSITY,
        CONF_DUCT_HETEROGENEOUS,
        CONF_TRACE_ISOTOPE_THRESHOLD,
        CONF_XS_TEMP_ISOTOPE,
    },
    XSGeometryTypes.getStr(XSGeometryTypes.TWO_DIMENSIONAL_HEX): {
        CONF_XSID,
        CONF_GEOM,
        CONF_BUCKLING,
        CONF_EXTERNAL_DRIVER,
        CONF_DRIVER,
        CONF_REACTION_DRIVER,
        CONF_EXTERNAL_RINGS,
        CONF_BLOCK_REPRESENTATION,
        CONF_EXTERNAL_FLUX_FILE_LOCATION,
        CONF_COMPONENT_AVERAGING,
        CONF_XS_EXECUTE_EXCLUSIVE,
        CONF_XS_PRIORITY,
        CONF_XS_MAX_ATOM_NUMBER,
        CONF_MIN_DRIVER_DENSITY,
        CONF_XS_TEMP_ISOTOPE,
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
        vol.Optional(CONF_MERGE_INTO_FUEL): [str],
        vol.Optional(CONF_XS_FILE_LOCATION): [str],
        vol.Optional(CONF_EXTERNAL_FLUX_FILE_LOCATION): str,
        vol.Optional(CONF_MESH_PER_CM): vol.Coerce(float),
        vol.Optional(CONF_XS_EXECUTE_EXCLUSIVE): bool,
        vol.Optional(CONF_XS_PRIORITY): vol.Coerce(float),
        vol.Optional(CONF_XS_MAX_ATOM_NUMBER): vol.Coerce(int),
        vol.Optional(CONF_MIN_DRIVER_DENSITY): vol.Coerce(float),
        vol.Optional(CONF_COMPONENT_AVERAGING): bool,
        vol.Optional(CONF_DUCT_HETEROGENEOUS): bool,
        vol.Optional(CONF_TRACE_ISOTOPE_THRESHOLD): vol.Coerce(float),
        vol.Optional(CONF_XS_TEMP_ISOTOPE): str,
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
        1. If ``AA`` and ``AB`` exist, but ``AC`` is created, then the intended behavior
           is that ``AC`` settings will be set to the settings in ``AA``.

        2. If only ``YZ`` exists and ``YA`` is created, then the intended behavior is that
           ``YA`` settings will NOT be set to the settings in ``YZ``

        3. Requirements for using the existing cross section settings:

           a.  The existing XS ID must match the current XS ID.
           b.  The current xs burnup group must be larger than the lowest burnup group for the
               existing XS ID
           c.  If 3a. and 3b. are not met, then the default cross section settings will be
               set for the current XS ID

        """
        if xsID in self:
            return dict.__getitem__(self, xsID)

        # exact key not present so give lowest env group key, eg AA or BA as the source for
        # settings since users do not typically provide all combinations of second chars explicitly
        xsType = xsID[0]
        envGroup = xsID[1]
        existingXsOpts = [xsOpt for xsOpt in self.values() if xsOpt.xsType == xsType and xsOpt.envGroup < envGroup]

        if not any(existingXsOpts):
            return self._getDefault(xsID)

        else:
            return sorted(existingXsOpts, key=lambda xsOpt: xsOpt.envGroup)[0]

    def setDefaults(self, blockRepresentation, validBlockTypes):
        """
        Set defaults for current and future xsIDs based user settings.

        This must be delayed after read-time since the settings affecting this may not be loaded yet and could still be
        at their own defaults when this input is being processed. Thus, defaults are set at a later time.

        Parameters
        ----------
        blockRepresentation : str
            Valid options are provided in ``CrossSectionGroupManager.BLOCK_COLLECTIONS``
        validBlockTypes : list of str or bool
           This configures which blocks (by their type) the cross section group manager will merge together to create a
           representative block. If set to ``None`` or ``True`` then all block types in the XS ID will be considered. If
           set to ``False`` then a default of ["fuel"] will be used. If set to a list of strings then the specific list
           will be used. A typical input may be ["fuel"] to just consider the fuel blocks.

        See Also
        --------
        armi.physics.neutronics.crossSectionGroupManager.CrossSectionGroupManager.interactBOL : calls this
        """
        self._blockRepresentation = blockRepresentation
        self._validBlockTypes = validBlockTypes
        for _xsId, xsOpt in self.items():
            xsOpt.setDefaults(blockRepresentation, validBlockTypes)
            xsOpt.validate()

    def _getDefault(self, xsID):
        """
        Process the optional ``crossSectionControl`` setting.

        This input allows users to override global defaults for specific cross section IDs (xsID).

        To simplify downstream handling of the various XS controls, we build a full data structure here
        that should fully define the settings for each individual cross section ID.
        """
        # Only check since the state of the underlying cross section dictionary does not
        # get broadcasted to worker nodes. This check is only relevant for the first time
        # this is called and when called by the head node.
        if context.MPI_RANK == 0:
            if self._blockRepresentation is None:
                raise ValueError(
                    f"The defaults of {self} have not been set. Call ``setDefaults`` first "
                    "before attempting to add a new XS ID."
                )

        xsOpt = XSModelingOptions(xsID, geometry=XSGeometryTypes.getStr(XSGeometryTypes.ZERO_DIMENSIONAL))
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
        this assigned xsID. This is required if the ``xsFileLocation``
        attribute is not provided. This cannot be set if the ``xsFileLocation``
        is provided.

    xsFileLocation: list of str or None
        This should be a list of paths where the cross sections for this
        xsID can be copied from. This is required if the ``geometry``
        attribute is not provided. This cannot be set if the ``geometry``
        is provided.

    fluxFileLocation: str or None
        This should be a path where a pre-calculated flux solution
        for this xsID can be copied from. The ``geometry`` attribute
        must be provided with this input.

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

    mergeIntoFuel : list of str
        This is a lattice physics configuration option that is a list of component
        names to merge into a "fuel" component. This is highly-design specific
        and is sometimes used to merge a "gap" or low-density region into
        a "fuel" region to avoid numerical issues.

    meshSubdivisionsPerCm : float
        This is a lattice physics configuration option that can be used to control
        subregion meshing of the representative block in 1D problems.

    xsExecuteExclusive : bool
        The mpi task that results from this xsID will reserve a full processor and
        no others will allocate to it. This is useful for time balancing when you
        have one task that takes much longer than the others.

    xsPriority: int
        The priority of the mpi tasks that results from this xsID. Lower priority
        will execute first. starting longer jobs first is generally more efficient.

    xsMaxAtomNumber : int
        The maximum atom number to model for infinite dilute isotopes in lattice physics.
        This is used to avoid modeling isotopes with a large atomic number
        (e.g., fission products) as a depletion product of an isotope with a much
        smaller atomic number.

    averageByComponent: bool
        Controls whether the representative block averaging is performed on a
        component-by-component basis or on the block as a whole. If True, the
        resulting representative block will have component compositions that
        largely reflect those of the underlying blocks in the collection. If
        False, the number densities of some nuclides in the individual
        components may not be reflective of those of the underlying components
        due to the block number density "dehomogenization".

    minDriverDensity: float
        The minimum number density for nuclides included in driver material for a 1D
        lattice physics model.

    ductHeterogeneous : bool
        This is a lattice physics configuration option used to enable a partially
        heterogeneous approximation for a 1D cylindrical model. Everything inside of the
        duct will be treated as homogeneous.

    traceIsotopeThreshold : float
        This is a lattice physics configuration option used to enable a separate 0D fuel
        cross section calculation for trace fission products when using a 1D cross section
        model. This can significantly reduce the memory and run time required for the 1D
        model. The setting takes a float value that represents the number density cutoff
        for isotopes to be considered "trace". If no value is provided, the default is 0.0.

    xsTempIsotope: str
        The isotope whose temperature is interrogated when placing a block in a temperature cross section group.
        See `tempGroups`. "U238" is default since it tends to be dominant doppler isotope in most reactors.

    requiredRAM: float
        The amount of available memory needed by MC2 to run this cross section model.

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
        xsFileLocation=None,
        fluxFileLocation=None,
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
        mergeIntoFuel=None,
        meshSubdivisionsPerCm=None,
        xsExecuteExclusive=None,
        xsPriority=None,
        xsMaxAtomNumber=None,
        averageByComponent=False,
        minDriverDensity=0.0,
        ductHeterogeneous=False,
        traceIsotopeThreshold=0.0,
        xsTempIsotope="U238",
        requiredRAM=40.0,
    ):
        self.xsID = xsID
        self.geometry = geometry
        self.xsFileLocation = xsFileLocation
        self.validBlockTypes = validBlockTypes
        self.blockRepresentation = blockRepresentation

        # These are application specific, feel free use them
        # in your own lattice physics plugin(s).
        self.fluxFileLocation = fluxFileLocation
        self.driverID = driverID
        self.criticalBuckling = criticalBuckling
        self.nuclideReactionDriver = nuclideReactionDriver
        self.externalDriver = externalDriver
        self.useHomogenizedBlockComposition = useHomogenizedBlockComposition
        self.numInternalRings = numInternalRings
        self.numExternalRings = numExternalRings
        self.mergeIntoClad = mergeIntoClad
        self.mergeIntoFuel = mergeIntoFuel
        self.meshSubdivisionsPerCm = meshSubdivisionsPerCm
        self.xsMaxAtomNumber = xsMaxAtomNumber
        self.minDriverDensity = minDriverDensity
        self.averageByComponent = averageByComponent
        self.ductHeterogeneous = ductHeterogeneous
        self.traceIsotopeThreshold = traceIsotopeThreshold
        # these are related to execution
        self.xsExecuteExclusive = xsExecuteExclusive
        self.xsPriority = xsPriority
        self.xsTempIsotope = xsTempIsotope
        self.requiredRAM = requiredRAM

    def __repr__(self):
        if self.xsIsPregenerated:
            suffix = f"Pregenerated: {self.xsIsPregenerated}"
        else:
            suffix = f"Geometry Model: {self.geometry}"
            if self.fluxIsPregenerated:
                suffix = f"{suffix}, External Flux Solution: {self.fluxFileLocation}"

        return f"<{self.__class__.__name__}, XSID: {self.xsID}, {suffix}>"

    def __iter__(self):
        return iter(self.__dict__.items())

    @property
    def xsType(self):
        """Return the single-char cross section type indicator."""
        return self.xsID[0]

    @property
    def envGroup(self):
        """Return the single-char burnup group indicator."""
        return self.xsID[1]

    @property
    def xsIsPregenerated(self):
        """True if this points to a pre-generated XS file."""
        return self.xsFileLocation is not None

    @property
    def fluxIsPregenerated(self):
        """True if this points to a pre-generated flux solution file."""
        return self.fluxFileLocation is not None

    def serialize(self):
        """Return as a dictionary without ``CONF_XSID`` and with ``None`` values excluded."""
        doNotSerialize = [CONF_XSID]
        return {key: val for key, val in self if key not in doNotSerialize and val is not None}

    def validate(self):
        """
        Performs validation checks on the inputs and provides warnings for option inconsistencies.

        Raises
        ------
        ValueError
            When the mutually exclusive ``xsFileLocation`` and ``geometry`` attributes
            are provided or when neither are provided.
        """
        # Check for valid inputs when the file location is supplied.
        if self.xsFileLocation:
            if self.geometry is not None:
                runLog.warning(
                    f"Either file location or geometry inputs in {self} should be given, but not both. "
                    "The file location setting will take precedence over the geometry inputs. "
                    "Remove one or the other in the `crossSectionSettings` input to fix this warning."
                )

        if self.xsFileLocation is None or self.fluxFileLocation is not None:
            if self.geometry is None:
                raise ValueError(f"{self} is missing a geometry input or a file location.")

        invalids = []
        if self.xsFileLocation is not None:
            for var, val in self:
                # Skip these attributes since they are valid options
                # when the ``xsFileLocation`` attribute`` is set.
                if var in [CONF_XSID, CONF_XS_FILE_LOCATION, CONF_BLOCK_REPRESENTATION]:
                    continue
                if val is not None:
                    invalids.append((var, val))

        if invalids:
            runLog.debug(f"The following inputs in {self} are not valid when the file location is set:")
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
            runLog.debug(f"The following inputs in {self} are not valid when `{self.geometry}` geometry type is set:")
            for var, val in invalids:
                runLog.debug(f"\tAttribute: {var}, Value: {val}")
            runLog.debug(f"The valid options for the `{self.geometry}` geometry are: {validOptions}")

    def setDefaults(self, blockRepresentation, validBlockTypes):
        """
        This sets the defaults based on some recommended values based on the geometry type.

        Parameters
        ----------
        blockRepresentation : str
            Valid options are provided in ``CrossSectionGroupManager.BLOCK_COLLECTIONS``
        validBlockTypes : list of str or bool
           This configures which blocks (by their type) the cross section group manager will merge together to create a
           representative block. If set to ``None`` or ``True`` then all block types in the XS ID will be considered. If
           set to ``False`` then a default of ["fuel"] will be used. If set to a list of strings then the specific list
           will be used. A typical input may be ["fuel"] to just consider the fuel blocks.

        Notes
        -----
        These defaults are application-specific and design specific. They are included to provide an example and are
        tuned to fit the internal needs of TerraPower. Consider a separate implementation/subclass if you would like
        different behavior.
        """
        if type(validBlockTypes) is bool:
            validBlockTypes = None if validBlockTypes else ["fuel"]
        else:
            validBlockTypes = validBlockTypes

        defaults = {}
        if self.xsIsPregenerated:
            allowableBlockCollections = [
                crossSectionGroupManager.MEDIAN_BLOCK_COLLECTION,
                crossSectionGroupManager.AVERAGE_BLOCK_COLLECTION,
                crossSectionGroupManager.FLUX_WEIGHTED_AVERAGE_BLOCK_COLLECTION,
            ]
            defaults = {
                CONF_XS_FILE_LOCATION: self.xsFileLocation,
                CONF_BLOCK_REPRESENTATION: blockRepresentation,
            }

        elif self.geometry == XSGeometryTypes.getStr(XSGeometryTypes.ZERO_DIMENSIONAL):
            allowableBlockCollections = [
                crossSectionGroupManager.MEDIAN_BLOCK_COLLECTION,
                crossSectionGroupManager.AVERAGE_BLOCK_COLLECTION,
                crossSectionGroupManager.FLUX_WEIGHTED_AVERAGE_BLOCK_COLLECTION,
            ]
            bucklingSearch = not self.fluxIsPregenerated
            defaults = {
                CONF_GEOM: self.geometry,
                CONF_BUCKLING: bucklingSearch,
                CONF_DRIVER: "",
                CONF_BLOCK_REPRESENTATION: blockRepresentation,
                CONF_BLOCKTYPES: validBlockTypes,
                CONF_EXTERNAL_FLUX_FILE_LOCATION: self.fluxFileLocation,
            }
        elif self.geometry == XSGeometryTypes.getStr(XSGeometryTypes.ONE_DIMENSIONAL_SLAB):
            allowableBlockCollections = [
                crossSectionGroupManager.SLAB_COMPONENTS_BLOCK_COLLECTION,
            ]
            defaults = {
                CONF_GEOM: self.geometry,
                CONF_MESH_PER_CM: 1.0,
                CONF_BLOCK_REPRESENTATION: crossSectionGroupManager.SLAB_COMPONENTS_BLOCK_COLLECTION,
                CONF_BLOCKTYPES: validBlockTypes,
            }
        elif self.geometry == XSGeometryTypes.getStr(XSGeometryTypes.ONE_DIMENSIONAL_CYLINDER):
            allowableBlockCollections = [crossSectionGroupManager.CYLINDRICAL_COMPONENTS_BLOCK_COLLECTION]
            defaults = {
                CONF_GEOM: self.geometry,
                CONF_DRIVER: "",
                CONF_MERGE_INTO_CLAD: ["gap"],
                CONF_MERGE_INTO_FUEL: [],
                CONF_MESH_PER_CM: 1.0,
                CONF_INTERNAL_RINGS: 0,
                CONF_EXTERNAL_RINGS: 1,
                CONF_HOMOGBLOCK: False,
                CONF_BLOCK_REPRESENTATION: crossSectionGroupManager.CYLINDRICAL_COMPONENTS_BLOCK_COLLECTION,
                CONF_BLOCKTYPES: validBlockTypes,
                CONF_DUCT_HETEROGENEOUS: False,
                CONF_TRACE_ISOTOPE_THRESHOLD: 0.0,
            }
        elif self.geometry == XSGeometryTypes.getStr(XSGeometryTypes.TWO_DIMENSIONAL_HEX):
            allowableBlockCollections = [
                crossSectionGroupManager.MEDIAN_BLOCK_COLLECTION,
                crossSectionGroupManager.AVERAGE_BLOCK_COLLECTION,
                crossSectionGroupManager.FLUX_WEIGHTED_AVERAGE_BLOCK_COLLECTION,
            ]
            defaults = {
                CONF_GEOM: self.geometry,
                CONF_BUCKLING: False,
                CONF_EXTERNAL_DRIVER: True,
                CONF_DRIVER: "",
                CONF_REACTION_DRIVER: None,
                CONF_EXTERNAL_RINGS: 1,
                CONF_BLOCK_REPRESENTATION: blockRepresentation,
            }

        defaults[CONF_XS_EXECUTE_EXCLUSIVE] = False
        defaults[CONF_XS_PRIORITY] = 5
        defaults[CONF_COMPONENT_AVERAGING] = False
        defaults[CONF_MEMORY_REQUIREMENT] = 40.0

        for attrName, defaultValue in defaults.items():
            currentValue = getattr(self, attrName)
            if currentValue is None:
                setattr(self, attrName, defaultValue)
            else:
                if attrName == CONF_BLOCK_REPRESENTATION:
                    if currentValue not in allowableBlockCollections:
                        raise ValueError(
                            f"Invalid block collection type `{currentValue}` assigned "
                            f"for {self.xsID}. Expected one of the "
                            f"following: {allowableBlockCollections}"
                        )

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
                config: confVal for config, confVal in xsOpts.items() if config != CONF_XSID and confVal is not None
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
