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

"""NOTE: This is currently in beta testing, and is not (yet) a replacement for uniformMesh.py"""

# pylint: disable = anomalous-backslash-in-string, invalid-name

import logging
from armi.reactor.flags import Flags

runLog = logging.getLogger(__name__)


class UniformMeshV2:
    """beta class for uniform mesh converter overhaul"""

    def __init__(self, core, primaryFlag: str, secondaryFlag: str):
        self.core = core
        self.primaryFlag = Flags.fromString(primaryFlag)
        self.secondaryFlag = Flags.fromString(secondaryFlag)
        self.uniformMesh = []

    def getCoreWideUniformMesh(self, printLikeBlkSmears: bool = False):
        """calculate core wide uniform mesh

        Parameters
        ----------
        printLikeBlkSmears : boolean, optional
            There may be inter-block smearing between similar/like blocks. E.g., fuel to fuel, plenum to plenum, etc.
            These smearing instances may be less important than dissimilar blocks (e.g., control to plenum,
            shield to fuel, fuel to plenum). This boolean controls whether or not the similar/like block
            smearing cases are printed.
        """
        runLog.info(
            "Getting uniform mesh for axially disjoint core... "
            "Inter-block material smearing report available via 'verbosity: debug'."
        )
        primaryAssems = []
        secondaryAssems = []
        otherAssems = []
        for a in self.core.getAssemblies():
            if a.hasFlags(self.primaryFlag):
                primaryAssems.append(a)
            elif a.hasFlags(self.secondaryFlag):
                secondaryAssems.append(a)
            else:
                otherAssems.append(a)

        # Overlay uniform meshes on each other for a core wide uniform mesh and check for smearing
        self.uniformMesh = _createUniformMeshCore(
            primaryAssemsToPreserve=primaryAssems,
            secondaryAssemsToPreserve=secondaryAssems,
            otherAssems=otherAssems,
        )

        runLog.debug(
            "Smearing Report For Primary Assemblies -- {0:s}".format(
                str(self.primaryFlag)
            )
        )
        self._checkForSmearing(primaryAssems, printLikeBlkSmears)

        runLog.debug(
            "Smearing Report For Secondary Assemblies -- {0:s}".format(
                str(self.secondaryFlag)
            )
        )
        self._checkForSmearing(secondaryAssems, printLikeBlkSmears)

    def applyCoreWideUniformMesh(self):
        """apply the core wide uniform mesh to the core"""
        runLog.info("Applying uniform mesh to reactor.core...")
        for assem in self.core.getChildren():
            uniAssem = self._updateAssemblyAxialMesh(assem)
            spatialLocator = assem.spatialLocator
            self.core.removeAssembly(assem, discharge=False)
            self.core.add(uniAssem, spatialLocator)

        # get new axial mesh with subMesh
        coreAxialMesh = self.core.findAllAxialMeshPoints()
        self.core.p.axialMesh = coreAxialMesh

    def _updateAssemblyAxialMesh(self, sourceAssembly):
        """apply calculated core-wise uniform mesh to assembly

        Parameters
        ----------
        sourceAssembly: :py:class:`Assembly <armi.reactor.assemblies.Assembly>` object
            ARMI assembly to be adjusted

        Returns
        -------
        uniAssm : :py:class:`Assembly <armi.reactor.assemblies.Assembly>` object
            a new assembly object that has self.uniformMesh applied to sourceAssembly

        Raises
        ------
        ValueError
            unexpected error in assembly.py::Assembly::getBlocksBetweenElevations. Usually means
            that zLower and zUpper are the same... Which isn't good.
        """
        # create a new assembly, a, that is the same type and contains the same params, grid, etc as sourceAssembly
        uniAssem = sourceAssembly.__class__(sourceAssembly.getType())
        uniAssem.setName(sourceAssembly.getName())
        for param in sourceAssembly.getParamNames():
            uniAssem.p[param] = sourceAssembly.p[param]
        uniAssem.spatialGrid = sourceAssembly.spatialGrid
        uniAssem.spatialGrid.armiObject = uniAssem

        zLower = 0
        for i, zUpper in enumerate(self.uniformMesh):
            overlappingBlockInfo = sourceAssembly.getBlocksBetweenElevations(
                zLower, zUpper
            )
            # This is not expected to occur given that the assembly mesh is consistent with
            # the blocks within it, but this is added for defensive programming and to
            # highlight a developer issue.
            if not overlappingBlockInfo:
                raise ValueError(
                    f"No blocks found between {zLower:.3f} and {zUpper:.3f} in {sourceAssembly}. "
                    f"This is a major bug that should be reported to the developers."
                )
            b = _createNewBlock(overlappingBlockInfo, zUpper - zLower)
            b.p.assemNum = uniAssem.p.assemNum
            b.name = b.makeName(uniAssem.p.assemNum, i)
            uniAssem.add(b)
            zLower = zUpper

        uniAssem.reestablishBlockOrder()
        uniAssem.calculateZCoords()

        return uniAssem

    def _checkForSmearing(self, aList: list, printLikeBlkSmears: bool):
        """indicate smearing by presence of block bounds that are not aligned with uniformMesh

        Parameters
        ----------
        aList : list, :py:class:`Assembly <armi.reactor.assemblies.Assembly>` object
            List of assemblies which uniformMesh would be applied; will or will not have inter-block smearing\
        printLikeBlkSmears : boolean
            There may be inter-block smearing between similar/like blocks. E.g., fuel to fuel, plenum to plenum, etc.
            These smearing instances may be less important than dissimilar blocks (e.g., control to plenum,
            shield to fuel, fuel to plenum). This boolean controls whether or not the similar/like block
            smearing cases are printed.
        """
        for a in aList:
            runLog.debug(
                "{0}...".format(a)  # pylint: disable=logging-format-interpolation
            )
            for i, _z in enumerate(self.uniformMesh):
                if i == 0:
                    bottom = 0.0
                else:
                    bottom = self.uniformMesh[i - 1]
                top = self.uniformMesh[i]
                overlap = a.getBlocksBetweenElevations(bottom, top)
                if len(overlap) > 1:
                    diffMaterialInBlocks = len(set(b.p.flags for b, _h in overlap)) > 1
                    if printLikeBlkSmears or diffMaterialInBlocks:
                        runLog.debug(
                            "    uniform mesh block {0}, ({1:.3f},{2:.3f})".format(
                                i, bottom, top
                            )
                        )
                        runLog.debug("    percent contribution \t block")
                        for b, val in overlap:
                            runLog.debug(
                                "    {0:9.2f}\t\t\t{1}".format(
                                    val / (top - bottom) * 100.0, b.p.flags
                                )
                            )


