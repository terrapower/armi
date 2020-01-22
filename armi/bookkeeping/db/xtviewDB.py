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
The old database implementation, which XTView still knows how to read.

Until XTView is updated to speak the new database format, this will need to be
maintained to allow conversions between database formats and visualization.
"""
# pylint: disable=too-many-public-methods

import copy
import math
import io
import os
import re
from typing import Tuple, Generator
import traceback
import itertools

import numpy

import armi
from armi import runLog
from armi import settings
from armi import utils
from armi.bookkeeping import db
from armi.nucDirectory import nucDir
from armi.nucDirectory import nuclideBases
from armi.reactor import reactors
from armi.reactor import blocks
from armi.reactor import assemblies
from armi.reactor import locations
from armi.reactor import parameters
from armi.reactor import geometry
from armi.reactor.flags import Flags
from armi.utils import exceptions

import h5py


class XTViewDatabase:
    """The contract interface class for database subclasses

    Please be aware that decorated parent class methods
    lose their decoration when overridden (unless directly invoked).

    """

    _NONE_ATTR = "has_value"
    _JAGGED_ATTR = "array_sizes"
    version = "2"

    def __init__(self, fName, permission):
        """Lowest level of common attributes between database implementors

        Parameters
        ----------
        permission : tuple of string value and set containing accepted strings

        """
        self._hdf_file = h5py.File(fName, permission)
        self._name = os.path.abspath(fName)
        # perform rudimentary set up methods during normal method calls
        self._initDatabaseContact = True
        self._numTimeSteps = -1  # updated with property call
        self._numberDensityParamNames = None
        # necessary for writing blocks in the correct ordering
        self._frozenBlockOrder = None
        # An associated reactor object to support the load() interface. Isn't really
        # needed for anything else
        self._reactor = None

    def __repr__(self):
        return "<{} {}>".format(
            self.__class__.__name__,
            repr(self._hdf_file).replace("<", "").replace(">", ""),
        )

    def __enter__(self):
        """Context management support"""
        return self

    def __exit__(self, _type, _value, _traceback):
        """Typically we don't care why it broke but we want the DB to close"""
        self.close()

    def __del__(self):
        """Unreliable trash collection behavior to try to ensure disconnecting works

        When possible use the context management __enter__ and __exit__ which are better guarantees.
        """
        self.close()

    def close(self):
        """Close the HDF file"""
        self._hdf_file.close()

    def loadCS(self):
        from armi import settings

        cs = settings.Settings()
        cs.caseTitle = os.path.splitext(os.path.basename(self._hdf_file.filename))[0]
        cs.loadFromString(self._hdf_file["inputs/settings"][()])
        return cs

    def loadBlueprints(self):
        from armi.reactor import blueprints

        stream = io.StringIO(self._hdf_file["inputs/blueprints"][()])
        stream = blueprints.Blueprints.migrate(stream)
        bp = blueprints.Blueprints.load(stream)

        return bp

    def loadGeometry(self):
        from armi.reactor import geometry

        geom = geometry.SystemLayoutInput()
        geomData = self._hdf_file["inputs/geomFile"][()]
        if isinstance(geomData, bytes):
            # different versions of the code may have outputted these differently,
            # possibly when using using python2, or possibly from different versions of
            # h5py handling strings differently.
            geomData = geomData.decode()
        geom.readGeomFromStream(io.StringIO(geomData))
        return geom

    def load(self, cycle, node, cs=None, bp=None, geom=None):
        cs = cs or self.loadCS()
        settings.setMasterCs(cs)
        bp = bp or self.loadBlueprints()
        geom = geom or self.loadGeometry()

        if self._reactor is None:
            self._reactor = reactors.factory(cs, bp, geom)

        dbTimeStep = utils.getTimeStepNum(cycle, node, cs)

        self.updateFromDB(self._reactor, dbTimeStep)

        return self._reactor

    def writeToDB(self, reactor, statePointName=None):
        """
        Puts self.r in the database.

        Parameters
        ----------
        statePointName: str, optional
            explicit name of the state point to be written. A state point is not
            necessarily a cycle or time node, it may make the most sense to simply think
            of it as a label for the current state.
        """
        if self._initDatabaseContact:
            self._createDBSchema(reactor)
            self._initDatabaseContact = False

        if statePointName:
            statePointName = statePointName
        else:
            # check for None instead of truth since these may be 0
            cycle = reactor.p.cycle
            node = reactor.p.timeNode
            statePointName = utils.getTimeStepNum(cycle, node, settings.getMasterCs())

        self._writeReactorParams(reactor, statePointName)
        self._writeAssemblyParams(reactor, statePointName)
        self._writeBlockParams(reactor, statePointName)
        self._writeComponentParams(reactor, statePointName)

        self._numTimeSteps = -1  # update numTimeSteps attribute

    def writeInputsToDB(self, cs, csString=None, geomString=None, bpString=None):
        """
        Write inputs into the database based the CaseSettings.

        This is not DRY on purpose. The goal is that any particular Database
        implementation should be very stable, so we dont want it to be easy to change
        one Database implementation's behavior when trying to change another's.

        Notes
        -----
        This is hard-coded to read the entire file contents into memory and write that
        directly into the database. We could have the cs/blueprints/geom write to a
        string, however the ARMI log file contains a hash of each files' contents. In
        the future, we will be able to reproduce calculation showing that the inputs are
        identical.
        """
        if csString is None:
            with open(cs.path, "r") as fileStream:
                csString = fileStream.read()

        if geomString is None:
            with open(
                os.path.join(os.path.dirname(cs.path), cs["geomFile"]), "r"
            ) as fileStream:
                geomString = fileStream.read()

        if bpString is None:
            with open(
                os.path.join(os.path.dirname(cs.path), cs["loadingFile"]), "r"
            ) as fileStream:
                bpString = fileStream.read()

        self._hdf_file["inputs/settings"] = csString
        self._hdf_file["inputs/geomFile"] = geomString
        self._hdf_file["inputs/blueprints"] = bpString

    def readInputsFromDB(self):
        return (
            self._hdf_file["inputs/settings"][()],
            self._hdf_file["inputs/geomFile"][()],
            self._hdf_file["inputs/blueprints"][()],
        )

    def updateFromDB(self, reactor, dbTimeStep, updateIndividualAssemblyNumbers=True):
        r"""Reads in the state from the database

        Performs necessary schema loads on the data to get it integrated in properly.
        Meaning several things:
        * Reads each block param from the DB and sets each block to the
          corresponding value
        * Reads each reactor param from the DB and sets them
        * Handles some special params like b.p.type, b.p.assemType, and xsTypeNum
          to actually set the types
        * Applies the temperatures from the DB to the components in the blocks,
          updating the thermal expansion, etc.
        * Sets the number densities of all nXXX-type parameters, updating the
          component mass fractions
        * Updates assembly-level parameters like maxpercentBu
        * Updates block heights and makes sure all assemblies are consistent
          heights.

        Parameters
        ----------
        reactor : reactor object
            The ARMI reactor to update from current db
        dbTimeStep : int
            The timestep (starting at 0) to load from db
        updateIndividualAssemblyNumbers : bool, optional
            If True, will update assembly numbers of all assemblies on loading. This in
            turn affects their name. Turn this off if you are analyzing previous
            timesteps of a run (such as EOL safety) so you don't interfere with
            assemblies that are already in the SFP.

        Raises
        ------
        ValueError
            If the requested time step is not present in the database, or if some
            parameters cannot be processed correctly
        """
        runLog.info(
            "Updating {} state at time step {} from {} ".format(
                reactor, dbTimeStep, repr(self)
            )
        )
        try:
            timesteps = self.getAllTimesteps()
        except exceptions.NoDataModelInDatabaseException:
            timesteps = []
        if not dbTimeStep in timesteps:
            raise ValueError(
                "Cannot load from {} at timestep {}. There are {} valid timesteps."
                "".format(repr(self), dbTimeStep, self._numTimeSteps)
            )

        # make a block list ordered based on the DB location order at this time.
        blockList = reactor.core.getLocationContents(self.lookupGeometry())

        # reset this so we make sure to get one off the DB
        setParameterWithRenaming(reactor.core, "maxAssemNum", None)

        blockParamNames = set(self.getBlockParamNames())

        # these get read manually/individually
        blockParamNames -= {"ztop", "zbottom"}

        # preload the types of assemblies and blocks to ensure that geometry changes
        # (ducts and control rod changes) are correctly accounted for by replacing blocks
        self._updateAssemblyTypeFromDB(reactor, dbTimeStep)
        self._updateBlockTypeFromDB(reactor, blockList, dbTimeStep)
        self._updateAxialMesh(reactor, blockList, dbTimeStep)
        self._updateReactorParams(reactor, dbTimeStep)

        self._updateAssemblyParams(reactor, dbTimeStep)

        self._updateBlockParamsFromDB(blockList, blockParamNames, dbTimeStep)
        self._setInputComponentTemperatures(reactor)
        self._updateMassFractionsFromParamValues(reactor, blockParamNames, blockList)
        self._applyTemperaturesToComponents(reactor)
        self._updateBondFractions(reactor)

        self._numTimeSteps = -1  # update numTimeSteps attribute

        reactor.core.regenAssemblyLists()
        runLog.info("After load, keff is {}".format(reactor.core.p.keff))

    @property
    def numberDensityParamNames(self):
        """Return a set containing the number density parameter definition names"""
        if not self._numberDensityParamNames:
            # check for an old or new type of xsStyle from loading
            ndensParams = [nn.getDatabaseName() for nn in nucDir.getNuclides()]
            self._numberDensityParamNames = set(ndensParams)
        return self._numberDensityParamNames

    def _updateAssemblyTypeFromDB(self, reactor, dbTimeStep):
        """Updates assemblies in reactor if database says its a different type"""
        assemTypes = self.readAssemblyParam("type", dbTimeStep)
        rings = self.readAssemblyParam("Ring", dbTimeStep)
        positions = self.readAssemblyParam("Pos", dbTimeStep)
        grid = reactor.core.spatialGrid
        for assemType, i, j in zip(assemTypes, rings, positions):
            loc = grid.getLocationFromRingAndPos(i, j)
            a = reactor.core.childrenByLocator[loc]
            a.setType(assemType)

    def _updateBlockTypeFromDB(self, reactor, blockList, dbTimeStep):
        """Updates blocks in reactor if database says its a different type of block"""
        dataList = self.readBlockParam("type", dbTimeStep)

        for blockTypeInDB, b in zip(dataList, blockList):
            oldBType = b.getType()

            if blockTypeInDB != oldBType:
                a = b.parent
                bolAssem = reactor.blueprints.assemblies.get(a.getType(), None)
                if not bolAssem:
                    raise RuntimeError(
                        "No BOL assem of type {0} exists in the input.".format(
                            a.getType()
                        )
                    )
                newBlock = bolAssem.getFirstBlockByType(blockTypeInDB)
                if not newBlock:
                    raise RuntimeError(
                        "Could not find a {0} block in {1}. Not updating block type.".format(
                            blockTypeInDB, a
                        )
                    )
                else:
                    newBlock = copy.deepcopy(newBlock)
                    runLog.extra(
                        "Updating block {} with BOL block: {} because the block type "
                        "changed from {} to {}".format(
                            b, newBlock, oldBType, blockTypeInDB
                        )
                    )
                    b.replaceBlockWithBlock(newBlock)

    def _updateBlockParamsFromDB(self, blockList, paramList, dbTimeStep):
        """Read block params and apply them to each block"""

        for b in blockList:
            b.clearCache()

        for param in paramList:
            if param == "TimeStep":
                continue
            runLog.debug("Reading block param {0}".format(param))

            dataList = self.readBlockParam(param, dbTimeStep)

            if (  # pylint: disable=len-as-condition; required for numpy
                dataList is None or len(dataList) == 0
            ):
                # the parameter was not stored in the DB
                continue

            if len(blockList) != len(dataList):
                raise RuntimeError(
                    "When loading `{}` from the database, the number of blocks ({}) "
                    "does not match the available data ({})".format(
                        param, len(blockList), len(dataList)
                    )
                )

            for i, b in enumerate(blockList):
                val = dataList[i]

                if param == "percentBu":
                    b.p.basePBu = val

                elif param in self.numberDensityParamNames:
                    # number density param.
                    if i == 0:
                        # on the first block, translate old style names to new style names.
                        # We restrict to the first block only because we can't extract
                        # the nuclide name from an already-extracted nuclide name.
                        nucName = param[1:].upper()
                        try:
                            newParam = nucDir.getNuclide(nucName).getDatabaseName()
                        except AttributeError:
                            raise RuntimeError(
                                "nuc name {} could not be found".format(nucName)
                            )
                        param = newParam

                setParameterWithRenaming(b, param, val)

    def _updateReactorParams(self, reactor, dbTimeStep):
        """Update reactor-/core-level parameters from the database"""
        # These are the names present in the reactors section of the DB
        dbParamNames = self.getReactorParamNames()

        reactorNames = set(
            pDef.name for pDef in parameters.ALL_DEFINITIONS.forType(reactors.Reactor)
        )
        coreNames = set(
            pDef.name for pDef in parameters.ALL_DEFINITIONS.forType(reactors.Core)
        )

        for paramName in dbParamNames:
            if paramName == "TimeStep":
                continue
            runLog.debug("Reading scalar {0}".format(paramName))
            # get time-ordered list of scalar vals. Pick the relevant one.
            val = self.readReactorParam(paramName, dbTimeStep)[0]
            if val is parameters.NoDefault:
                continue
            if paramName in ["cycle", "timeNode"]:
                # int(float('0.000E+00')) works, but int('0.00E+00')
                val = int(float(val))
            if paramName in reactorNames:
                reactor.p[paramName] = val
            elif paramName in coreNames:
                reactor.core.p[paramName] = val
            else:
                runLog.warning(
                    'The parameter "{}" was present in the database, but is not '
                    "recognized as a Reactor or Core parameter".format(paramName)
                )

    def _updateAssemblyParams(self, reactor, dbTimeStep):
        """Update assembly-level parameters (and name) from the database"""
        runLog.debug("Reading assembly-level params of all assemblies")
        # an assembly-level param table exists. Load from it.
        loadAssemParamsFromDB = True
        assemParams = self.getAssemblyParamNames()
        for removal in ["RowID", "spatialLocator.indices"]:
            if removal in assemParams:
                assemParams.remove(
                    removal
                )  # take out the DB primary so as to not set it.

        assemParamData = self.readMultipleAssemblyParam(
            dbTimeStep, assemParams
        )  # pylint: disable=no-member
        for a in reactor.core.getAssemblies():
            if loadAssemParamsFromDB:
                ring, pos = a.spatialLocator.getRingPos()
                for assemParamName in assemParams:
                    val = assemParamData[assemParamName, ring, pos]
                    setParameterWithRenaming(a, assemParamName, val)

                    if assemParamName == "assemNum" and val:
                        # update assembly name based on assemNum
                        name = a.makeNameFromAssemNum(val)
                        a.name = name
                        a.renameBlocksAccordingToAssemblyNum()

    @staticmethod
    def _applyTemperaturesToComponents(reactor):
        """Update temperatures of block components now that densities have been set.

        Thermally expand them if there's coupled TH

        Useful only if the case is being loaded from did NOT have coupled T/H.

        See Also
        --------
        _setInputComponentTemperatures : deals with loading from coupled TH cases

        """
        from terrapower.physics.thermalHydraulics import thutils

        if (
            settings.getMasterCs()["useInputTemperaturesOnDBLoad"]
            and reactor.o.couplingIsActive()
        ):
            thutils.applyTemperaturesToComponents(reactor)

    @staticmethod
    def _setInputComponentTemperatures(reactor):
        """Update all materials to their proper temperatures.

        If we are doing a coupled T/H case but the case we're loading from did not have
        T/H coupling activated, then its composition was written to DB based on
        user-input temperatures. Thus, they should be read from these temps as well so
        as to factor out thermal expansion. :py:meth:`_applyTemperaturesToComponents`
        will do the proper coupled T/H expansion after the load.

        On the other hand, if the case we're loading from did have coupled T/H
        activated, then we must apply the proper temperatures/thermal
        expansion/dimensions BEFORE loading the number densities and then there will be
        nothing to do after the load.

        """
        from terrapower.physics.thermalHydraulics import thutils

        thutils.applyTemperaturesToComponents(reactor, updateDensityParams=False)

    @staticmethod
    def _updateMassFractionsFromParamValues(reactor, blockParamNames, blockList):
        """
        Set the block densities based on the already-updated n block-params.

        The DB reads in params that represent the nuclide densities on each block,
        but they cannot be applied to the component until the temperatures are updated.

        """
        runLog.info("Updating component mass fractions from DB params")
        # Set all number densities on a block at a time so we don't have to compute volume fractions N times.
        allNucNamesInProblem = set(reactor.blueprints.allNuclidesInProblem)
        allNucBasesInProblem = {
            nuclideBases.byName[nucName] for nucName in allNucNamesInProblem
        }
        nucBasesInBlockParams = {
            nb for nb in allNucBasesInProblem if nb.getDatabaseName() in blockParamNames
        }

        if settings.getMasterCs()["zeroOutNuclidesNotInDB"]:
            nucBasesNotInBlockParams = allNucBasesInProblem - nucBasesInBlockParams
            zeroOut = {nb.getDatabaseName(): 0.0 for nb in nucBasesNotInBlockParams}
            if zeroOut:
                runLog.important(
                    "Zeroing out {0} because they are not in the db.".format(
                        nucBasesNotInBlockParams
                    )
                )
        else:
            zeroOut = {}

        for b in blockList:
            ndens = {
                nuc.name: b.p[nuc.getDatabaseName()] for nuc in nucBasesInBlockParams
            }
            ndens.update(zeroOut)
            # apply all non-zero number densities no matter what.
            # zero it out if it was already there and is now set to zero.
            ndens = {
                name: val
                for name, val in ndens.items()
                if val or name in set(b.getNuclides())
            }
            b.setNumberDensities(ndens)

        allNucsNamesInDB = {
            nuclideBases.nucNameFromDBName(paramName)
            for paramName in blockParamNames.intersection(nuclideBases.byDBName.keys())
        }
        nucNamesInDataBaseButNotProblem = allNucsNamesInDB - allNucNamesInProblem
        for nucName in nucNamesInDataBaseButNotProblem:
            runLog.warning(
                "Nuclide {0} exists in the database but not the problem. It is being ignored"
                "".format(nucName)
            )

    def _updateAxialMesh(self, reactor, blockList, dbTimeStep):
        """
        Update block heights and reactor axial mesh based on block param values in database.

        This must be done before the number densities are read in so the dimensions of
        the core are consistent.

        The refAssem writes the neutronics mesh. This method is necessary  in case the
        refAssem has been removed. Assume all fuel assemblies have the same mesh unless
        there is ``detailedAxialExpansion``.

        Mass must be conserved of the fuel, even in the BOL assemblies, especially if
        shuffling and depletion is to occur after loading.
        """
        ztops = self.readBlockParam("ztop", dbTimeStep)
        zbottoms = self.readBlockParam("zbottom", dbTimeStep)
        # can't use setBlockHeights here because of the arbitrary order of the blockList
        for block, ztop, zbottom in zip(blockList, ztops, zbottoms):
            block.p.height = ztop - zbottom  # avoid N^2 loop
            block.clearCache()  # update volume
        for a in reactor.core:
            a.calculateZCoords()

        reactor.core.updateAxialMesh()

    @staticmethod
    def _updateBondFractions(reactor):
        """Move the coolant into the proper components as directed by fuel performance

        after loading from DB, coolant density is distributed evenly over all components
        containing this material (e.g. sodium in bond, coolant, intercoolant).
        But if bond removal was happening, we need to move it out of the bond
        according to the bondRemoved param.
        """
        for b in reactor.core.getBlocks(Flags.FUEL):
            b.enforceBondRemovalFraction(b.p.bondRemoved)

    def lookupGeometry(self):
        """
        Read the order that block data is stored in BLOBs from the database

        Returns
        -------
        locationList : list
            List of location strings in the order that block params are packed into BLOBs
        """
        locList = []
        for locationUniqNumber, locationTypeName in self._getLocationOrder():
            location = locations.locationFactory(locationTypeName)()
            location.fromUniqueInt(locationUniqNumber)
            locList.append(str(location))

        return locList

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        self._name = os.path.abspath(value)

    def _create_1d_datasets(self, name, data):  # pylint: disable=too-many-branches
        """Qualified name of group1/group2/.../groupN/dataset and data dictionary to be stored

        Stores each dictionary key as its own dataset corresponding to an array of values

        All None's are stripped out and represented by a positional marking attribute on the generated dataset.
        This is because None's are an incompatible python object with HDF's more primitive datatypes and this
        was deemed the most elegant solution.

        If the input structures contain lists or ndarrays they're treated as if they could contain jagged lengths
        which is similarly incompatible as it casts the dtype of the stored array to the impossible "object" dtype.
        The jagged arrays are padded out and the real length stored in the marking attribute.

        To maintain fidelity with input data, any generated datasets
        should be read out by the accompanying reader method ``_get_1d_dataset``

        """
        for key, values in data.items():
            try:
                cur_name = r"{}/{}".format(name, key)

                nones = any(value is None for value in values)
                if nones:
                    hasValue = numpy.array([value is not None for value in values])
                    values = [value for value in values if not value is None]

                jagged = False
                if len(values) != 0 and isinstance(  # pylint: disable=len-as-condition
                    values[0], (list, numpy.ndarray)
                ):
                    # deal with list or array values
                    lengths = [len(v) for v in values]
                    jagged = any(length != lengths[0] for length in lengths)
                    if jagged:
                        values = [list(v) for v in values]
                        padTo = max(lengths)
                        dummyValue = next(
                            iter(v[0] for l, v in zip(lengths, values) if l != 0)
                        )
                        # use of a dummyValue b/c some lists in need of padding may not have their own element
                        # to pad with
                        for _l, _v in zip(lengths, values):
                            _v.extend([dummyValue] * (padTo - _l))

                    convertedValues = []
                    for valueItem in values:
                        convertedValueItem = numpy.array(valueItem)
                        if convertedValueItem.dtype.kind == "U":
                            # hdf5 can't handle unicode arrays. Convert to bytes
                            convertedValueItem = convertedValueItem.astype("S")
                        convertedValues.append(convertedValueItem)
                    values = convertedValues
                else:
                    # handle values that are just unicode (such as xsType)
                    values = numpy.array(values)
                    if values.dtype.kind == "U":
                        # hdf5 can't handle unicode arrays. Convert to bytes
                        values = values.astype("S")

                try:
                    self._hdf_file.create_dataset(
                        cur_name, data=values, compression="gzip"
                    )
                except RuntimeError:
                    # this can happen when updating an existing dataset.
                    del self._hdf_file[cur_name]
                    self._hdf_file.create_dataset(
                        cur_name, data=values, compression="gzip"
                    )
                except TypeError:
                    runLog.error(
                        "Failed to coerce data for {} into HDF5 dataset.".format(
                            cur_name
                        )
                    )
                    raise

                if nones:
                    self._hdf_file[cur_name].attrs[self._NONE_ATTR] = hasValue
                if jagged:
                    self._hdf_file[cur_name].attrs[self._JAGGED_ATTR] = lengths
            except:  # pylint: disable=broad-except
                traceback.print_exc()  # print actual traceback and then add more info
                if hasattr(values, "dtype"):
                    tp = values.dtype
                else:
                    tp = type(values)
                raise ValueError(
                    "Cannot write to database for parameter '{}' with values: {}\n\n"
                    "Please ensure the data are well-formed and consistently typed (they are {})..".format(
                        key, values, tp
                    )
                )

    def _createParamDatasets(  # pylint: disable=too-many-branches
        self, timeStepName, armiObjects
    ):
        """Qualified name of group1/group2/.../groupN/dataset and data dictionary to be
        stored

        Stores each dictionary key as its own dataset corresponding to an array of
        values

        All None's are stripped out and represented by a positional marking attribute on
        the generated dataset.  This is because None's are an incompatible python object
        with HDF's more primitive datatypes and this was deemed the most elegant
        solution.

        If the input structures contain lists or ndarrays they're treated as if they
        could contain jagged lengths which is similarly incompatible as it casts the
        dtype of the stored array to the impossible "object" dtype.  The jagged arrays
        are padded out and the real length stored in the marking attribute.

        To maintain fidelity with input data, any generated datasets should be read out
        by the accompanying reader method ``_get_1d_dataset``
        """
        compType = type(armiObjects[0])

        paramDefs = armiObjects[0].p.paramDefs.toWriteToDB(parameters.SINCE_ANYTHING)
        for paramDef in paramDefs:
            datasetName = r"{}/{}".format(timeStepName, paramDef.name)

            try:
                paramName = paramDef.name  # quick lookup
                values = []
                hasValue = numpy.repeat(True, len(armiObjects))

                for ic, armiObject in enumerate(armiObjects):
                    val = armiObject.p.get(paramName, paramDef.default)
                    if val is None or val is parameters.NoDefault:
                        hasValue[ic] = False
                    else:
                        values.append(val)

                jagged = False
                if values and isinstance(values[0], (list, numpy.ndarray)):
                    lengths = [len(v) for v in values]
                    jagged = any(l != lengths[0] for l in lengths)
                    if jagged:
                        values = [list(v) for v in values]
                        padTo = max(lengths)
                        dummyValue = next(
                            iter(v[0] for l, v in zip(lengths, values) if l != 0)
                        )
                        # use of a dummyValue b/c some lists in need of padding may not have their own element
                        # to pad with
                        for _l, _v in zip(lengths, values):
                            _v.extend([dummyValue] * (padTo - _l))
                    convertedValues = []
                    for valueItem in values:
                        convertedValueItem = numpy.array(valueItem)
                        if convertedValueItem.dtype.kind == "U":
                            # hdf5 can't handle unicode arrays. Convert to bytes
                            convertedValueItem = convertedValueItem.astype("S")
                        convertedValues.append(convertedValueItem)
                    values = convertedValues
                else:
                    # handle values that are just unicode (such as xsType)
                    values = numpy.array(values)
                    if values.dtype.kind == "U":
                        # hdf5 can't handle unicode arrays. Convert to bytes
                        values = values.astype("S")

                try:
                    self._hdf_file.create_dataset(
                        datasetName, data=values, compression="gzip"
                    )
                except RuntimeError:
                    # HDF5 does not delete from disk
                    del self._hdf_file[datasetName]
                    self._hdf_file.create_dataset(
                        datasetName, data=values, compression="gzip"
                    )

                paramDef.assigned &= ~parameters.SINCE_LAST_DB_TRANSMISSION

                if not all(hasValue):
                    self._hdf_file[datasetName].attrs[self._NONE_ATTR] = hasValue

                if jagged:
                    self._hdf_file[datasetName].attrs[self._JAGGED_ATTR] = lengths

            except Exception as e:  # pylint: disable=broad-except, invalid-name
                if type(armiObjects[0] is reactors.Core and paramName == "serialNum"):
                    continue
                traceback.print_exc()  # print actual traceback and then add more info
                runLog.error("Caught exception: {}".format(e))
                raise ValueError(
                    "Cannot write to database for parameter '{}' ({}) with values: {}\n\n"
                    "Please ensure the data are well-formed and consistently typed.".format(
                        paramDef, datasetName, values
                    )
                )

    def _get_1d_dataset(self, name):
        """
        Read a dataset out of the HDF file.

        Information properly put into the file through ``_create_1d_datasets``
        will require going through this method.

        Jagged reconstruction and UTF-8 is handled first so we can skip the logic needed
        to make Nones play well with the code.

        """
        try:
            dataset = self._hdf_file[name]
        except KeyError:
            runLog.warning(
                "Database lookup for {} failed, returning None.".format(name)
            )
            return None

        data = dataset[()]
        # All hdf5 data in in the form of numpy arrays at first. Great time to convert
        # bytes to UTF
        if data.dtype.kind == "S":
            # convert bytes back to unicode strings
            data = data.astype("U")

        # update byte strings to unicode for list/array values
        if len(data) != 0 and isinstance(  # pylint: disable=len-as-condition
            data[0], (list, numpy.ndarray)
        ):
            convertedValues = []
            for di in data:
                if di.dtype.kind == "S":
                    di = di.astype("U")
                convertedValues.append(di)
            data = numpy.array(convertedValues)

        # load it all out of memory, which is important for performance with block data
        data = data.tolist()

        nones = self._NONE_ATTR in dataset.attrs
        jagged = self._JAGGED_ATTR in dataset.attrs

        if not nones and not jagged:
            return numpy.array(data)

        if jagged:
            data = numpy.array(
                [
                    value[:end]
                    for value, end in zip(data, dataset.attrs[self._JAGGED_ATTR])
                ]
            )
        if nones:
            values = iter(data)
            data = numpy.array(
                [
                    next(values) if hasValue else None
                    for hasValue in dataset.attrs[self._NONE_ATTR]
                ]
            )

        return data

    def _writeReactorParams(self, reactor, timeStep):
        """Writing reactor parameter info

        For now, this fuses the Reactor and Core parameter collections into the
        'reactor/#' group.  This avoids modifying the database schema and breaking
        compatibility with external tools.  Previously, there was no such thing as a
        Core, so most Core parameters were originally on the Reactor object, which is
        why the database only has a `/reactor` group. At some point it will become
        necessary to split these, but it will be a painful enough process that we should
        be confident that we have appropriately classified the Core/Reactor parameters
        before doing so.
        """
        runLog.extra(
            "Writing at time step {} assembly parameter info for {}".format(
                timeStep, reactor
            )
        )
        self._createParamDatasets("{}/reactors".format(timeStep), [reactor])
        self._createParamDatasets("{}/reactors".format(timeStep), [reactor.core])

    def _writeAssemblyParams(self, reactor, timeStep):
        """Writing assembly parameter info"""
        runLog.extra(
            "Writing at time step {} assembly parameter info for {}".format(
                timeStep, reactor
            )
        )
        self._createParamDatasets("{}/assemblies".format(timeStep), list(reactor.core))
        assemblyRingPos = {}
        assemblyRingPos["Ring"] = []
        assemblyRingPos["Pos"] = []

        for a in reactor.core:
            ring, pos = a.spatialLocator.getRingPos()
            assemblyRingPos["Ring"].append(ring)
            assemblyRingPos["Pos"].append(pos)

        self._create_1d_datasets("{}/assemblies".format(timeStep), assemblyRingPos)

    def _writeBlockParams(self, reactor, timeStep):
        """Writing block parameter info"""
        runLog.extra(
            "Writing at time step {} block parameter info for {}".format(
                timeStep, reactor
            )
        )
        blocks = reactor.core.getBlocksByIndices(self._frozenBlockOrder)
        self._createParamDatasets("{}/blocks".format(timeStep), blocks)

    def _writeComponentParams(self, reactor, timeStep):
        """Writing component parameter info"""
        pass

    def _createDBSchema(self, reactor):
        # block order will change across the run, the geometry table won't
        self._frozenBlockOrder = [
            b.spatialLocator.getCompleteIndices() for b in reactor.core.getBlocks()
        ]

        stale_entries = [
            key
            for key in self._hdf_file.keys()
            if re.match(r"(Geometry|Materials)", key)
        ]
        if stale_entries:
            runLog.extra(
                "DB not empty for clean schema creation. Clearing {}".format(
                    stale_entries
                )
            )
            self.clear(stale_entries)
        runLog.extra("Creating DB schema tables for {}".format(repr(self)))

        self._createGeometryDataFrame(reactor)
        self._createMaterialsDataFrame(reactor)

    def _createGeometryDataFrame(self, r):
        geom = None
        for block in r.core.getBlocksByIndices(self._frozenBlockOrder):
            geom = gatherGeomData(geom, block)
        self._create_1d_datasets("Geometry", geom)

    def _createMaterialsDataFrame(self, r):
        mats = {"Material": [], "BlobIndex": []}
        # need to get core grid because it is a HexGrid (for hex reactor)
        coreGrid = r.core.spatialGrid
        for i, block in enumerate(r.core.getBlocksByIndices(self._frozenBlockOrder)):
            loc = block.spatialLocator
            ring, pos = coreGrid.getRingPos(loc.getCompleteIndices())
            uniqueInt = ring * 100000 + pos * 100 + loc.k
            mats["Material"].append(uniqueInt)
            mats["BlobIndex"].append(i)
        self._create_1d_datasets("Materials", mats)

    def getAllTimesteps(self):
        timesteps = sorted(
            [int(key) for key in self._hdf_file.keys() if re.match(r"\d+", key)]
        )

        return timesteps

    def genTimeSteps(self):
        timeInts = self.getAllTimesteps()
        cs = self.loadCS()
        for ti in timeInts:
            yield utils.getCycleNode(ti, cs)

    def genAuxiliaryData(self, ts: Tuple[int, int]) -> Generator[str, None, None]:
        cycle, node = ts
        cs = self.loadCS()
        tn = utils.getTimeStepNum(cycle, node, cs)
        specialKeys = {"reactors", "blocks", "assemblies"}
        return (
            str(tn) + "/" + key
            for key in self._hdf_file[str(tn)].keys()
            if key not in specialKeys
        )

    def getAuxiliaryDataPath(self, ts: Tuple[int, int], name: str) -> str:
        cycle, node = ts
        cs = self.loadCS()
        tn = utils.getTimeStepNum(cycle, node, cs)
        return str(tn) + "/" + name

    def _getParamNames(self, objName):
        # TODO: add a set of names as attributes somewhere so it's reliably exhaustive?
        # using the last TS currently to get all parameters defined, iterating across
        # each entry is way too slow
        # TODO: should allow a specific TS lookup in the case of loadState
        last_ts = self.getAllTimesteps()[-1]
        return list(self._hdf_file["{}/{}".format(last_ts, objName)].keys())

    def getReactorParamNames(self):
        return self._getParamNames("reactors")

    def _readReactorParams(self, param, ts):
        return self._readParams("reactors", param, ts)

    def readReactorParam(self, param, ts=None):
        """Read reactor param at all or one timesteps."""
        timesteps = [ts] if ts is not None else self.getAllTimesteps()
        # need to try both since Reactor and Core are squashed in the DB.
        try:
            # pylint: disable=protected-access
            paramDef = reactors.Reactor.paramCollectionType.pDefs[param]
        except KeyError:
            # pylint: disable=protected-access
            try:
                paramDef = reactors.Core.paramCollectionType.pDefs[param]
            except KeyError:
                # Dead parameter?
                runLog.warning(
                    "Reactor/Core parameter `{}` was unrecognized and is being "
                    "ignored.".format(param)
                )

        all_vals = []
        for timestep in timesteps:
            value = self._get_1d_dataset("{}/reactors/{}".format(timestep, param))
            if value is not None:
                # unpack if there's a value (like if there's just one reactor)
                all_vals.append(value[0])
            else:
                # Go to the paramDef's default in case
                # it's not None (e.g. time default is 0.0)
                all_vals.append(paramDef.default)
        return all_vals

    def getAssemblyParamNames(self):
        return self._getParamNames("assemblies")

    def readMultipleAssemblyParam(self, ts, paramNames):
        """
        Read all assembly params into a (param, ring, pos) keyed dictionary.

        This is a faster alternative to calling ``readAssemblyParam`` many times.
        """
        paramNames = paramNames[:]  # since we'll modify it.
        assemParams = {}
        for paramName in paramNames + [
            "Ring",
            "Pos",
        ]:  # add non-param keys ring/pos to read list.
            assemParams[paramName] = self._get_1d_dataset(
                "{}/assemblies/{}".format(ts, paramName)
            )
            if assemParams[paramName] is None:
                assemParams[paramName] = itertools.cycle([None])

        assemParamsByAssem = {}
        for paramName in paramNames:
            for paramVal, ring, pos in zip(
                assemParams[paramName], assemParams["Ring"], assemParams["Pos"]
            ):
                assemParamsByAssem[paramName, ring, pos] = paramVal
        return assemParamsByAssem

    def getBlockParamNames(self):
        return self._getParamNames("blocks")

    def readBlockParam(self, param, ts):
        return self._get_1d_dataset("{}/blocks/{}".format(ts, param))

    def readAssemblyParam(self, param, ts):
        return self._get_1d_dataset("{}/assemblies/{}".format(ts, param))

    def _getLocationOrder(self):
        return zip(
            *[
                self._get_1d_dataset("Materials/Material"),
                self._get_1d_dataset("Geometry/Shape"),
            ]
        )


