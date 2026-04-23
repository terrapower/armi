# Copyright 2026 TerraPower, LLC
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

"""A simple base class to help define blocks in a Theta-R-Z geometry."""

from armi.reactor.blocks.block import Block


class ThRZBlock(Block):
    def getMaxArea(self):
        """Return the area of the Theta-R-Z block if it was totally full."""
        raise NotImplementedError("Cannot get max area of a TRZ block. Fully specify your geometry.")

    def radialInner(self):
        """Return a smallest radius of all the components."""
        innerRadii = self.getDimensions("inner_radius")
        smallestInner = min(innerRadii) if innerRadii else None
        return smallestInner

    def radialOuter(self):
        """Return a largest radius of all the components."""
        outerRadii = self.getDimensions("outer_radius")
        largestOuter = max(outerRadii) if outerRadii else None
        return largestOuter

    def thetaInner(self):
        """Return a smallest theta of all the components."""
        innerTheta = self.getDimensions("inner_theta")
        smallestInner = min(innerTheta) if innerTheta else None
        return smallestInner

    def thetaOuter(self):
        """Return a largest theta of all the components."""
        outerTheta = self.getDimensions("outer_theta")
        largestOuter = max(outerTheta) if outerTheta else None
        return largestOuter

    def axialInner(self):
        """Return the lower z-coordinate."""
        return self.getDimensions("inner_axial")

    def axialOuter(self):
        """Return the upper z-coordinate."""
        return self.getDimensions("outer_axial")

    def verifyBlockDims(self):
        """Perform dimension checks related to ThetaRZ blocks."""
        return