def _createNewBlock(overlappingBlockInfo: list, uniformHeight: float):
    """create new armi block from overlapping block info"""
    # get source block type
    heights = [h for _b, h in overlappingBlockInfo]
    blocks = [b for b, _h in overlappingBlockInfo]
    sourceBlk = blocks[heights.index(max(heights))]

    # create a new block, b, that is the same type and contains the same params, grid, etc as sourceBlk
    b = sourceBlk.__class__(sourceBlk.getType())
    for param in sourceBlk.getParamNames():
        b.p[param] = sourceBlk.p[param]
    for c in sourceBlk.getChildren():
        b.add(c.__copy__())
    b.spatialGrid = sourceBlk.spatialGrid
    b.p.axMesh = 1
    b.p.height = uniformHeight  # other z params get set in uniAssem.calculateZCoords
    b.clearCache()  # reset component volumes so that they are referenced to new height
    _setNumberDensitiesFromOverlaps(b, overlappingBlockInfo)

    return b


def _createUniformMeshCore(
    primaryAssemsToPreserve: list, secondaryAssemsToPreserve: list, otherAssems: list
):
    """using three sets of assemblies, create a core-wide uniform mesh

    Parameters
    ----------
    primaryAssemsToPreserve: list, :py:class:`Assembly <armi.reactor.assemblies.Assembly>` object.
        list of assemblies that will be given top priority for resolving axial mesh discrepancies
    secondaryAssemsToPreserve: list, :py:class:`Assembly <armi.reactor.assemblies.Assembly>` object.
        list of assemblies that will be given secondary priority for resolving axial mesh discrepancies
    otherAssems: list, :py:class:`Assembly <armi.reactor.assemblies.Assembly>` object.
        remaining assemblies in ARMI core that do not belong to primary or secondary categories

    Returns
    -------
    coreUniformMesh: list
        uniform axial mesh for reactor
    """
    # get uniformMesh for otherAssems
    uniformMeshOther = otherAssems[0].getAxialMesh()
    for assem in otherAssems:
        uniformMeshOther = _updateUniformMesh(assem.getAxialMesh(), uniformMeshOther)

    # get uniformMesh for secondaryAssemsToPreserve
    uniformMeshSecondaryPreserve = secondaryAssemsToPreserve[0].getAxialMesh()
    for assem in secondaryAssemsToPreserve:
        uniformMeshSecondaryPreserve = _updateUniformMesh(
            assem.getAxialMesh(), uniformMeshSecondaryPreserve
        )

    # get uniformMesh for primaryAssemsToPreserve
    uniformMeshPrimaryPreserve = primaryAssemsToPreserve[0].getAxialMesh()
    for assem in primaryAssemsToPreserve:
        uniformMeshPrimaryPreserve = _updateUniformMesh(
            assem.getAxialMesh(), uniformMeshPrimaryPreserve
        )

    # overlay uniformMeshSecondaryPreserve on uniformMeshOther
    coreUniformMesh = _updateUniformMesh(
        uniformMeshSecondaryPreserve, uniformMeshOther, preserve=True
    )

    # overlay uniformMeshPrimaryPreserve on uniformMeshSecondaryPreserve
    coreUniformMesh = _updateUniformMesh(
        uniformMeshPrimaryPreserve, coreUniformMesh, preserve=True
    )

    return coreUniformMesh