def setParameterWithRenaming(obj, parameter, value):
    """
    Set a parameter on an object, supporting renamed parameters.

    This allows older databases to work with newer ARMI versions if the parameter renames are
    properly recorded.
    """
    # Watch out, this might be slow if it isn't cached by the App
    renames = armi.getApp().getParamRenames()
    name = parameter

    while name in renames:
        name = renames[name]

    try:
        obj.p[name] = value
    except (parameters.UnknownParameterError, AssertionError):
        runLog.warning(
            "Incompatible database has unsupported parameter: "
            '"{}", and will be ignored!'.format(parameter),
            single=True,
        )


def gatherGeomData(geom, b):
    """Appends to the geometry table data

    Parameters
    ----------
    geom : list
        The list of geometry info that gets accumulated

    b : Block
        The block to read geom info from

    Returns
    -------
    geom : list
        The updated geom list

    """
    geom = geom or {
        "Cell": [],
        "Material": [],
        "x": [],
        "y": [],
        "z": [],
        "hx": [],
        "hy": [],
        "hz": [],
        "Shape": [],
    }

    x, y, z = b.spatialLocator.getGlobalCoordinates()
    if isinstance(b, blocks.CartesianBlock):
        xw, yw = b.getPitch()
        height = b.getHeight()

        if xw == 1.0:  # 1-D problem. scale it up.
            xw = height
            yw = height

        hx, hy, hz = xw, yw, height
        shape = geometry.REC_PRISM

    elif isinstance(b, blocks.ThRZBlock):
        hx = b.radialOuter() - b.radialInner()
        hy = b.thetaOuter() - b.thetaInner()
        hz = b.getHeight()
        shape = geometry.ANNULUS_SECTOR_PRISM
    else:
        pitch = b.getPitch()

        hx, hy, hz = numpy.NaN, pitch, b.getHeight()
        shape = geometry.HEX_PRISM

    loc = b.spatialLocator
    ring, pos = b.parent.parent.spatialGrid.getRingPos(loc.getCompleteIndices())
    uniqueInt = ring * 100000 + pos * 100 + loc.k
    geom["Cell"].append(uniqueInt)
    geom["Material"].append(uniqueInt)
    geom["x"].append(x)
    geom["y"].append(y)
    geom["z"].append(z)
    geom["hx"].append(hx)
    geom["hy"].append(hy)
    geom["hz"].append(hz)
    geom["Shape"].append(shape)

    return geom
