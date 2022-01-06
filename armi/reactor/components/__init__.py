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

import math

import numpy

from armi import runLog
from armi.reactor.components.component import *  # pylint: disable=wildcard-import
from armi.reactor.components.basicShapes import *  # pylint: disable=wildcard-import
from armi.reactor.components.complexShapes import *  # pylint: disable=wildcard-import
from armi.reactor.components.volumetricShapes import *  # pylint: disable=wildcard-import


def factory(shape, bcomps, kwargs):
    """
    Build a new component object.

    Parameters
    ---------
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
            "Unrecognized component shape: '{}'\n"
            "Valid component names are {}".format(
                shape, ", ".join(ComponentType.TYPES.keys())
            )
        )

    _removeDimensionNameSpaces(kwargs)

    try:
        return class_(components=bcomps, **kwargs)
    except TypeError:
        # TypeError raised when kwarg is missing. We add extra information
        # to the error to indicate which component needs updating.
        runLog.error(
            f"Potentially invalid kwargs {kwargs} for {class_} of shape {shape}."
            " Check input."
        )
        raise


def _removeDimensionNameSpaces(attrs):
    """Some components use spacing in their dimension names, but can't internally."""
    for key in list(attrs.keys()):
        if " " in key:
            clean = key.replace(" ", "_")
            attrs[clean] = attrs.pop(key)


# Below are a few component base classes


class NullComponent(Component):
    r"""returns zero for all dimensions. is none."""

    def __cmp__(self, other):
        r"""be smaller than everything."""
        return -1

    def __lt__(self, other):
        return True

    def __bool__(self):
        r"""handles truth testing."""
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
    """

    pDefs = componentParameters.getUnshapedParameterDefinitions()

    def __init__(
        self,
        name,
        material,
        Tinput,
        Thot,
        area=numpy.NaN,
        modArea=None,
        isotopics=None,  # pylint: disable=too-many-arguments
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

    def getComponentArea(self, cold=False):
        """
        Get the area of this component in cm^2.

        Parameters
        ----------
        cold : bool, optional
            Compute the area with as-input dimensions instead of thermally-expanded
        """
        return self.p.area

    def setArea(self, val):
        self.p.area = val
        self.clearCache()

    def getBoundingCircleOuterDiameter(self, Tc=None, cold=False):
        """
        Approximate it as circular and return the radius.

        This is the smallest it can possibly be. Since this is used to determine
        the outer component, it will never be allowed to be the outer one.
        """
        return math.sqrt(self.p.area / math.pi)

    @staticmethod
    def fromComponent(otherComponent):
        """
        Build a new UnshapedComponent that has area equal to that of another component.

        This can be used to "freeze" a DerivedShape, among other things.
        """
        newC = UnshapedComponent(
            name=otherComponent.name,
            material=otherComponent.material,
            Tinput=otherComponent.inputTemperatureInC,
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
        area=numpy.NaN,
        op=None,
        isotopics=None,  # pylint: disable=too-many-arguments
        mergeWith=None,
        components=None,
        volume=numpy.NaN,
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

    def getComponentArea(self, cold=False):
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
    getNumberDensity

    Useful for situations where you want to give a block integrated flux, but ensure
    mass is never added to it

    See Also
    --------
    armi.reactor.batch.makeMgFluxBlock
    """

    def getNumberDensity(self, *args, **kwargs):
        """
        Always return 0 because this component has not mass
        """
        return 0.0

    def setNumberDensity(self, *args, **kwargs):
        """
        Never add mass
        """
        pass


class PositiveOrNegativeVolumeComponent(UnshapedVolumetricComponent):
    """
    A component that may have negative mass for removing mass from batches

    See Also
    --------
    armi.reactor.batch.makeMassAdditionComponent
    """

    def _checkNegativeVolume(self, volume):
        """
        Allow negative areas.
        """
        pass


class DerivedShape(UnshapedComponent):
    """
    This a component that does have specific dimensions, but they're complicated.

    Notes
    ----
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
        """Cannot compute volume until it is derived."""
        return self._deriveVolumeAndArea()

    def _deriveVolumeAndArea(self):
        """
        Derive the volume and area of ``DerivedShape``\ s.

        Notes
        -----
        If a parent exists, this will iterate over it and then determine
        both the volume and area based on its context within the scope
        of the parent object by considering the volumes and areas of
        the surrounding components.

        Since some components are volumetric shapes, this must consider the volume
        so that it wraps around in all three dimensions.

        But there are also situations where we need to handle zero-height blocks
        with purely 2D components. Thus we track area and volume fractions here
        when possible.
        """

        if self.parent is None:
            raise ValueError(
                f"Cannot compute volume/area of {self} without a parent object."
            )

        # Determine the volume/areas of the non-derived shape components
        # within the parent.
        siblingVolume = 0.0
        siblingArea = 0.0
        for sibling in self.parent.getChildren():
            if sibling is self:
                continue
            elif not self and isinstance(sibling, DerivedShape):
                raise ValueError(
                    f"More than one ``DerivedShape`` component in {self.parent} is not allowed."
                )

            siblingVolume += sibling.getVolume()
            try:
                if siblingArea is not None:
                    siblingArea += sibling.getArea()
            except:
                siblingArea = None

        remainingVolume = self.parent.getMaxVolume() - siblingVolume
        if siblingArea:
            remainingArea = self.parent.getMaxArea() - siblingArea

        # Check for negative
        if remainingVolume < 0:
            msg = (
                f"The component areas in {self.parent} exceed the maximum "
                f"allowable volume based on the geometry. Check that the "
                f"geometry is defined correctly.\n"
                f"Maximum allowable volume: {self.parent.getMaxVolume()} cm^3\n"
                f"Volume of all non-derived shape components: {siblingVolume} cm^3\n"
            )
            runLog.error(msg)
            raise ValueError(
                f"Negative area/volume errors occurred for {self.parent}. "
                "Check log for errors."
            )

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

    def getComponentArea(self, cold=False):
        """
        Get the area of this component in cm^2.

        Parameters
        ----------
        cold : bool, optional
            Ignored for this component
        """
        if self.parent.derivedMustUpdate:
            self.computeVolume()

        return self.p.area
