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
Mesh specifiers update the mesh structure of a reactor by increasing or decreasing the number of mesh coordinates.
"""

import math
import numpy

from armi import runLog
from armi.reactor import grids
from armi.reactor.flags import Flags, TypeSpec


class MeshConverter(object):
    """
    Base class for the reactor mesh conversions.
    
    Parameters
    ----------
    converterSettings : dict
        A set of str, value settings used in mesh conversion. Required
        settings are implementation specific.
    """

    def __init__(self, converterSettings: dict):
        self._converterSettings = converterSettings

    def generateMesh(self, r=None):
        raise NotImplementedError

    def writeMeshData(self):
        raise NotImplementedError


class RZThetaReactorMeshConverter(MeshConverter):
    """
    Handles mesh conversions for r-z-theta reactor geometries.

    Attributes
    ----------
    converterSettings: dict
        This is a dictionary of settings that are used for the RZThetaReactorMeshConverter.
        Required converter settings: ``uniformThetaMesh``,``thetaBins``

    See Also
    --------
    RZThetaReactorMeshConverterByRingCompositionAxialBins
    RZThetaReactorMeshConverterByRingCompositionAxialCoordinates
    """

    def __init__(self, converterSettings):
        MeshConverter.__init__(self, converterSettings)
        self._useUniformThetaMesh = None
        self._numThetaMeshBins = None
        self._axialSegsPerBin = None
        self._ringsPerBin = None
        self._numRingsInCore = None
        self._assemsInCore = None
        self._coreAxialMeshCoords = None
        self.radialMesh = None
        self.axialMesh = None
        self.thetaMesh = None
        self.numRingBins = None
        self.numAxialMeshBins = None
        self.numThetaMeshBins = None

    def generateMesh(self, r=None):
        core = r.core
        converterSettings = self._converterSettings
        self._useUniformThetaMesh = converterSettings["uniformThetaMesh"]
        self._numThetaMeshBins = converterSettings["thetaBins"]
        self._converterSettings = converterSettings
        self._numRingsInCore = core.getNumHexRings()
        self._assemsInCore = core.getAssemblies()
        self._coreAxialMeshCoords = core.findAllAxialMeshPoints(applySubMesh=False)
        self.setAxialMesh()
        self._checkAxialMeshList()
        self.setThetaMesh()
        self._checkThetaMeshList()
        self.setRingsToConvert(core)
        self._checkRingList(core)
        self.numRingBins = len(self.radialMesh)
        self.numAxialMeshBins = len(self.axialMesh)
        self.numThetaMeshBins = len(self.thetaMesh)
        self.writeMeshData()

        # Build mesh reactor mesh
        # thetaMesh doesn't include the zero point so add it back in.
        # axial mesh is handled on assemblies so make this 2-D.

        mesh = grids.ThetaRZGrid(
            bounds=([0.0] + self.thetaMesh, self.radialMesh, (0.0, 0.0))
        )
        return mesh

    def writeMeshData(self):
        """
        Write a summary table of the radial, axial, and theta bins that will be used for geometry conversion.

        Notes
        -----
        This should be on the ``ThetaRZGrid`` object.
        """
        binCombinations = (
            self.numRingBins * self.numAxialMeshBins * self.numThetaMeshBins
        )
        runLog.info("Total mesh bins (r, z, theta): {0}".format(binCombinations))
        runLog.info(
            "  Radial bins: {}\n"
            "  Axial bins:  {}\n"
            "  Theta bins:  {}".format(
                self.numRingBins, self.numAxialMeshBins, self.numThetaMeshBins
            )
        )
        self._writeMeshLogData()

    def _writeMeshLogData(self):
        self._logMeshData(self.radialMesh, "Radial ring indices:", "int")
        self._logMeshData(self.axialMesh, "Axial mesh coordinates:", "float")
        self._logMeshData(self.thetaMesh, "Theta mesh coordinates:", "float")

    def _logMeshData(self, listType, listName, listDataType):
        if listDataType == "float":
            listType = ["{:<8.3f}".format(floatValue) for floatValue in listType]
        runLog.extra("{0} {1}".format(listName, listType))

    def setRingsToConvert(self, core):
        raise NotImplementedError

    def setAxialMesh(self):
        raise NotImplementedError

    def setThetaMesh(self):
        """Generate a uniform theta mesh in radians."""
        if self._useUniformThetaMesh is None:
            raise ValueError(
                "useUniformThetaMesh setting was not specified in the converterSettings"
            )
        if self._numThetaMeshBins is None:
            raise ValueError("numThetaMeshBins were specified in the converterSettings")
        if self._useUniformThetaMesh:
            self._generateUniformThetaMesh()
        else:
            self._generateNonUniformThetaMesh()

    def _generateUniformThetaMesh(self):
        """Create a uniform theta mesh over 2*pi using the user specified number of theta bins."""
        self.thetaMesh = list(
            numpy.linspace(0, 2 * math.pi, self._numThetaMeshBins + 1)[1:]
        )

    def _generateNonUniformThetaMesh(self):
        raise NotImplementedError(
            "Non-uniform theta mesh not implemented. Use uniform theta mesh."
        )

    def _checkRingList(self, core):
        """Check for any errors in the radial rings."""
        minRingNum = 1
        self.radialMesh = sorted(self.radialMesh)
        rings = checkLastValueInList(
            self.radialMesh, "rings", self._numRingsInCore + 1, adjustLastValue=True
        )
        maxAssemsInOuterRing = core.getMaxAssembliesInHexRing(self._numRingsInCore)
        assemsInOuterRing = len(
            core.getAssembliesInSquareOrHexRing(self._numRingsInCore)
        )
        if (maxAssemsInOuterRing - assemsInOuterRing) > 0 and len(self.thetaMesh) > 1:
            self._combineLastTwoRadialBins()
        checkListBounds(rings, "rings", minRingNum, self._numRingsInCore + 1)

    def _combineLastTwoRadialBins(self):
        if (self.radialMesh[-1] - self.radialMesh[-2]) == 1:
            runLog.extra(
                "Outermost ring of the core {} is not fully filled and will be homogenized with the "
                "previous ring {}".format(self.radialMesh[-1], self.radialMesh[-2])
            )
            self.radialMesh.pop(-1)
            self.radialMesh.pop(-2)
            self.radialMesh.append(self.radialMesh[-1])

    def _checkAxialMeshList(self):
        """Check for errors in the axial mesh coordinates."""
        minAxialCoordInReactor = self._coreAxialMeshCoords[0]
        maxAxialCoordInReactor = self._coreAxialMeshCoords[-1]
        self.axialMesh = sorted(set(self.axialMesh))
        checkListBounds(
            self.axialMesh, "axialMesh", minAxialCoordInReactor, maxAxialCoordInReactor
        )
        self.axialMesh = checkLastValueInList(
            self.axialMesh, "axialMesh", maxAxialCoordInReactor, adjustLastValue=True
        )

    def _checkThetaMeshList(self):
        """Check for errors in the theta mesh coordinates."""
        self.thetaMesh = sorted(set(self.thetaMesh))
        checkListBounds(self.thetaMesh, "thetaMesh", 0.0, 2 * math.pi)
        self.thetaMesh = checkLastValueInList(self.thetaMesh, "axialMesh", 2 * math.pi)


class _RZThetaReactorMeshConverterByAxialCoordinates(RZThetaReactorMeshConverter):
    """Generate an axial mesh based on user provided axial mesh coordinates."""

    def setAxialMesh(self):
        """Set up the reactor's new radial rings based on a user-specified axial coordinate list (axial mesh)."""
        self.axialMesh = self._converterSettings["axialMesh"]


