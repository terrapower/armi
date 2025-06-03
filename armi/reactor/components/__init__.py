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
Components package contains components and shapes.

These objects hold the dimensions, temperatures, composition, and shape of reactor primitives.

.. _component-class-diagram:

.. pyreverse:: armi.reactor.components -A -k --ignore=componentParameters.py
    :align: center
    :alt: Component class diagram
    :width: 100%

    Class inheritance diagram for :py:mod:`armi.reactor.components`.
"""

# ruff: noqa: F405, I001
import math

import numpy as np

from armi import runLog
from armi.reactor.components.component import *  # noqa: F403
from armi.reactor.components.basicShapes import *  # noqa: F403
from armi.reactor.components.complexShapes import *  # noqa: F403
from armi.reactor.components.volumetricShapes import *  # noqa: F403


def factory(shape, bcomps, kwargs):
    """
    Build a new component object.

    Parameters
    ----------
    shape : str
        lowercase string corresponding to the component type name
    bcomps : list(Component)
        list of "sibling" components. This list is used to find component links, which are of the form
        ``<name>.<dimension``.
    kwargs : dict
        dictionary of inputs for the Component subclass's ``__init__`` method.
    """
    try:
        class_ = ComponentType.TYPES[shape]
    except KeyError:
        raise ValueError(
            "Unrecognized component shape: '{}'\nValid component names are {}".format(
                shape, ", ".join(ComponentType.TYPES.keys())
            )
        )

    _removeDimensionNameSpaces(kwargs)

    try:
        return class_(components=bcomps, **kwargs)
    except TypeError:
        # TypeError raised when kwarg is missing. We add extra information
        # to the error to indicate which component needs updating.
        runLog.error(f"Potentially invalid kwargs {kwargs} for {class_} of shape {shape}. Check input.")
        raise


def _removeDimensionNameSpaces(attrs):
    """Some components use spacing in their dimension names, but can't internally."""
    for key in list(attrs.keys()):
        if " " in key:
            clean = key.replace(" ", "_")
            attrs[clean] = attrs.pop(key)


# Below are a few component base classes


class NullComponent(Component):
    """Returns zero for all dimensions."""

    def __cmp__(self, other):
        """Be smaller than everything."""
        return -1

    def __lt__(self, other):
        return True

    def __bool__(self):
        """Handles truth testing."""
        return False

    __nonzero__ = __bool__  # Python2 compatibility

    def getBoundingCircleOuterDiameter(self, Tc=None, cold=False):
        return None

    def getDimension(self, key, Tc=None, cold=False):
        return 0.0


class UnshapedComponent(Component):
    """
    A component with undefined dimensions.

    Useful for situations where you just want to enter the area directly.

    For instance, when you want to model neutronic behavior of an assembly based
    on only knowing the area fractions of each material in the assembly.

    See Also
    --------
    DerivedShape : Useful to just fill leftover space in a block with a material
    """

    pDefs = componentParameters.getUnshapedParameterDefinitions()

    def __init__(
        self,
        name,
        material,
        Tinput,
        Thot,
        area=np.nan,
        modArea=None,
        isotopics=None,
        mergeWith=None,
        components=None,
    ):
        Component.__init__(
            self,
            name,
            material,
            Tinput,
            Thot,
            area=area,
            isotopics=isotopics,
            mergeWith=mergeWith,
            components=components,
        )
        self._linkAndStoreDimensions(components, modArea=modArea)

    def getComponentArea(self, cold=False, Tc=None):
        """
        Get the area of this component in cm^2.

        Parameters
        ----------
        cold : bool, optional
            If True, compute the area with as-input dimensions, instead of thermally-expanded.
        Tc : float, optional
            Temperature in C to compute the area at
        """
        if cold and Tc is not None:
            raise ValueError(f"Cannot compute component area at {Tc} and cold dimensions simultaneously.")
        coldArea = self.p.area
        if cold:
            return coldArea
        if Tc is None:
            Tc = self.temperatureInC

        return self.getThermalExpansionFactor(Tc) ** 2 * coldArea

    def getBoundingCircleOuterDiameter(self, Tc=None, cold=False):
        """
        Approximate it as circular and return the radius.

        This is the smallest it can possibly be. Since this is used to determine
        the outer component, it will never be allowed to be the outer one.

        Parameters
        ----------
        Tc : float
            Ignored for this component
        cold : bool, optional
            If True, compute the area with as-input dimensions, instead of thermally-expanded.

        Notes
        -----
        Tc is not used in this method for this particular component.
        """
        return 2 * math.sqrt(self.getComponentArea(cold=cold) / math.pi)

    def getCircleInnerDiameter(self, Tc=None, cold=False):
        """
        Component is unshaped; assume it is circular and there is no ID (return 0.0).

        Parameters
        ----------
        Tc : float, optional
            Ignored for this component
        cold : bool, optional
            Ignored for this component
        """
        return 0.0

    @staticmethod
    def fromComponent(otherComponent):
        """
        Build a new UnshapedComponent that has area equal to that of another component.

        This can be used to "freeze" a DerivedShape, among other things.

        Notes
        -----
        Components created in this manner will not thermally expand beyond the expanded
        area of the original component, but will retain their hot temperature.
        """
        newC = UnshapedComponent(
            name=otherComponent.name,
            material=otherComponent.material,
            Tinput=otherComponent.temperatureInC,
            Thot=otherComponent.temperatureInC,
            area=otherComponent.getComponentArea(),
        )

        return newC


