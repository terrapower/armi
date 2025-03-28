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
"""Fuel performance utilities."""

from armi.reactor.flags import Flags


def applyFuelDisplacement(block, displacementInCm):
    r"""
    Expands the fuel radius in a pin by a number of cm.

    Assumes there's thermal bond in it to displace.
    This adjusts the dimension of the fuel while conserving its mass.

    The bond mass is not conserved; it is assumed to be pushed up into the plenum
    but the modeling of this is not done yet by this method.

    .. warning:: A 0.5% buffer is included to avoid overlaps. This should be analyzed
        in detail as a methodology before using in any particular analysis.

    .. math::

        n V = n\prime V\prime
        n\prime = \frac{V}{V\prime} n

    """
    clad = block.getComponent(Flags.CLAD)
    fuel = block.getComponent(Flags.FUEL)
    originalHotODInCm = fuel.getDimension("od")
    cladID = clad.getDimension("id")
    # do not swell past cladding ID! (actually leave 0.5% buffer for thermal expansion)
    newHotODInCm = min(cladID * 0.995, originalHotODInCm + displacementInCm * 2)
    fuel.setDimension("od", newHotODInCm, retainLink=True, cold=False)
    # reduce number density of fuel to conserve number of atoms (and mass)
    fuel.changeNDensByFactor(originalHotODInCm**2 / newHotODInCm**2)


def gasConductivityCorrection(tempInC: float, porosity: float, morphology: int = 2):
    """
    Calculate the correction to conductivity for a porous, gas-filled solid.

    Parameters
    ----------
    tempInC
        temperature in celsius
    porosity
        fraction of open/total volume
    morphology, optional
        correlation to use regarding pore morphology (default 2 is irregular
        porosity for conservatism)

    Returns
    -------
    chi : float
        correction to conductivity due to porosity (should be multiplied)

    Notes
    -----
    Morphology is treated different by different models:

    0, no porosity correction
    1, bauer equation, spherical porosity
    2, bauer equation, irregular porosity
    3, bauer equation, mixed morphology, above 660, spherical. Below 660, irregular
    4, maxwell-eucken equation, beta=1.5

    Source1 : In-Pile Measurement of the Thermal Conductivity of Irradiated Metallic Fuel, T.H. Bauer J.W. Holland.
              Nuclear Technology, Vol. 110, 1995. Pages 407-421
    Source2 : The Porosity Dependence of the Thermal Conductivity for Nuclear Fuels, G. Ondracek B. Schulz.
              Journal of Nuclear Materials, Vol. 46, 1973. Pages 253-258
    """
    if morphology == 0:
        chi = 1.0
    elif morphology == 1:
        epsilon = 1.0
        chi = (1.0 - porosity) ** ((3.0 / 2.0) * epsilon)
    elif morphology == 2:
        epsilon = 1.72
        chi = (1.0 - porosity) ** ((3.0 / 2.0) * epsilon)
    elif morphology == 3:
        epsilon = 1.0
        if tempInC < 660:
            epsilon = 1.72
        else:
            epsilon = 1.00
        chi = (1.0 - porosity) ** ((3.0 / 2.0) * epsilon)
    elif morphology == 4:
        chi = (1.0 - porosity) / (1.0 + 1.5 * porosity)

    return chi