class _RZThetaReactorMeshConverterByAxialBins(RZThetaReactorMeshConverter):
    """
    Generate an axial mesh based on user provided axial bins.

    Notes
    -----
    The new mesh structure is formed by merging multiply "bins" together (i.e. numPerBin
    = 2 and the original mesh is [1, 2, 3, 4, 5, 6, 7, 8], the new mesh structure will
    be [2, 4, 6, 8]).
    """

    def setAxialMesh(self):
        """
        Set up axial mesh coordinates using user-specified number of axial segments per bins.

        Notes
        -----
        Example:
            Original core axial mesh list - [25.0, 50.0, 75.0, 100.0, 175.0] cm
            axialSegsPerBin = 2
            Merged core axial mesh list - [50.0, 100.0, 175.0] cm
        """
        self._axialSegsPerBin = self._converterSettings["axialSegsPerBin"]
        self._mergeAxialMeshByAxialSegsPerBin()

    def _mergeAxialMeshByAxialSegsPerBin(self):
        axialStartNum = 0
        totalAxialSegsInCore = len(self._coreAxialMeshCoords) - 1
        axialMeshIndices = generateBins(
            totalAxialSegsInCore, self._axialSegsPerBin, axialStartNum
        )
        self.axialMesh = [0] * len(axialMeshIndices)
        for axialMeshIndex, locIndex in enumerate(axialMeshIndices):
            self.axialMesh[axialMeshIndex] = self._coreAxialMeshCoords[locIndex]
        return self.axialMesh