class UnshapedVolumetricComponent(UnshapedComponent):
    """
    A component with undefined dimensions.

    Useful for situations where you just want to enter the volume directly.
    """

    is3D = True

    def __init__(
        self,
        name,
        material,
        Tinput,
        Thot,
        area=np.nan,
        op=None,
        isotopics=None,
        mergeWith=None,
        components=None,
        volume=np.nan,
    ):
        Component.__init__(
            self,
            name,
            material,
            Tinput,
            Thot,
            area=area,
            isotopics=isotopics,
            mergeWith=mergeWith,
            components=components,
        )
        self._linkAndStoreDimensions(components, op=op, userDefinedVolume=volume)

    def getComponentArea(self, cold=False, Tc=None):
        return self.getVolume() / self.parent.getHeight()

    def getComponentVolume(self):
        """Get the volume of the component in cm^3."""
        return self.getDimension("userDefinedVolume")

    def setVolume(self, val):
        self.setDimension("userDefinedVolume", val)
        self.clearCache()


class ZeroMassComponent(UnshapedVolumetricComponent):
    """
    A component that never has mass -- it always returns zero for getMass and
    getNumberDensity.

    Useful for situations where you want to give a block integrated flux, but ensure
    mass is never added to it

    See Also
    --------
    armi.reactor.batch.makeMgFluxBlock
    """

    def getNumberDensity(self, *args, **kwargs):
        """Always return 0 because this component has not mass."""
        return 0.0

    def setNumberDensity(self, *args, **kwargs):
        """Never add mass."""
        pass


class PositiveOrNegativeVolumeComponent(UnshapedVolumetricComponent):
    """
    A component that may have negative mass for removing mass from batches.

    See Also
    --------
    armi.reactor.batch.makeMassAdditionComponent
    """

    def _checkNegativeVolume(self, volume):
        """Allow negative areas."""
        pass


