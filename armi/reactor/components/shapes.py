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
Component subclasses that have shape.
"""
import math

import numpy

from armi.reactor.components import Component
from armi.reactor.components import componentParameters


class NullComponent(Component):
    r"""returns zero for all dimensions. is none. """

    def __cmp__(self, other):
        r"""be smaller than everything. """
        return -1

    def __lt__(self, other):
        return True

    def __bool__(self):
        r"""handles truth testing. """
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
        op=None,
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
        self._linkAndStoreDimensions(components, op=op, modArea=modArea)

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


class UnshapedVolumetricComponent(UnshapedComponent):
    """
    A component with undefined dimensions.

    Useful for situations where you just want to enter the volume directly.

    See Also
    --------
    armi.reactor.batch.Batch
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

    def setVolume(self, volume):
        self.setDimension("userDefinedVolume", volume)
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


class ShapedComponent(Component):
    """A component with well-defined dimensions."""


class DerivedShape(UnshapedComponent):
    """
    This a component that does have specific dimensions, but they're complicated.

    Notes
    ----
    - This component type is "derived" through the addition or
      subtraction of other shaped components (e.g. Coolant)
    """

    def getBoundingCircleOuterDiameter(self, Tc=None, cold=False):
        """
        The bounding circle for a derived component.

        Notes
        -----
        This is used to sort components relative to one another.

        There can only be one derived component per block, this is generally the coolant inside a
        duct. Under most circumstances, the volume (or area) of coolant will be greater than any
        other (single) component (i.e. a single pin) within the assembly. So, sorting based on the
        Dh of the DerivedShape will result in somewhat expected results.
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
        return self.parent._deriveUndefinedVolume()  # pylint: disable=protected-access

    def getVolume(self):
        """
        Get volume of derived shape.

        The DerivedShape must pay attention to all of the companion objects, because if they change, this changes.
        However it's inefficient to always recompute the derived volume, so we have to rely on the parent to know
        if anything has changed.

        Since each parent is only allowed one DerivedShape, we can reset the update flag here.

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