class _RZThetaReactorMeshConverterByRingComposition(RZThetaReactorMeshConverter):
    """Generate a new mesh based on the radial compositions in the core."""

    def __init__(self, cs):
        RZThetaReactorMeshConverter.__init__(self, cs)
        self._ringCompositions = None

    def setRingsToConvert(self, core):
        """Set up the reactor's new radial rings based on the ring compositions (assembly types)."""
        self.radialMesh, self._ringCompositions = self._getCompositionTypesPerRing(core)

    def _getCompositionTypesPerRing(self, core):
        """Set composition of each ring in the reactor by the assembly type."""
        ringIndices = []
        ringCompositions = []
        numRings = [r for r in range(1, self._numRingsInCore + 1)]
        for _i, ring in enumerate(numRings):
            assemsInRing = core.getAssembliesInRing(ring)
            compsInRing = []
            for a in assemsInRing:
                assemType = a.getType().lower()
                if assemType not in compsInRing:
                    compsInRing.append(assemType)
            for c in compsInRing:
                ringIndices.append(ring + 1)
                ringCompositions.append(c)
        return ringIndices, ringCompositions

    def _checkRingList(self, core):
        """Check for initialization errors in the radial ring list provided by the user."""
        minRingNum = 1
        self.radialMesh = sorted(self.radialMesh)
        rings = checkLastValueInList(
            self.radialMesh, "rings", self._numRingsInCore + 1, adjustLastValue=True
        )
        checkListBounds(rings, "rings", minRingNum, self._numRingsInCore + 1)

    def _writeMeshLogData(self):
        radialIndices = [i + 1 for i in range(len(self.radialMesh))]
        self._logMeshData(radialIndices, "Radial ring indices:", "int")
        self._logMeshData(self._ringCompositions, "Radial ring compositions:", "str")
        self._logMeshData(self.axialMesh, "Axial mesh coordinates:", "float")
        self._logMeshData(self.thetaMesh, "Theta mesh coordinates:", "float")


class RZThetaReactorMeshConverterByRingCompositionAxialBins(
    _RZThetaReactorMeshConverterByRingComposition,
    _RZThetaReactorMeshConverterByAxialBins,
):
    """
    Generate a new mesh based on the radial compositions and axial bins in the core.

    See Also
    --------
    _RZThetaReactorMeshConverterByRingComposition
    _RZThetaReactorMeshConverterByAxialBins
    """

    pass


class RZThetaReactorMeshConverterByRingCompositionAxialCoordinates(
    _RZThetaReactorMeshConverterByRingComposition,
    _RZThetaReactorMeshConverterByAxialCoordinates,
):
    """
    Generate a new mesh based on the radial compositions and axial coordinates in the core.

    See Also
    --------
    _RZThetaReactorMeshConverterByRingComposition
    _RZThetaReactorMeshConverterByAxialCoordinates
    """

    pass


def checkLastValueInList(
    inputList, listName, expectedValue, eps=0.001, adjustLastValue=False
):
    """
    Check that the last value in the list is equal to the expected value within +/- eps
    """
    msg = "The last value in {} is {} and should be {}".format(
        listName, inputList[-1], expectedValue
    )
    if not numpy.isclose(inputList[-1], expectedValue, eps):
        if adjustLastValue:
            del inputList[-1]
            inputList.append(expectedValue)
            runLog.extra(msg)
            runLog.extra(
                "Updating {} in {} to {}".format(inputList[-1], listName, expectedValue)
            )
        else:
            raise ValueError(msg)
    return inputList


def checkListBounds(inputList, listName, minVal, maxVal, eps=0.001):
    """
    Ensure that each value in a list does not exceed the allowable bounds
    """
    for value in inputList:
        minDiff = value - minVal
        maxDiff = value - maxVal
        if minDiff < -eps or maxDiff > eps:
            raise ValueError(
                "Invalid values {} out of expected bounds {} to {}".format(
                    listName, minVal - eps, maxVal + eps
                )
            )


