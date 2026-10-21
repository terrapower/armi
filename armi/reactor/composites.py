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
Implementation of the `Composite` class in the composite design pattern underlying the reactor package.

This follows the principles of the `Composite Design Pattern <https://en.wikipedia.org/wiki/Composite_pattern>`_ to
allow the construction of a part/whole hierarchy representing a physical nuclear reactor in a tree strucutre. The
`Composite` class implements the 'whole' aspect of the part/whole hierarchy (this is the `Composite` class in
`Gang of Four <https://en.wikipedia.org/wiki/Design_Patterns>`_). The `Composite` objects act somewhat like lists: they
can be indexed, iterated over, appended, extended, inserted, etc. Each member of the hierarchy knows its children and
its parent, so full access to the hierarchy is available from everywhere. This design was chosen because of the close
analogy of the model to the physical nature of nuclear reactors.

Warning
-------
Because each member of the hierarchy is linked to the entire tree, it is often unsafe to save references to individual
members; it can cause large and unexpected memory inefficiencies.

See Also
--------
:doc:`/developer/index`.
armi.reactor.armiObject.ArmiObject
armi.reactor.components.component.Component

"""

import collections
import itertools
import operator
import timeit
from typing import (
    TYPE_CHECKING,
    Callable,
    Iterator,
    List,
    Optional,
    Union,
)

import numpy as np

from armi import context, runLog
from armi.nucDirectory import nuclideBases
from armi.reactor import parameters
from armi.reactor.armiObject import ArmiObject
from armi.reactor.flags import TypeSpec
from armi.utils import tabulate, units

if TYPE_CHECKING:
    from armi.reactor.components.component import Component


class Composite(ArmiObject):
    """
    An ArmiObject that has children.

    This class implements an interface for accessing and managing child objects.

    This is a fundamental ARMI state object that generally represents some piece of the
    nuclear reactor that is made up of other smaller pieces. This object can cache
    information about its children to help performance.

    **Details about spatial representation**

    Spatial representation of a ``Composite`` is handled through a combination of the
    ``spatialLocator`` and ``spatialGrid`` parameters. The ``spatialLocator`` is a numpy
    triple representing either:

    1. Indices in the parent's ``spatialGrid`` (for lattices, etc.), used when the dtype is int.

    2. Coordinates in the parent's universe in cm, used when the dtype is float.

    The top parent of any composite must have a coordinate-based ``spatialLocator``. For
    example, a Reactor and a Pump should both have coordinates based on how far apart
    they are.

    The traversal of indices and grids is recursive. The Reactor/Core/Assembly/Block
    model is handled by putting a 2-D grid (either Theta-R, Hex, or Cartesian) on the
    Core and individual 1-D Z-meshes on the assemblies. Then, Assemblies have 2-D
    spatialLocators (i,j,0) and Blocks have 1-D spatiaLocators (0,0,k). These get added
    to form the global indices. This way, if an assembly is moved, all the blocks
    immediately and naturally move with it. Individual children may have
    coordinate-based spatialLocators mixed with siblings in a grid. This allows mixing
    grid-representation with explicit representation, often useful in advanced
    assemblies and thermal reactors.

    .. impl:: Composites are a physical part of the reactor in a hierarchical data model.
        :id: I_ARMI_CMP0
        :implements: R_ARMI_CMP

        An ARMI reactor model is composed of collections of ARMIObject objects. This
        class is a child-class of the ARMIObject class and provides a structure
        allowing a reactor model to be composed of Composites.

        This class provides various methods to query and modify the hierarchical ARMI
        reactor model, including but not limited to, iterating, sorting, and adding or
        removing child Composites.

    """

    _children: list["ArmiObject"]

    def __init__(self, name):
        ArmiObject.__init__(self, name)
        self.childrenByLocator = {}
        self._children = []

    def __setstate__(self, state):
        """Sets the state of this Composite."""
        ArmiObject.__setstate__(self, state)

        if self.spatialGrid is not None:
            # Spatial locators also get disassociated with their grids when detached;
            # make sure they get hooked back up.
            for c in self:
                c.spatialLocator.associate(self.spatialGrid)

        # now "reattach" children
        for c in self:
            c.parent = self

    def __getitem__(self, index):
        return self._children[index]

    def __setitem__(self, index, obj):
        raise NotImplementedError("Unsafe to insert elements directly")

    def __add__(self, other):
        """Return a list of all children in this and another object."""
        return self.getChildren() + other.getChildren()

    def __iter__(self):
        """Iterate over the children contained in this Composite."""
        return iter(self._children)

    def __len__(self):
        """Get the number of children contained in this Composite."""
        return len(self._children)

    def __contains__(self, item):
        """
        Membership check.

        This does not use quality checks for membership checking because equality
        operations can be fairly heavy. Rather, this only checks direct identity
        matches.
        """
        return id(item) in set(id(c) for c in self._children)

    def sort(self):
        """Sort the children of this object."""
        # sort the top-level children of this Composite
        self._children.sort()

        # recursively sort the children below it.
        for c in self._children:
            if issubclass(c.__class__, Composite):
                c.sort()

    def index(self, obj):
        """Obtain the list index of a particular child."""
        return self._children.index(obj)

    def append(self, obj):
        """Append a child to this object."""
        self._children.append(obj)

    def extend(self, seq):
        """Add a list of children to this object."""
        for item in seq:
            self.add(item)

    def add(self, obj):
        """Add one new child."""
        if obj in self:
            raise RuntimeError(f"Cannot add {obj} because it has already been added to {self}.")
        obj.parent = self
        self._children.append(obj)

    def remove(self, obj):
        """Remove a particular child."""
        obj.parent = None
        obj.spatialLocator = obj.spatialLocator.detachedCopy()
        self._children.remove(obj)

    def moveTo(self, locator):
        """Move to specific location in parent. Often in a grid."""
        if locator.grid.armiObject is not self.parent:
            raise ValueError(
                f"Cannot move {self} to a location in  {locator.grid.armiObject}"
                ", which is not its parent ({self.parent})."
            )
        self.spatialLocator = locator

    def insert(self, index, obj):
        """Insert an object into the list of children at a particular index."""
        if obj in self._children:
            raise RuntimeError(f"Cannot insert {obj} because it has already been added to {self}.")
        obj.parent = self
        self._children.insert(index, obj)

    def clearCache(self):
        """Clear the cache so all new values are recomputed."""
        ArmiObject.clearCache(self)
        for child in self:
            child.clearCache()

    def getVolume(self):
        return sum(child.getVolume() for child in self)

    def getArea(self, cold=False, Tc=None):
        """Get the area of a Composite in cm^2.

        Parameters
        ----------
        cold : bool, optional
            Compute the area with as-input dimensions instead of thermally-expanded
        Tc : float, optional
            Temperature to compute the area at
        """
        return sum(child.getArea(cold=cold, Tc=Tc) for child in self)

    def _updateVolume(self):
        """Recompute and store volume."""
        children = self.getChildren()
        # Derived shapes must come last so we temporarily change the order if we have one.
        from armi.reactor.components import DerivedShape

        for child in children[:]:
            if isinstance(child, DerivedShape):
                children.remove(child)
                children.append(child)
        for child in children:
            child._updateVolume()

    def getVolumeFractions(self):
        """
        Return volume fractions of each child.

        Sets volume or area of missing piece (like coolant) if it exists.

        Returns
        -------
        fracs : list
            list of (component, volFrac) tuples

        See Also
        --------
        test_block.TestBlock.test_consistentAreaWithOverlappingComponents

        Notes
        -----
        void areas can be negative in gaps between fuel/clad/liner(s), but these
        negative areas are intended to account for overlapping positive areas to insure
        the total area of components inside the clad is accurate. See
        test_block.TestBlock.test_consistentAreaWithOverlappingComponents
        """
        children = self.getChildren()
        numerator = [c.getVolume() for c in children]
        denom = sum(numerator)
        if denom == 0.0:
            numerator = [c.getArea() for c in children]
            denom = sum(numerator)

        fracs = [(ci, nu / denom) for ci, nu in zip(children, numerator)]
        return fracs

    def getMass(self, nuclideNames: Union[None, str, list[str]] = None) -> float:
        """
        Determine the mass in grams of nuclide(s) and/or elements in this object.

        .. impl:: Return mass of composite.
            :id: I_ARMI_CMP_GET_MASS
            :implements: R_ARMI_CMP_GET_MASS

            This method allows for the querying of the mass of a Composite.
            If the ``nuclideNames`` argument is included, it will filter for the mass
            of those nuclide names and provide the sum of the mass of those nuclides.

        Parameters
        ----------
        nuclideNames
            The nuclide/element specifier to get the mass of in the object.
            If omitted, total mass is returned.

        Returns
        -------
        mass : float
            The mass in grams.
        """
        return sum(c.getMass(nuclideNames=nuclideNames) for c in self)

    def getFuelMass(self):
        """Returns mass of fuel in grams."""
        return sum((c.getFuelMass() for c in self))

    def getNumberDensity(self, nucName):
        """
        Return the number density of a nuclide in atoms/barn-cm.

        .. impl:: Get number density for a specific nuclide
            :id: I_ARMI_CMP_GET_NDENS0
            :implements: R_ARMI_CMP_GET_NDENS

            This method queries the number density
            of a specific nuclide within the Composite. It invokes the
            ``getNuclideNumberDensities`` method for just the requested nuclide.

        Parameters
        ----------
        nucName : str
            Nuclide name to get number densities for, e.g. 'U233'

        Notes
        -----
        This can get called very frequently and has to do volume computations so should
        use some kind of caching that is invalidated by any temperature, composition,
        etc. changes. Even with caching the volume calls are still somewhat expensive so
        prefer the methods in see also.

        See Also
        --------
        ArmiObject.getNuclideNumberDensities: More efficient for >1 specific nuc density is needed.
        ArmiObject.getNumberDensities: More efficient for when all nucs in object is needed.
        """
        return self.getNuclideNumberDensities([nucName])[0]

    def getNuclideNumberDensities(self, nucNames):
        """Return a list of number densities in atoms/barn-cm for the nuc names requested.

        .. impl:: Get number densities for specific nuclides.
            :id: I_ARMI_CMP_GET_NDENS1
            :implements: R_ARMI_CMP_GET_NDENS

        Parameters
        ----------
        nucNames : list of str
            Nuclide names to get number densities for, e.g. ['U233', 'U235', 'Pu239']

        Notes
        -----
        This method provides the capability to query the volume weighted number
        densities for a list of nuclides within a given Composite. It provides the
        result in units of atoms/barn-cm. The volume weighting is accomplished by
        multiplying the number densities within each child Composite by the volume
        of the child Composite and dividing by the total volume of the Composite.
        """
        volumes = np.array([c.getVolume() / (c.parent.getSymmetryFactor() if c.parent else 1.0) for c in self])  # c x 1
        totalVol = volumes.sum()
        if totalVol == 0.0:
            # there are no children so no volume or number density
            return [0.0] * len(nucNames)

        nucDensForEachComp = np.array([c.getNuclideNumberDensities(nucNames) for c in self])  # c x n
        return volumes.dot(nucDensForEachComp) / totalVol

    def _getNdensHelper(self):
        """
        Return a number densities dict with unexpanded lfps.

        Notes
        -----
        This is implemented more simply on the component level.
        """
        nucNames = self.getNuclides()
        return dict(zip(nucNames, self.getNuclideNumberDensities(nucNames)))

    def setNumberDensity(self, nucName, val):
        """
        Set the number density of this nuclide to this value.

        This distributes atom density evenly across all children that contain nucName.
        If the nuclide doesn't exist in any of the children, then that's actually an
        error. This would only happen if some unnatural nuclide like Pu239 built up in
        fresh UZr. That should be anticipated and dealt with elsewhere.

        Parameters
        ----------
        nucName : str
            Nuclide number density to modify
        val : float
            Number density to set in atoms/bn-cm (heterogeneous)
        """
        activeChildren = self.getChildrenWithNuclides({nucName})
        if not activeChildren:
            activeVolumeFrac = 1.0
            if val:
                raise ValueError(
                    f"The nuclide {nucName} does not exist in any children of {self}; "
                    f"cannot set its number density to {val}. The nuclides here are: {self.getNuclides()}"
                )
        else:
            activeVolumeFrac = sum(vf for ci, vf in self.getVolumeFractions() if ci in activeChildren)
        dehomogenizedNdens = val / activeVolumeFrac  # scale up to dehomogenize on children.
        for child in activeChildren:
            child.setNumberDensity(nucName, dehomogenizedNdens)

    def setNumberDensities(self, numberDensities):
        """
        Set one or more multiple number densities. Reset any non-listed nuclides to 0.0.

        Parameters
        ----------
        numberDensities : dict
            nucName: ndens pairs.

        Notes
        -----
        We'd like to not have to call setNumberDensity for each nuclide because we don't
        want to call ``getVolumeFractions`` for each nuclide (it's inefficient).
        """
        numberDensities.update({nuc: 0.0 for nuc in self.getNuclides() if nuc not in numberDensities})
        self.updateNumberDensities(numberDensities)

    def updateNumberDensities(self, numberDensities):
        """
        Set one or more multiple number densities. Leaves unlisted number densities alone.

        This changes a nuclide number density only on children that already have that
        nuclide, thereby allowing, for example, actinides to stay in the fuel component
        when setting block-level values.

        The complication is that various number densities are distributed among various
        components. This sets the number density for each nuclide evenly across all
        components that contain it.

        Parameters
        ----------
        numberDensities : dict
            nucName: ndens pairs.
        """
        children, volFracs = zip(*self.getVolumeFractions())
        childNucs = tuple(set(child.getNuclides()) for child in children)

        allDehomogenizedNDens = collections.defaultdict(dict)

        # compute potentially-different homogenization factors for each child.  evenly
        # distribute entire number density over the subset of active children.
        for nuc, dens in numberDensities.items():
            # Get "active" indices, i.e. indices of children containing nuclide.
            # NOTE: This uses explicit indexing to clarify subsequent code, since it is not necessary to zip + filter +
            # extract individual components (we just extract by filtered index).
            indiciesToSet = tuple(i for i, nucsInChild in enumerate(childNucs) if nuc in nucsInChild)

            if not indiciesToSet:
                if dens == 0:
                    # density is zero, skip
                    continue

                # This nuc doesn't exist in any children but is to be set.
                # Evenly distribute it everywhere.
                childrenToSet = children
                dehomogenizedNDens = dens / sum(volFracs)

            else:
                childrenToSet = tuple(children[i] for i in indiciesToSet)
                dehomogenizedNDens = dens / sum(volFracs[i] for i in indiciesToSet)

            for child in childrenToSet:
                allDehomogenizedNDens[child][nuc] = dehomogenizedNDens

        # apply the child-dependent ndens vectors to the children
        for child, ndens in allDehomogenizedNDens.items():
            child.updateNumberDensities(ndens)

    def changeNDensByFactor(self, factor):
        """Change the number density of all nuclides within the object by a multiplicative factor."""
        densitiesScaled = {nuc: val * factor for nuc, val in self.getNumberDensities().items()}
        self.setNumberDensities(densitiesScaled)

        # Update detailedNDens if it exists (Components only)
        if self.p.get("detailedNDens", None) is not None:
            self.p.detailedNDens *= factor

        # Update pinNDens if it exists (Components only)
        if self.p.get("pinNDens", None) is not None:
            self.p.pinNDens *= factor

    def calcTotalParam(
        self,
        param,
        objs=None,
        volumeIntegrated=False,
        addSymmetricPositions=False,
        typeSpec: TypeSpec = None,
        generationNum=1,
        calcBasedOnFullObj=False,
    ):
        """
        Sums up a parameter throughout the object's children or list of objects.

        Parameters
        ----------
        param : str
            Name of the block parameter to sum

        objs : iterable, optional
            A list of objects to sum over. If None, all children in object will be used
        volumeIntegrated : bool, optional
            Integrate over volume
        addSymmetricPositions : bool, optional
            If True, will multiply by the symmetry factor of the core (3 for 1/3 models, 1 for full core models)
        typeSpec : TypeSpec
            object types to restrict to
        generationNum : int, optional
            Which generation to consider. 1 means direct children, 2 means grandchildren. Default: 1.
        calcBasedOnFullObj : bool, optional
            Some assemblies or blocks, such as the center assembly in a third-core model, are not modeled as full
            assemblies or blocks. In the third-core model, objects at these positions are modeled as having 1/3 the
            volume and thus 1/3 the power. Setting this argument to True will apply the full value of the parameter as
            if it was a full block or assembly.
        """
        tot = 0.0
        if objs is None:
            objs = self.getChildren(generationNum=generationNum)

        if addSymmetricPositions:
            if calcBasedOnFullObj:
                raise ValueError(
                    "AddSymmetricPositions is Incompatible with calcBasedOnFullObj. Will result in double counting."
                )
            try:
                coreMult = self.powerMultiplier
            except AttributeError:
                coreMult = self.parent.powerMultiplier
            if not coreMult:
                raise ValueError(f"powerMultiplier is equal to {coreMult}")
        else:
            coreMult = 1.0

        for a in objs:
            if not a.hasFlags(typeSpec):
                continue

            mult = a.getVolume() if volumeIntegrated else 1.0
            if calcBasedOnFullObj:
                mult *= a.getSymmetryFactor()

            tot += a.p[param] * mult

        return tot * coreMult

    def calcAvgParam(
        self,
        param,
        typeSpec: TypeSpec = None,
        weightingParam=None,
        volumeAveraged=True,
        absolute=True,
        generationNum=1,
    ):
        r"""
        Calculate the child-wide average of a parameter.

        Parameters
        ----------
        param : str
            The ARMI block parameter that you want to average
        typeSpec : TypeSpec
            The child types that should be included in the calculation. Restrict average
            to a certain child type with this parameter.
        weightingParam : None or str, optional
             An optional block param that the average will be weighted against
        volumeAveraged : bool, optional
            volume (or height, or area) average this param
        absolute : bool, optional
            Returns the average of the absolute value of param
        generationNum : int, optional
            Which generation to average over (1 for children, 2 for grandchildren)

        The weighted sum is:

        .. math::

            \left<\text{x}\right> = \frac{\sum_{i} x_i w_i}{\sum_i w_i}

        where :math:`i` is each child, :math:`x_i` is the param value of the i-th child,
        and :math:`w_i` is the weighting param value of the i-th child.

        Warning
        -------
        If a param is unset/zero on any of the children, this will be included in the
        average and may significantly perturb results.

        Returns
        -------
        float
            The average parameter value.
        """
        total = 0.0
        weightSum = 0.0
        for child in self.getChildren(generationNum=generationNum):
            if child.hasFlags(typeSpec):
                if weightingParam:
                    weight = child.p[weightingParam]
                    if weight < 0:
                        # Just for conservatism, do not allow negative weights.
                        raise ValueError(f"Weighting value ({weightingParam},{weight}) cannot be negative.")
                else:
                    weight = 1.0

                if volumeAveraged:
                    weight *= child.getVolume()

                weightSum += weight
                if absolute:
                    total += abs(child.p[param]) * weight
                else:
                    total += child.p[param] * weight
        if not weightSum:
            raise ValueError(
                f"Cannot calculate {weightingParam}-weighted average of {param} in {self}. "
                f"Weights sum to zero. typeSpec is {typeSpec}"
            )
        return total / weightSum

    def getMaxParam(
        self,
        param,
        typeSpec: TypeSpec = None,
        absolute=True,
        generationNum=1,
        returnObj=False,
    ):
        """
        Find the maximum value for the parameter in this container.

        Parameters
        ----------
        param : str
            block parameter that will be sought.

        typeSpec : TypeSpec
            restricts the search to cover a variety of block types.

        absolute : bool
            looks for the largest magnitude value, regardless of sign, default: true

        returnObj : bool, optional
            If true, returns the child object as well as the value.

        Returns
        -------
        maxVal : float
            The maximum value of the parameter asked for
        obj : child object
            The object that has the max (only returned if ``returnObj==True``)
        """
        compartor = lambda x, y: x > y
        return self._minMaxHelper(
            param,
            typeSpec,
            absolute,
            generationNum,
            returnObj,
            -float("inf"),
            compartor,
        )

    def getMinParam(
        self,
        param,
        typeSpec: TypeSpec = None,
        absolute=True,
        generationNum=1,
        returnObj=False,
    ):
        """
        Find the minimum value for the parameter in this container.

        See Also
        --------
        getMaxParam : details
        """
        compartor = lambda x, y: x < y
        return self._minMaxHelper(param, typeSpec, absolute, generationNum, returnObj, float("inf"), compartor)

    def _minMaxHelper(
        self,
        param,
        typeSpec: TypeSpec,
        absolute,
        generationNum,
        returnObj,
        startingNum,
        compartor,
    ):
        """Helper for getMinParam and getMaxParam."""
        maxP = (startingNum, None)
        realVal = 0.0
        objs = self.getChildren(generationNum=generationNum)
        for b in objs:
            if b.hasFlags(typeSpec):
                try:
                    val = b.p[param]
                except parameters.UnknownParameterError:
                    # No worries; not all Composite types are guaranteed to have the
                    # relevant parameter. It might be a good idea to more strongly
                    # type-check this, perhaps by passing the paramDef,
                    # rather than its name?
                    continue
                if val is None:
                    # Neither bigger or smaller than anything (also illegal in Python3)
                    continue
                if absolute:
                    absVal = abs(val)
                else:
                    absVal = val
                if compartor(absVal, maxP[0]):
                    maxP = (absVal, b)
                    realVal = val
        if returnObj:
            return realVal, maxP[1]
        else:
            return realVal

    def getNuclides(self):
        """
        Determine which nuclides are present in this armi object.

        Returns
        -------
        nucs : list of str
            Nuclide names that exist in this ArmiObject
        """
        nucs = set()
        for child in self:
            nucs.update(child.getNuclides())
        return nucs

    def removeAll(self):
        """Remove all children."""
        for c in self.getChildren()[:]:
            self.remove(c)

    def setChildren(self, items):
        """Clear this container and fills it with new children."""
        self.removeAll()
        for c in items:
            self.add(c)

    def iterChildren(
        self,
        deep=False,
        generationNum=1,
        predicate: Optional[Callable[["ArmiObject"], bool]] = None,
    ) -> Iterator["ArmiObject"]:
        """Iterate over children objects of this composite.

        Parameters
        ----------
        deep : bool, optional
            If true, traverse the entire composite tree. Otherwise, go as far as ``generationNum``.
        generationNum: int, optional
            Produce composites at this depth. A depth of ``1`` includes children of ``self``, ``2``
            is children of children, and so on.
        predicate: f(Composite) -> bool, optional
            Function to check on a composite before producing it. All items in the iteration
            will pass this check.

        Returns
        -------
        iterator of Composite and/or Component objects

        See Also
        --------
        :meth:`getChildren` produces a list for situations where you need to perform
        multiple iterations or do list operations (append, indexing, sorting, containment, etc.)

        Composites are naturally iterable. The following are identical::

            >>> for child in c.getChildren():
            ...     pass
            >>> for child in c.iterChildren():
            ...     pass
            >>> for child in c:
            ...     pass

        If you do not need any depth-traversal, natural iteration should be sufficient.

        The :func:`filter` command may be sufficient if you do not wish to pass a predicate. The following
        are identical::
            >>> checker = lambda c: len(c.name) % 3
            >>> for child in c.getChildren(predicate=checker):
            ...     pass
            >>> for child in c.iterChildren(predicate=checker):
            ...     pass
            >>> for child in filter(checker, c):
            ...     pass

        If you're going to be doing traversal beyond the first generation, this method will help you.
        """
        if deep and generationNum > 1:
            raise RuntimeError("Cannot get children with a generation number set and the deep flag set")
        if predicate is None:
            checker = lambda _: True
        else:
            checker = predicate
        yield from self._iterChildren(deep, generationNum, checker)

    def _iterChildren(
        self, deep: bool, generationNum: int, checker: Callable[["ArmiObject"], bool]
    ) -> Iterator["ArmiObject"]:
        """Generator function for iterating over composite tree children.

        Parameters
        ----------
        deep : bool, optional
            If true, traverse the entire composite tree. Otherwise, go as far as ``generationNum``.
        generationNum: int, optional
            Generator depth. A depth of ``1`` includes children of ``self``, ``2``
            excluisively is children of children, and so on.
        checker: f(Composite) -> bool, optional
            Function that filters what children ar added to the generator object.
        """
        ## Add the children at the 'base' level of the composite tree, if needed
        if deep or generationNum == 1:
            yield from filter(checker, self)
        ## Add deeper children to the generator object recursively.
        if deep or generationNum > 1:
            for c in self:
                if isinstance(c, Composite):
                    yield from c._iterChildren(deep, generationNum - 1, checker)
                else:
                    yield from ()

    def iterChildrenWithMaterials(self, *args, **kwargs) -> Iterator:
        """Produce an iterator that also includes any materials found on descendants.

        Arguments are forwarded to :meth:`iterChildren` and control the depth of traversal
        and filtering of objects.

        This is useful for sending state across MPI tasks where you need a more full
        representation of the composite tree. Which includes the materials attached
        to components.
        """
        children = self.iterChildren(*args, **kwargs)
        # Each entry is either (c, ) or (c, c.material) if the child has a material attribute
        stitched = map(
            lambda c: ((c,) if getattr(c, "material", None) is None else (c, c.material)),
            children,
        )
        # Iterator that iterates over each "sub" iterator. If we have ((c0, ), (c1, m1)), this produces a single
        # iterator of (c0, c1, m1)
        return itertools.chain.from_iterable(stitched)

    def getChildren(
        self,
        deep=False,
        generationNum=1,
        includeMaterials=False,
        predicate: Optional[Callable[["ArmiObject"], bool]] = None,
    ) -> list["ArmiObject"]:
        """
        Return the children objects of this composite.

        .. impl:: Composites have children in the hierarchical data model.
            :id: I_ARMI_CMP1
            :implements: R_ARMI_CMP

            This method retrieves all children within a given Composite object. Children of any
            generation can be retrieved. This is achieved by visiting all children and calling this
            method recursively for each generation requested.

            If the method is called with ``includeMaterials``, it will additionally include
            information about the material for each child. If a function is supplied as the
            ``predicate`` argument, then this method will be used to evaluate all children as a
            filter to include or not. For example, if the caller of this method only desires
            children with a certain flag, or children which only contain a certain material, then
            the ``predicate`` function can be used to perform this filtering.

        Parameters
        ----------
        deep : boolean, optional
            Return all children of all levels.

        generationNum : int, optional
            Which generation to return. 1 means direct children, 2 means children of children.
            Setting this parameter will only return children of this generation, not their parents.
            Default: Just return direct children.

        includeMaterials : bool, optional
            Include the material properties

        predicate : callable, optional
            An optional unary predicate to use for filtering results. This can be used to request
            children of specific types, or with desired attributes. Not all ArmiObjects have the
            same methods and members, so care should be taken to make sure that the predicate
            executes gracefully in all cases (e.g., use ``getattr(obj, "attribute", None)`` to
            access instance attributes). Failure to meet the predicate only affects the object in
            question; children will still be considered.

        See Also
        --------
        :meth:`iterChildren` if you do not need to produce a full list, e.g., just iterating
        over objects.

        Examples
        --------
        >>> obj.getChildren()
        [child1, child2, child3]

        >>> obj.getChildren(generationNum=2)
        [grandchild1, grandchild2, grandchild3]

        >>> obj.getChildren(deep=True)
        [child1, child2, child3, grandchild1, grandchild2, grandchild3]

        # Assuming that grandchild1 and grandchild3 are Component objects
        >>> obj.getChildren(deep=True, predicate=lambda o: isinstance(o, Component))
        [grandchild1, grandchild3]

        """
        if not includeMaterials:
            items = self.iterChildren(deep=deep, generationNum=generationNum, predicate=predicate)
        else:
            items = self.iterChildrenWithMaterials(deep=deep, generationNum=generationNum, predicate=predicate)
        return list(items)

    def iterChildrenWithFlags(self, typeSpec: TypeSpec, exactMatch=False) -> Iterator["ArmiObject"]:
        """Produce an iterator of children that have given flags."""
        return self.iterChildren(predicate=lambda o: o.hasFlags(typeSpec, exactMatch))

    def getChildrenWithFlags(self, typeSpec: TypeSpec, exactMatch=False) -> list["ArmiObject"]:
        """Get all children that have given flags."""
        return list(self.iterChildrenWithFlags(typeSpec, exactMatch))

    def getChildrenWithNuclides(self, nucNames):
        """Return children that contain any nuclides in nucNames."""
        nucNames = set(nucNames)  # only convert to set once
        return [child for child in self if nucNames.intersection(child.getNuclides())]

    def iterChildrenOfType(self, typeName: str) -> Iterator["ArmiObject"]:
        """Iterate over children that have a specific input type name."""
        return self.iterChildren(predicate=lambda o: o.getType() == typeName)

    def getChildrenOfType(self, typeName: str) -> list["ArmiObject"]:
        """Produce a list of children that have a specific input type name."""
        return list(self.iterChildrenOfType(typeName))

    def doChildrenHaveFlags(self, typeSpec: TypeSpec, deep=False):
        """
        Generator that yields True if the next child has given flags.

        Parameters
        ----------
        typeSpec : TypeSpec
            Requested type of the child
        """
        for c in self.getChildren(deep):
            if c.hasFlags(typeSpec, exact=False):
                yield True
            else:
                yield False

    def containsAtLeastOneChildWithFlags(self, typeSpec: TypeSpec):
        """
        Return True if any of the children are of a given type.

        Parameters
        ----------
        typeSpec : TypeSpec
            Requested type of the children

        See Also
        --------
        self.doChildrenHaveFlags
        self.containsOnlyChildrenWithFlags
        """
        return any(self.doChildrenHaveFlags(typeSpec))

    def containsOnlyChildrenWithFlags(self, typeSpec: TypeSpec):
        """
        Return True if all of the children are of a given type.

        Parameters
        ----------
        typeSpec : TypeSpec
            Requested type of the children

        See Also
        --------
        self.doChildrenHaveFlags
        self.containsAtLeastOneChildWithFlags
        """
        return all(self.doChildrenHaveFlags(typeSpec))

    def setChildrenLumpedFissionProducts(self, lfpCollection):
        for c in self:
            c.setLumpedFissionProducts(lfpCollection)

    def getChildParamValues(self, param):
        """Get the child parameter values in a numpy array."""
        return np.array([child.p[param] for child in self])

    def copyParamsToChildren(self, paramNames):
        """
        Copy param values in paramNames to all children.

        Parameters
        ----------
        paramNames : list
            List of param names to copy to children
        """
        for paramName in paramNames:
            myVal = self.p[paramName]
            for c in self:
                c.p[paramName] = myVal

    def getFirstComponent(self, typeSpec: TypeSpec = None, exact=False):
        """
        Returns a single Component object within this Composite.

        Parameters
        ----------
        typeSpec : TypeSpec
            Component flags. Will restrict Components to specific ones matching the flags specified.
        exact : bool, optional
            Only match exact component labels (names). If True, 'coolant' will not match 'interCoolant'. This has no
            impact if typeSpec is None.

        Returns
        -------
        Component
            The first item matching typeSpec and exact criteria
        """
        try:
            return next(self.iterComponents(typeSpec, exact))
        except StopIteration:
            raise ValueError(f"No component matches {typeSpec} {exact}")

    def iterComponents(self, typeSpec: TypeSpec = None, exact: bool = False) -> Iterator["Component"]:
        """
        Return an iterator of armi.reactor.component.Component objects within this Composite.

        Parameters
        ----------
        typeSpec : TypeSpec
            Component flags. Will restrict Components to specific ones matching the flags specified.

        exact : bool, optional
            Only match exact component labels (names). If True, 'coolant' will not match
            'interCoolant'. This has no impact if typeSpec is None.

        Returns
        -------
        iterator of Component
            items matching typeSpec and exact criteria
        """
        return (
            c
            for child in self
            for c in (
                child.iterComponents(typeSpec, exact)
                if isinstance(child, Composite)
                else [child]
                if child.hasFlags(typeSpec, exact)
                else []
            )
        )

    def getComponentNames(self):
        """
        Get all unique component names of this Composite.

        Returns
        -------
        set or str
            A set of all unique component names found in this Composite.
        """
        return set(c.getName() for c in self.iterComponents())

    def getComponentsOfShape(self, shapeClass):
        """
        Return list of components in this block of a particular shape.

        Parameters
        ----------
        shapeClass : Component
            The class of component, e.g. Circle, Helix, Hexagon, etc.

        Returns
        -------
        param : list
            List of components in this block that are of the given shape.
        """
        return [c for c in self.iterComponents() if isinstance(c, shapeClass)]

    def getComponentsOfMaterial(self, material=None, materialName=None):
        """
        Return list of components in this block that are made of a particular material.

        Only one of the selectors may be used

        Parameters
        ----------
        material : armi.materials.material.Material, optional
            The material to match
        materialName : str, optional
            The material name to match.

        Returns
        -------
        componentsWithThisMat : list
        """
        if materialName is None:
            materialName = material.getName()
        else:
            assert material is None, "Cannot call with more than one selector. Choose one or the other."

        componentsWithThisMat = []
        for c in self.iterComponents():
            if c.getProperties().getName() == materialName:
                componentsWithThisMat.append(c)
        return componentsWithThisMat

    def hasComponents(self, typeSpec: Union[TypeSpec, List[TypeSpec]], exact=False):
        """
        Return true if components matching all TypeSpec exist in this object.

        Parameters
        ----------
        typeSpec : Flags or iterable of Flags
            Component flags to check for
        """
        # Wrap the typeSpec in a tuple if we got a scalar
        try:
            typeSpec = iter(typeSpec)
        except TypeError:
            typeSpec = (typeSpec,)

        return all(self.getComponents(t, exact) for t in typeSpec)

    def getComponentByName(self, name: str) -> "Component":
        """
        Gets a particular component from this object, based on its name.

        Parameters
        ----------
        name
            The blueprint name of the component to return

        Returns
        -------
        Component, c, whose c.name matches name.
        """
        components = [c for c in self.iterComponents() if c.name == name]
        nComp = len(components)
        if nComp == 0:
            return None
        elif nComp > 1:
            raise ValueError(f"More than one component named '{name}' in {self}")
        else:
            return components[0]

    def getComponent(self, typeSpec: TypeSpec, exact: bool = False, quiet: bool = True) -> Optional["Component"]:
        """
        Get a particular component from this object.

        Be careful with multiple similar names in one object.

        Parameters
        ----------
        typeSpec : flags.Flags or list of Flags
            The type specification of the component to return
        exact : boolean, optional
            Demand that the component flags be exactly equal to the typespec. Default: False
        quiet : boolean, optional
            Log if the component is not found. Default: True

        Returns
        -------
        Component : The component that matches the criteria or None

        Raises
        ------
        ValueError: more than one Component matches the typeSpec
        """
        results = self.getComponents(typeSpec, exact=exact)
        if len(results) == 1:
            return results[0]
        elif not results:
            if not quiet:
                runLog.debug(
                    f"No component matched {typeSpec} in {self}. Returning None",
                    single=True,
                    label=f"None component returned instead of {typeSpec}",
                )
            return None
        else:
            raise ValueError(f"Multiple components match in {self} match typeSpec {typeSpec}: {results}")

    def getComponents(self, typeSpec: TypeSpec = None, exact=False):
        """
        Return a list of Component objects within this Composite.

        Parameters
        ----------
        typeSpec : TypeSpec
            Component flags. Will restrict Components to specific ones matching the flags specified.
        exact : bool, optional
            Only match exact component labels (names). If True, 'coolant' will not match 'interCoolant'. This has no
            impact if typeSpec is None.

        Returns
        -------
        list of Component
            items matching typeSpec and exact criteria
        """
        return list(self.iterComponents(typeSpec, exact))

    def getNumComponents(self, typeSpec: TypeSpec, exact=False):
        """
        Get the number of components that have these flags, taking into account multiplicity. Useful
        for getting nPins even when there are pin detailed cases.

        Parameters
        ----------
        typeSpec : Flags
            Expected flags of the component to get. e.g. Flags.FUEL

        Returns
        -------
        total : int
            the number of components of this type in this object, including multiplicity.
        """
        total = 0
        for c in self.iterComponents(typeSpec, exact):
            total += int(c.getDimension("mult"))
        return total

    def setComponentDimensionsReport(self):
        """Makes a summary of the dimensions of the components in this object."""
        reportGroups = []
        for c in self.iterComponents():
            reportGroups.append(c.setDimensionReport())

        return reportGroups

    def getBoundingIndices(self):
        """
        Find the 3-D index bounds (min, max) of all children in the spatial grid of this object.

        Returns
        -------
        bounds : tuple
            ((minI, maxI), (minJ, maxJ), (minK, maxK))
        """
        minI = minJ = minK = float("inf")
        maxI = maxJ = maxK = -float("inf")
        for obj in self:
            i, j, k = obj.spatialLocator.getCompleteIndices()
            if i >= maxI:
                maxI = i
            if i <= minI:
                minI = i

            if j >= maxJ:
                maxJ = j
            if j <= minJ:
                minJ = j

            if k >= maxK:
                maxK = k
            if k <= minK:
                minK = k

        return ((minI, maxI), (minJ, maxJ), (minK, maxK))

    def expandElementalToIsotopics(self, elementalNuclide):
        """
        Expand the density of a specific element to its natural isotopic distribution.

        Parameters
        ----------
        elementalNuclide : :class:`armi.nucDirectory.nuclideBases.NaturalNuclide` element to
            expand into natural isotopic distribution.
        """
        for component in self.iterComponents():
            self._expandElementalToIsotopics(component, elementalNuclide)

    def getAverageTempInC(self, typeSpec: TypeSpec = None, exact=False):
        """Return the volume-averaged temperature (in degrees Celsius) of the ArmiObject over all children.

        Parameters
        ----------
        typeSpec : TypeSpec
            Component flags. Will restrict Components to specific ones matching the flags specified.
        exact : bool, optional
            Only match exact component labels (names). If True, 'coolant' will not match 'interCoolant'. This has no
            impact if typeSpec is None.

        Returns
        -------
        averageTemperature : float
            Child-averaged temperature (in degrees Celsius)
        """
        tempNumerator = 0.0
        totalVol = 0.0
        for component in self.iterComponents(typeSpec, exact):
            vol = component.getVolume()
            tempNumerator += component.temperatureInC * vol
            totalVol += vol

        return tempNumerator / totalVol

    def resolveLinkedDims(self, components):
        """Resolve link strings to links on all child components."""
        for component in self.iterComponents():
            component.resolveLinkedDims(components)

    def getDominantMaterial(self, typeSpec: TypeSpec = None, exact=False):
        """
        Return the first sample of the most dominant material (by volume) in this object.

        Parameters
        ----------
        typeSpec : Flags or iterable of Flags, optional
            The types of components to consider (e.g. ``[Flags.FUEL, Flags.CONTROL]``)
        exact : bool, optional
            Whether or not the TypeSpec is exact

        Returns
        -------
        mat : armi.materials.material.Material
             the first instance of the most dominant material (by volume) in this object.

        See Also
        --------
        getComponentsOfMaterial
            Gets components that are made of a particular material
        gatherMaterialsByVolume
            Classifies all materials by volume
        """
        return getDominantMaterial([self], typeSpec, exact)

    def syncMpiState(self):
        """
        Synchronize all parameters of this object and all children to all worker nodes over the
        network using MPI.

        In parallelized runs, if each process has its own copy of the entire reactor hierarchy, this
        method synchronizes the state of all parameters on all objects.

        .. impl:: Composites can be synchronized across MPI threads.
            :id: I_ARMI_CMP_MPI
            :implements: R_ARMI_CMP_MPI

            Parameters need to be handled properly during parallel code execution. This method
            synchronizes all parameters of the composite object across all processes by cycling
            through all the children of the Composite and ensuring that their parameters are
            properly synchronized. If it fails to synchronize, an error message is displayed which
            alerts the user to which Composite has inconsistent data across the processes.

        Returns
        -------
        int
            number of parameters synchronized over all components
        """
        if context.MPI_SIZE == 1:
            return 0

        startTime = timeit.default_timer()
        # sync parameters...
        genItems = itertools.chain(
            [self],
            self.iterChildrenWithMaterials(deep=True),
        )
        allComps = [c for c in genItems if hasattr(c, "p")]
        sendBuf = [c.p.getSyncData() for c in allComps]
        runLog.debug(f"syncMpiState has {len(allComps)} comps")

        try:
            context.MPI_COMM.barrier()  # sync up
            allGatherTime = -timeit.default_timer()
            allSyncData = context.MPI_COMM.allgather(sendBuf)
            allGatherTime += timeit.default_timer()
        except:
            msg = ["Failure while trying to allgather."]
            for ci, compData in enumerate(sendBuf):
                if compData is not None:
                    msg += [f"sendBuf[{ci}]: {compData}"]
            runLog.error("\n".join(msg))
            raise

        # key is (comp, paramName) value is conflicting nodes
        errors = collections.defaultdict(list)
        syncCount = 0
        compsPerNode = {len(nodeSyncData) for nodeSyncData in allSyncData}

        if len(compsPerNode) != 1:
            raise ValueError(f"The workers have different reactor sizes! comp lengths: {compsPerNode}")

        for ci, comp in enumerate(allComps):
            if not hasattr(comp, "_syncParameters"):
                # materials don't have Parameters to sync
                continue
            data = (nodeSyncData[ci] for nodeSyncData in allSyncData)
            syncCount += comp._syncParameters(data, errors)

        if errors:
            errorData = sorted(
                (str(comp), comp.__class__.__name__, str(comp.parent), paramName, nodes)
                for (comp, paramName), nodes in errors.items()
            )
            message = "Synchronization failed due to overlapping data. Only the first duplicates are listed\n{}".format(
                tabulate.tabulate(
                    errorData,
                    headers=[
                        "ArmiObject",
                        "Composite Type",
                        "Composite Parent",
                        "ParameterName",
                        "NodeRanks",
                    ],
                )
            )
            raise ValueError(message)

        self._markSynchronized()
        runLog.extra(
            f"Synchronized reactor over MPI in {timeit.default_timer() - startTime:.4f} seconds"
            f", {allGatherTime:.4f} seconds in MPI allgather. count:{syncCount}"
        )

        return syncCount

    def _markSynchronized(self):
        """
        Mark the composite and child parameters as synchronized across MPI.

        We clear SINCE_LAST_DISTRIBUTE_STATE so that anything after this point will set the
        SINCE_LAST_DISTRIBUTE_STATE flag, indicating it has been modified
        SINCE_LAST_DISTRIBUTE_STATE.
        """
        paramDefs = set()
        items = itertools.chain(
            [self],
            self.iterChildrenWithMaterials(deep=True),
        )
        for child in items:
            # Materials don't have a "p" / Parameter attribute to sync
            if hasattr(child, "p"):
                # below reads as: assigned & everything_but(SINCE_LAST_DISTRIBUTE_STATE)
                child.p.assigned &= ~parameters.SINCE_LAST_DISTRIBUTE_STATE
                paramDefs.add(child.p.paramDefs)

        for paramDef in paramDefs:
            paramDef.resetAssignmentFlag(parameters.SINCE_LAST_DISTRIBUTE_STATE)

    def getLumpedFissionProductsIfNecessary(self, nuclides=None):
        """Return Lumped Fission Product objects that belong to this object or any of its children."""
        if self.requiresLumpedFissionProducts(nuclides=nuclides):
            lfps = self.getLumpedFissionProductCollection()
            if lfps is None:
                for c in self:
                    return c.getLumpedFissionProductsIfNecessary(nuclides=nuclides)
            else:
                return lfps
        # There are no lumped fission products in the batch so if you use a
        # dictionary no one will know the difference
        return {}

    def getLumpedFissionProductCollection(self):
        """
        Get collection of LFP objects. Will work for global or block-level LFP models.

        Returns
        -------
        lfps : object
            lfpName keys, lfp object values

        See Also
        --------
        armi.physics.neutronics.fissionProductModel.lumpedFissionProduct.LumpedFissionProduct
        """
        lfps = ArmiObject.getLumpedFissionProductCollection(self)
        if lfps is None:
            for c in self:
                lfps = c.getLumpedFissionProductCollection()
                if lfps is not None:
                    break

        return lfps

    def requiresLumpedFissionProducts(self, nuclides=None):
        """True if any of the nuclides in this object are Lumped nuclides."""
        if nuclides is None:
            nuclides = self.getNuclides()

        # ruff: noqa: SIM110
        for nucName in nuclides:
            if isinstance(self.nuclideBases.byName[nucName], nuclideBases.LumpNuclideBase):
                return True

        return False

    def getIntegratedMgFlux(self, adjoint=False, gamma=False):
        """
        Returns the multigroup neutron tracklength in [n-cm/s].

        The first entry is the first energy group (fastest neutrons). Each additional group is the
        next energy group, as set in the ISOTXS library.

        Parameters
        ----------
        adjoint : bool, optional
            Return adjoint flux instead of real
        gamma : bool, optional
            Whether to return the neutron flux or the gamma flux.

        Returns
        -------
        integratedFlux : np.ndarray
            multigroup neutron tracklength in [n-cm/s]
        """
        integratedMgFlux = np.zeros(1)
        for c in self:
            mgFlux = c.getIntegratedMgFlux(adjoint=adjoint, gamma=gamma)
            if mgFlux is not None:
                integratedMgFlux = integratedMgFlux + mgFlux

        return integratedMgFlux

    def getReactionRates(self, nucName, nDensity=None):
        """
        Get the reaction rates of a certain nuclide on this ArmiObject.

        Parameters
        ----------
        nucName : str
            nuclide name -- e.g. 'U235'
        nDensity : float
            number Density

        Returns
        -------
        rxnRates : dict
            reaction rates (1/s) for nG, nF, n2n, nA and nP

        Notes
        -----
        This is volume integrated NOT (1/cm3-s).

        If you set nDensity to 1 this makes 1-group cross section generation easier.
        """
        from armi.reactor.components import Component

        # find child objects
        objects = self.getChildren(deep=True, predicate=lambda x: isinstance(x, Component))
        if not len(objects):
            objects = [self]

        # The reaction rates for this object is the sum of its children
        rxnRates = {"nG": 0, "nF": 0, "n2n": 0, "nA": 0, "nP": 0, "n3n": 0}
        for armiObject in objects:
            for rxName, val in armiObject._getReactionRates(nucName, nDensity).items():
                rxnRates[rxName] += val

        return rxnRates

    def printContents(self, includeNuclides=True):
        """Display information about all the comprising children in this object."""
        runLog.important(self)
        for c in self:
            c.printContents(includeNuclides=includeNuclides)

    def getBoundingCircleOuterDiameter(self, Tc=None, cold=False):
        """
        Get sum circle bound.

        Used to roughly approximate relative size vs. other objects
        """
        getter = operator.methodcaller("getBoundingCircleOuterDiameter", Tc, cold)
        return sum(map(getter, self))

    def getPuMoles(self):
        """Returns total number of moles of Pu isotopes."""
        nucNames = [nuc.name for nuc in self.nuclideBases.elements.byZ[94].nuclides]
        puN = np.sum(self.getNuclideNumberDensities(nucNames))

        return puN / units.MOLES_PER_CC_TO_ATOMS_PER_BARN_CM * self.getVolume()

    def retainState(self, paramsToApply=None):
        """
        Restores a state before and after some operation.

        Parameters
        ----------
        paramsToApply : iterable
            Parameters that should be applied to the state after existing the state retainer. All
            others will be reverted to their values upon entering.

        Notes
        -----
        This should be used in a `with` statement.
        """
        return StateRetainer(self, paramsToApply)


class StateRetainer:
    """
    Retains state during some operations.

    This can be used to temporarily cache state, perform an operation, extract some info, and then
    revert back to the original state.

    * A state retainer is faster than restoring state from a database as it reduces the number of IO
      reads; however, it does use more memory.

    * This can be used on any object within the composite pattern via with
      ``[rabc].retainState([list], [of], [parameters], [to], [retain]):``.
      Use on an object up in the hierarchy applies to all objects below as well.

    * This is intended to work across MPI, so that if you were to broadcast the reactor the state
      would be correct; however the exact implication on ``parameters`` may be unclear.

    """

    def __init__(self, composite: Composite, paramsToApply=None):
        """
        Create an instance of a StateRetainer.

        Parameters
        ----------
        composite: Composite
            composite object to retain state (recursively)

        paramsToApply: iterable of parameters.Parameter
            Iterable of parameters.Parameter to retain updated values after `__exit__`. All other
            parameters are reverted to the original state, i.e. retained at the original value.
        """
        self.composite = composite
        self.paramsToApply = set(paramsToApply or [])

    def __enter__(self):
        self._enterExitHelper(lambda obj: obj.backUp())
        return self

    def __exit__(self, *args):
        self._enterExitHelper(lambda obj: obj.restoreBackup(self.paramsToApply))

    def _enterExitHelper(self, func):
        """Helper method for ``__enter__`` and ``__exit__``. ``func`` is a lambda to either
        ``backUp()`` or ``restoreBackup()``.
        """
        paramDefs = set()
        items = itertools.chain(
            (self.composite,),
            self.composite.iterChildrenWithMaterials(deep=True),
        )
        for child in items:
            if hasattr(child, "p"):
                # materials don't have Parameters
                paramDefs.update(child.p.paramDefs)
            func(child)
        for paramDef in paramDefs:
            func(paramDef)


def gatherMaterialsByVolume(objects: List[ArmiObject], typeSpec: TypeSpec = None, exact=False):
    """
    Compute the total volume of each material in a set of objects and give samples.

    Parameters
    ----------
    objects : list of ArmiObject
        Objects to look within. This argument allows clients to search though some subset of the
        three (e.g. when you're looking for all CLADDING components within FUEL blocks)

    typeSpec : TypeSpec
        Flags for the components to look at

    exact : bool
        Whether or not the TypeSpec is exact

    Notes
    -----
    This helper method is outside the main ArmiObject tree for the special clients that need to
    filter both by container type (e.g. Block type) with one set of flags, and Components with
    another set of flags.

    .. warning:: This is a **composition** related helper method that will likely be filed into
        classes/modules that deal specifically with the composition of things in the data model.
        Thus clients that use it from here should expect to need updates soon.
    """
    volumes = {}
    samples = {}
    for obj in objects:
        for c in obj.iterComponents(typeSpec, exact):
            vol = c.getVolume()
            matName = c.material.getName()
            volumes[matName] = volumes.get(matName, 0.0) + vol
            if matName not in samples:
                samples[matName] = c.material

    return volumes, samples


def getDominantMaterial(objects: List[ArmiObject], typeSpec: TypeSpec = None, exact=False):
    """
    Return the first sample of the most dominant material (by volume) in a set of objects.

    Warning
    -------
    This is a **composition** related helper method that will likely be filed into classes/modules
    that deal specifically with the composition of things in the data model. Thus clients that use
    it from here should expect to need updates soon.
    """
    volumes, samples = gatherMaterialsByVolume(objects, typeSpec, exact)

    if volumes:
        # find matName with max volume
        maxMatName = list(sorted(volumes.items(), key=lambda item: item[1])).pop()[0]
        # return this material. Note that if this material has properties like Zr-frac, enrichment,
        # etc. then this will just return one in the batch, not an average.
        return samples[maxMatName]

    return None
