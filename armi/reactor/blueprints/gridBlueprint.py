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
Input definitions for Grids.

Grids are given names which can be referred to on other input structures
(like core maps and pin maps).

These are in turn interpreted into concrete things at lower levels. For
example:

* Core map lattices get turned into :py:mod:`armi.reactor.grids`,
  which get set to ``core.spatialGrid``.
* Block pin map lattices get applied to the components to provide
  some subassembly spatial details

Lattice inputs here are floating in space. Specific dimensions
and anchor points are handled by the lower-level objects definitions. This
is intended to maximize lattice reusability.

See Also
--------
armi.utils.asciimaps
    Description of the ascii maps and their formats.

Examples
--------

    grids:
        control:
            geom: hex
            symmetry: full
            lattice map: |
               - - - - - - - - - 1 1 1 1 1 1 1 1 1 4
                - - - - - - - - 1 1 1 1 1 1 1 1 1 1 1
                 - - - - - - - 1 8 1 1 1 1 1 1 1 1 1 1
                  - - - - - - 1 1 1 1 1 1 1 1 1 1 1 1 1
                   - - - - - 1 1 1 1 1 1 1 1 1 1 1 1 1 1
                    - - - - 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1
                     - - - 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1
                      - - 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1
                       - 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1
                        7 1 1 1 1 1 1 1 1 0 1 1 1 1 1 1 1 1 1
                         1 1 1 1 1 1 1 1 2 1 1 1 1 1 1 1 1 1
                          1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1
                           1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1
                            1 1 1 1 1 1 1 1 1 1 1 1 1 1 1
                             1 1 1 1 1 1 1 1 1 1 1 1 1 1
                              1 1 1 1 1 1 1 1 1 3 1 1 1
                               1 1 1 1 1 1 1 1 1 1 1 1
                                1 6 1 1 1 1 1 1 1 1 1
                                 1 1 1 1 1 1 1 1 1 1
        sfp:
            geom: cartesian
            lattice pitch:
                x: 25.0
                y: 25.0
            lattice map: |
                2 2 2 2 2
                2 1 1 1 2
                2 1 3 1 2
                2 3 1 1 2
                2 2 2 2 2

        core:
            geom: hex
            symmetry: third periodic
            origin:
                x: 0.0
                y: 10.1
                z: 1.1
            lattice map: |
                -     SH   SH   SH
                -  SH   SH   SH   SH
                 SH   RR   RR   RR   SH
                   RR   RR   RR   RR   SH
                 RR   RR   RR   RR   RR   SH
                   RR   OC   OC   RR   RR   SH
                     OC   OC   OC   RR   RR   SH
                   OC   OC   OC   OC   RR   RR
                     OC   MC   OC   OC   RR   SH
                       MC   MC   PC   OC   RR   SH
                     MC   MC   MC   OC   OC   RR
                       MC   MC   MC   OC   RR   SH
                         PC   MC   MC   OC   RR   SH
                       MC   MC   MC   MC   OC   RR
                         IC   MC   MC   OC   RR   SH
                           IC   US   MC   OC   RR
                         IC   IC   MC   OC   RR   SH
                           IC   MC   MC   OC   RR
                         IC   IC   MC   PC   RR   SH