def _updateUniformMesh(
    assemAxialMesh: list, currentUniformMesh: list, preserve: bool = False
):
    """update currentUniformMesh given assembly, assem

    Parameters
    ----------
    assemAxialMesh : list, float
        axial mesh of :py:class:`Assembly <armi.reactor.assemblies.Assembly>` object
    currentUniformMesh : list, float
        the current uniform mesh
    preserve : bool, optional
        boolean to engage different behavior if assemAxialMesh is to be given priority for preservation

    Returns
    -------
    newMeshPoints : list, float
        the updated uniform mesh based on any discrepancies between currentUniformMesh
        and the axial mesh of assem
    """
    newMeshPoints = []
    ib, ia = 0, 0
    while ib < len(currentUniformMesh):
        diff = abs(currentUniformMesh[ib] - assemAxialMesh[ia])
        if 0 < diff < 1:
            if not preserve:
                # Average the mesh difference; will result in some inevitable material smearing.
                newMeshPoints.append(
                    (currentUniformMesh[ib] + assemAxialMesh[ia]) / 2.0
                )
            else:
                # choose mesh point for assembly that you want to preserve
                newMeshPoints.append(assemAxialMesh[ia])
            ib += 1
            ia += 1
        elif diff >= 1:
            # Difference is sufficient to add new mesh point.
            zLowerOpts = [currentUniformMesh[ib - 1], assemAxialMesh[ia - 1]]
            zUpperOpts = [currentUniformMesh[ib], assemAxialMesh[ia]]
            if ia == 0:
                zLowerOpts[1] = 0.0
            if ib == 0:
                zLowerOpts[0] = 0.0
            meshBetweenBlk = _getBlockBoundsBetweenElevation(
                assemAxialMesh,
                max(zLowerOpts),
                max(zUpperOpts),
            )
            if not meshBetweenBlk:
                newMeshPoints.append(currentUniformMesh[ib])
                ib += 1
            else:
                for val in meshBetweenBlk:
                    newMeshPoints.append(val)
                    ia += 1
        elif diff == 0:
            # Mesh points perfectly align.
            newMeshPoints.append(currentUniformMesh[ib])
            ib += 1
            ia += 1

    if preserve:
        _checkAxialMeshValidity(newMeshPoints, preservedMeshPoints=assemAxialMesh)
    else:
        _checkAxialMeshValidity(newMeshPoints)

    return newMeshPoints