def generateBins(totalNumDataPoints, numPerBin, minNum):
    """
    Fill in a list based on the total number of data points and the number of data points per bin
    """
    listToFill = []
    if numPerBin >= totalNumDataPoints:
        listToFill.append(totalNumDataPoints)
    else:
        currentNum = 0
        while currentNum < totalNumDataPoints:
            currentNum += numPerBin
            if currentNum > totalNumDataPoints:
                currentNum = totalNumDataPoints
            if currentNum > minNum:
                listToFill.append(currentNum)
    return listToFill


class AxialExpansionModifier(MeshConverter):
    """
    Axially expand or contract a reactor.

    Useful for fuel performance, thermal expansion, reactivity coefficients, etc.
    """

    def __init__(self, percent, fuelLockedToClad=False, cs=None):
        """
        Build an axial expansion converter.

        Parameters
        ----------
        percent : float
            the desired axial expansion in percent. If negative, use special
            treatment of down-expanding

        fuelLockedToClad : bool
            Specify whether or not to conserve mass on structure due to
            the fuel being locked to the clad. Note: this should
            generally be set to False even if the fuel is locked to the clad
            because the duct will not be axially expanding.
        """
        MeshConverter.__init__(self, cs)
        self._percent = percent
        self._fuelLockedToClad = fuelLockedToClad

    def convert(self, r=None, converterSettings=None):
        """
        Perform an axial expansion of the core.

        Notes
        -----
        This loops through the fuel blocks, making their height larger by a fraction of
        maxPercent. It reduces the homogenized actinide number densities to conserve
        atoms.

        This is a first approximation, adjusting the whole core uniformly and adjusting
        fuel with structure and everything.

        When fuel is locked to clad, this only expands the actinides! So the structural
        materials and sodium stay as they are in terms of density. By growing the mesh,
        we are introducing NEW ATOMS of these guys, thus violating conservation of
        atoms. However, the new ones are effectively piled up on top of the reactor
        where they are neutronically uninteresting.  This approximates fuel movement
        without clad/duct movement.
        """
        adjustFlags = Flags.FUEL | Flags.CLAD if self._fuelLockedToClad else Flags.FUEL
        adjustList = getAxialExpansionNuclideAdjustList(r, adjustFlags)

        runLog.extra(
            "Conserving mass during axial expansion for: {0}".format(str(adjustList))
        )

        # plenum shrinks so we should just measure the fuel height.
        oldMesh = r.core.p.axialMesh
        for a in r.core.getAssemblies(includeBolAssems=True):
            a.axiallyExpand(self._percent, adjustList)

        r.core.p.axialExpansionPercent = self._percent

        if not self._converterSettings["detailedAxialExpansion"]:
            # loop through again now that the reference is adjusted and adjust the non-fuel assemblies.
            refAssem = r.core.getFirstAssembly(Flags.FUEL) or r.core.getFirstAssembly()
            axMesh = refAssem.getAxialMesh()
            for a in r.core.getAssemblies(includeBolAssems=True):
                # See ARMI Ticket #112 for explanation of the commented out code
                a.setBlockMesh(
                    axMesh
                )  # , conserveMassFlag=True, adjustList=adjustList)

        r.core.updateAxialMesh()  # floating point correction
        newMesh = r.core.p.axialMesh
        runLog.important(
            "Adjusted full core fuel axial mesh uniformly "
            "{0}% from {1} cm to {2} cm.".format(self._percent, oldMesh, newMesh)
        )


def getAxialExpansionNuclideAdjustList(r, componentFlags: TypeSpec = None):
    r"""
    Determine which nuclides should have their mass conserved during axial expansion

    Parameters
    ----------
    r : Reactor
        The Reactor object to search for nuclide instances
    componentFlags : TypeSpec, optional
        A type specification to use for filtering components that should conserve mass.
        If None, Flags.FUEL is used.


    """

    if componentFlags is None:
        componentFlags = [Flags.FUEL]

    adjustSet = {
        nuc
        for b in r.core.getBlocks()
        for c in b.getComponents(componentFlags)
        for nuc in c.getNuclides()
    }

    return list(adjustSet)