"""
import itertools

import yamlize

from armi.utils import asciimaps
from armi.reactor import geometry
from armi.reactor import grids
from armi import runLog
from .reactorBlueprint import Triplet


class GridBlueprint(yamlize.Object):
    """
    A grid input blueprint.

    These directly build Grid objects and contain information about
    how to populate the Grid with child ArmiObjects for the Reactor Model.

    The grids get origins either from a parent block (for pin lattices)
    or from a System (for Cores, SFPs, and other components).

    For backward compatibility, the geometry and grid can be
    alternatively read from a latticeFile (historically the geometry.xml file).

    Attributes
    ----------
    name : str
        The grid name
    geom : str
        The geometry of the grid (e.g. 'cartesian')
    latticeFile : str
        Path to input file containing just the lattice contents definition
    latticeMap : str
        An asciimap representation of the lattice contents
    latticeDimensions : Triplet
        An x/y/z dict with grid dimensions in cm
    symmetry : str
        A string defining the symmetry mode of the grid
    gridContents : dict
        A {(i,j): str} dictionary mapping spatialGrid indices
        in 2-D to string specifiers of what's supposed to be in the grid.

    """

    name = yamlize.Attribute(key="name", type=str)
    geom = yamlize.Attribute(key="geom", type=str, default=geometry.HEX)
    latticeFile = yamlize.Attribute(key="lattice file", type=str, default=None)
    latticeMap = yamlize.Attribute(key="lattice map", type=str, default=None)
    latticeDimensions = yamlize.Attribute(
        key="lattice pitch", type=Triplet, default=None
    )
    symmetry = yamlize.Attribute(
        key="symmetry", type=str, default=geometry.THIRD_CORE + geometry.PERIODIC
    )
    # gridContents is the final form of grid contents information;
    # it is set regardless of how the input is read. This is how all
    # grid contents information is written out.
    gridContents = yamlize.Attribute(key="grid contents", type=dict, default=None)

    def __init__(
        self,
        name=None,
        geom=geometry.HEX,
        latticeMap=None,
        latticeFile=None,
        symmetry=geometry.THIRD_CORE + geometry.PERIODIC,
        gridContents=None,
    ):
        """
        A Grid blueprint.

        Notes
        -----
        yamlize does not call an __init__ method, instead it uses __new__ and setattr
        this is only needed for when you want to make this object from a non-YAML source.

        .. warning:: This is a Yamlize object, so ``__init__`` never really gets called. Only
            ``__new__`` does.

        """
        self.name = name
        self.geom = geom
        self.latticeMap = latticeMap
        self.latticeFile = latticeFile
        self.symmetry = symmetry
        self.gridContents = gridContents
        self.eqPathInput = {}

    def construct(self):
        """Build a Grid from a grid definition."""
        self._readGridContents()
        grid = self._constructSpatialGrid()
        return grid

    def _constructSpatialGrid(self):
        """
        Build spatial grid.

        If you do not enter latticeDimensions, a unit grid will be produced
        which must be adjusted to the proper dimensions (often
        by inspection of children) at a later time.
        """
        geom = self.geom
        maxIndex = self._getMaxIndex()
        runLog.extra("Creating the spatial grid")
        if geom in [geometry.RZT, geometry.RZ]:
            # for now, these can only be read in from the old geometry XML files.
            spatialGrid = self._makeRZGridFromLatticeFile()
        if geom == geometry.HEX:
            pitch = self.latticeDimensions.x if self.latticeDimensions else 1.0
            # add 2 for potential dummy assems
            spatialGrid = grids.hexGridFromPitch(pitch, numRings=maxIndex + 2,)
        elif geom == geometry.CARTESIAN:
            # if full core or not cut-off, bump the first assembly from the center of the mesh
            # into the positive values.
            xw, yw = (
                (self.latticeDimensions.x, self.latticeDimensions.y)
                if self.latticeDimensions
                else (1.0, 1.0)
            )
            isOffset = (
                self.symmetry and geometry.THROUGH_CENTER_ASSEMBLY not in self.symmetry
            )
            spatialGrid = grids.cartesianGridFromRectangle(
                xw, yw, numRings=maxIndex, isOffset=isOffset,
            )
        runLog.debug("Built grid: {}".format(spatialGrid))
        # set geometric metadata on spatialGrid. This information is needed in various
        # parts of the code and is best encapsulated on the grid itself rather than on
        # the container state.
        spatialGrid.geomType = self.geom
        spatialGrid.symmetry = self.symmetry
        return spatialGrid

    def _getMaxIndex(self):
        """
        Find the max index in the grid contents.
        
        Used to limit the size of the spatialGrid. Used to be
        called maxNumRings.
        """
        return max(itertools.chain(*zip(*self.gridContents.keys())))

    def _makeRZGridFromLatticeFile(self):
        """Read an old-style XML file to build a RZT spatial grid."""
        geom = geometry.SystemLayoutInput()
        geom.readGeomFromFile(self.latticeFile)
        spatialGrid = grids.thetaRZGridFromGeom(geom)
        return spatialGrid

    def _readGridContents(self):
        """
        Read the specifiers as a function of grid position.

        The contents can either be provided as:

        * A dict mapping indices to specifiers (default output of this)
        * An asciimap
        * A YAML file in the gen-2 geometry file format
        * An XML file in the gen-1 geometry file format

        The output will always be stored in ``self.gridContents``.
        """
        if self.gridContents:
            # grid contents read directly from input so nothing to do here.
            return
        elif self.latticeMap:
            self._readGridContentsLattice()
        elif self.latticeFile:
            self._readGridContentsFile()

    def _readGridContentsLattice(self):
        """Read an ascii map of grid contents.

        This update the gridContents attribute, which is a
        dict mapping grid i,j,k indices to textual specifiers
        (e.g. ``IC``))
        """
        latticeCls = asciimaps.asciiMapFromGeomAndSym(self.geom, self.symmetry)
        lattice = latticeCls()
        self.gridContents = lattice.readMap(self.latticeMap)

    def _readGridContentsFile(self):
        """
        Read grid contents from a file.

        Notes
        -----
        This reads both the old XML format as well as the new
        YAML format. The concept of a grid blueprint is slowly
        trying to take over from the geometry file/geometry object.
        """
        self.gridContents = {}
        geom = geometry.SystemLayoutInput()
        geom.readGeomFromFile(self.latticeFile)
        for indices, spec in geom.assemTypeByIndices.items():
            self.gridContents[indices] = spec
        self.geom = str(geom.geomType)
        self.symmetry = str(geom.symmetry)

        # eqPathInput allows fuel management to be input alongside the core grid.
        # This would be better as an independent grid but is here for now to help
        # migrate inputs from previous versions.
        self.eqPathInput = geom.eqPathInput

    def getLocators(self, spatialGrid: grids.Grid, latticeIDs: list):
        """
        Return spatialLocators in grid corresponding to lattice IDs.

        This requires a fully-populated ``gridContents`` attribute.
        """
        if latticeIDs is None:
            return []
        if self.gridContents is None:
            return []
        # tried using yamlize to coerce ints to strings but failed
        # after much struggle, so we just auto-convert here to deal
        # with int-like specifications.
        # (yamlize.StrList fails to coerce when ints are provided)
        latticeIDs = [str(i) for i in latticeIDs]
        locators = []
        for (i, j), spec in self.gridContents.items():
            locator = spatialGrid[i, j, 0]
            if spec in latticeIDs:
                locators.append(locator)
        return locators

    def getMultiLocator(self, spatialGrid, latticeIDs):
        """Create a MultiIndexLocation based on lattice IDs."""
        spatialLocator = grids.MultiIndexLocation(grid=spatialGrid)
        spatialLocator.extend(self.getLocators(spatialGrid, latticeIDs))
        return spatialLocator


class Grids(yamlize.KeyedList):
    item_type = GridBlueprint
    key_attr = GridBlueprint.name