def _checkAxialMeshValidity(axialMesh: list, preservedMeshPoints: list = None):
    """check validity of axialMesh (that each subsequent entry increases)

    Parameters
    ----------
    axialMesh : float, list
        the axialMesh to verify validity for.
    preservedMeshPoints: float, list, optional
        mesh points to use to resolve discrepancies (see notes for details)

    Notes
    -----
    - Validity is accounted for by checking that each subsequent axial mesh location
    is greater than the one before it.
    - a "discrepancy" is defined as cases in which the mesh points within axialMesh
    are found to be less than 1 cm. Discrepancies are only checked if preservedMeshPoints
    is not None.

    Raises
    ------
    RuntimeError
        an axial mesh point is less than the one before it
    RuntimeError
        neither axial mesh point being resolved is found in perservedMeshPoints
    """
    i = 0
    while i < (len(axialMesh) - 1):
        check = axialMesh[i + 1] - axialMesh[i]
        if check < 0:
            runLog.error(axialMesh)
            raise RuntimeError(
                "The values in axialMesh need to increase, this is not the case!"
            )
        if preservedMeshPoints is None:
            i += 1
        else:
            if check >= 1:
                i += 1
            elif 0 < check < 1:
                try:
                    preservedMeshPoints.index(axialMesh[i])
                    axialMesh.pop(i + 1)
                except ValueError:
                    try:
                        preservedMeshPoints.index(axialMesh[i + 1])
                        axialMesh.pop(i)
                    except ValueError as second:
                        raise RuntimeError(
                            "values {0} and {1} not found in preservedMeshPoints!".format(
                                axialMesh[i], axialMesh[i + 1]
                            )
                        ) from second


def _getBlockBoundsBetweenElevation(axialGrid: list, zLower: float, zUpper: float):
    """retrieve axial mesh values on axialGrid that fall between zLower and zUpper

    Parameters
    ----------
    axialGrid: list, float
        axial mesh/grid for a given :py:class:`Assembly <armi.reactor.assemblies.Assembly>` object
    zLower: float
        lower elevation bound (not necessarily associated with block bound)
    zUpper: float
        upper elevation bound (not necessarily associated with block bound)

    Notes
    -----
    - if axialGrid is within EPS of either zLower or zUpper, it is skipped

    Returns
    -------
    blkBndsBetweenElev: list
        a list of axial mesh values from axialGrid that fall between zLower and zUpper
    """
    EPS = 1e-3  # pylint: disable=invalid-name
    blkBndsBetweenElev = []
    for i in range(len(axialGrid[:-1])):
        if zLower < axialGrid[i] < zUpper:
            if axialGrid[i] - zLower < EPS:
                continue
            if zUpper - axialGrid[i] < EPS:
                continue
            blkBndsBetweenElev.append(axialGrid[i])
        elif axialGrid[i] > zUpper:
            break

    return blkBndsBetweenElev


def _setNumberDensitiesFromOverlaps(block, overlappingBlockInfo):
    """
    Set number densities on a block based on overlapping blocks

    Notes
    -----
    A conservation of number of atoms technique is used to map the non-uniform number densities onto the uniform
    neutronics mesh. When the number density of a height :math:`H` neutronics mesh block :math:`N^{\prime}` is
    being computed from one or more blocks in the ARMI mesh with number densities :math:`N_i` and
    heights :math:`h_i`, the following formula is used:

    .. math::

        N^{\prime} =  \sum_i N_i \frac{h_i}{H}

    NOTE: yes, this is a copy from armi.reactor.converters.uniformMesh; the intent is that it will be carried over
          when the original uniformMesh gets replaced.

    See Also
    --------
    _setStateFromOverlaps : does this for state other than number densities.
    """
    totalDensities = {}
    block.clearNumberDensities()
    blockHeightInCm = block.getHeight()
    for overlappingBlock, overlappingHeightInCm in overlappingBlockInfo:
        for nucName, numberDensity in overlappingBlock.getNumberDensities().items():
            totalDensities[nucName] = (
                totalDensities.get(nucName, 0.0)
                + numberDensity * overlappingHeightInCm / blockHeightInCm
            )
    block.setNumberDensities(totalDensities)