class DerivedShape(UnshapedComponent):
    """
    This a component that does have specific dimensions, but they're complicated.

    Notes
    -----
    - This component type is "derived" through the addition or
      subtraction of other shaped components (e.g. Coolant)
    - Because its area and volume are defined by other components,
      a DerivedShape's area and volume may change as the other
      components thermally expand. However the DerivedShape cannot
      drive thermal expansion itself, even if it is a solid component
      with non-zero thermal expansion coefficient
    """

    def getBoundingCircleOuterDiameter(self, Tc=None, cold=False):
        """
        The bounding circle for a derived component.

        Notes
        -----
        This is used to sort components relative to one another.

        There can only be one derived component per block, this is generally the coolant
        inside a duct. Under most circumstances, the volume (or area) of coolant will be
        greater than any other (single) component (i.e. a single pin) within the assembly.
        So, sorting based on the Dh of the DerivedShape will result in somewhat expected
        results.
        """
        if self.parent is None:
            # since this is only used for comparison, and it must be smaller than at
            # least one component, make it 0 instead of infinity.
            return 0.0
        else:
            # area = pi r**2 = pi d**2 / 4  => d = sqrt(4*area/pi)
            return math.sqrt(4.0 * self.getComponentArea() / math.pi)

    def computeVolume(self):
        """Cannot compute volume until it is derived.

        .. impl:: The volume of a DerivedShape depends on the solid shapes surrounding
            them.
            :id: I_ARMI_COMP_FLUID0
            :implements: R_ARMI_COMP_FLUID

            Computing the volume of a ``DerivedShape`` means looking at the solid
            materials around it, and finding what shaped space is left over in between
            them. This method calls the method ``_deriveVolumeAndArea``, which makes
            use of the fact that the ARMI reactor data model is hierarchical. It starts
            by finding the parent of this object, and then finding the volume of all
            the other objects at this level. Whatever is left over, is the volume of
            this object. Obviously, you can only have one ``DerivedShape`` child of any
            parent for this logic to work.
        """
        return self._deriveVolumeAndArea()

    def getMaxVolume(self):
        """
        The maximum volume of the parent Block.

        Returns
        -------
        vol : float
            volume in cm^3.
        """
        return self.parent.getMaxArea() * self.parent.getHeight()

    def _deriveVolumeAndArea(self):
        """
        Derive the volume and area of a ``DerivedShape``.

        Notes
        -----
        If a parent exists, this will iterate over it and then determine both the volume and area
        based on its context within the scope of the parent object by considering the volumes and
        areas of the surrounding components.

        Since some components are volumetric shapes, this must consider the volume so that it wraps
        around in all three dimensions.

        But there are also situations where we need to handle zero-height blocks with purely 2D
        components. Thus we track area and volume fractions here when possible.
        """
        if self.parent is None:
            raise ValueError(f"Cannot compute volume/area of {self} without a parent object.")

        # Determine the volume/areas of the non-derived shape components within the parent.
        siblingVolume = 0.0
        siblingArea = 0.0
        for sibling in self.parent:
            if sibling is self:
                continue
            elif not self and isinstance(sibling, DerivedShape):
                raise ValueError(f"More than one ``DerivedShape`` component in {self.parent} is not allowed.")

            siblingVolume += sibling.getVolume()
            try:
                if siblingArea is not None:
                    siblingArea += sibling.getArea()
            except Exception:
                siblingArea = None

        remainingVolume = self.getMaxVolume() - siblingVolume
        if siblingArea:
            remainingArea = self.parent.getMaxArea() - siblingArea

        # Check for negative
        if remainingVolume < 0:
            msg = (
                f"The component areas in {self.parent} exceed the maximum "
                "allowable volume based on the geometry. Check that the "
                "geometry is defined correctly.\n"
                f"Maximum allowable volume: {self.getMaxVolume()} "
                f"cm^3\nVolume of all non-derived shape components: {siblingVolume} cm^3\n"
            )
            runLog.error(msg)
            raise ValueError(f"Negative area/volume errors occurred for {self.parent}. Check log for errors.")

        height = self.parent.getHeight()
        if not height:
            # special handling for 0-height blocks
            if not remainingArea:
                raise ValueError(f"Cannot derive area in 0-height block {self.parent}")
            self.p.area = remainingArea
        else:
            self.p.area = remainingVolume / height

        return remainingVolume

    def getVolume(self):
        """
        Get volume of derived shape.

        The DerivedShape must pay attention to all of the companion objects, because if
        they change, this changes.  However it's inefficient to always recompute the
        derived volume, so we have to rely on the parent to know if anything has changed.

        Since each parent is only allowed one DerivedShape, we can reset the update flag
        here.

        Returns
        -------
        float
            volume of component in cm^3.
        """
        if self.parent.derivedMustUpdate:
            # tell _updateVolume to update it during the below getVolume call
            self.p.volume = None
            self.parent.derivedMustUpdate = False
        vol = UnshapedComponent.getVolume(self)
        return vol

    def getComponentArea(self, cold=False, Tc=None):
        """
        Get the area of this component in cm^2.

        Parameters
        ----------
        cold : bool, optional
            If True, compute the area with as-input dimensions, instead of thermally-expanded.
        Tc : float, optional
            Temperature in C to compute the area at
        """
        if cold and Tc is not None:
            raise ValueError(f"Cannot compute component area at {Tc} and cold dimensions simultaneously.")

        if cold:
            # At cold temp, the DerivedShape has the area of the parent minus the other siblings
            parentArea = self.parent.getMaxArea()
            # NOTE: Here we assume there is one-and-only-one DerivedShape in each Component
            siblings = sum([c.getArea(cold=True) for c in self.parent if not isinstance(c, DerivedShape)])
            return parentArea - siblings

        if Tc is not None:
            # The DerivedShape has the area of the parent minus the other siblings
            parentArea = self.parent.getMaxArea()
            # NOTE: Here we assume there is one-and-only-one DerivedShape in each Component
            siblings = sum([c.getArea(Tc=Tc) for c in self.parent if not isinstance(c, DerivedShape)])
            return parentArea - siblings

        if self.parent.derivedMustUpdate:
            self.computeVolume()

        return self.p.area
