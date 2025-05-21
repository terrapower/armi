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
The neutronics physics package in the ARMI framework.

Neutronics encompasses the modeling of nuclear chain reactions and their associated transmutation
and decay.
"""
# ruff: noqa: F401
from enum import IntEnum

from armi.physics.neutronics.const import (
    ALL,
    FLUXFILES,
    GAMMA,
    INPUTOUTPUT,
    NEUTRON,
    NEUTRONGAMMA,
    RESTARTFILES,
)
from armi.physics.neutronics.plugin import NeutronicsPlugin

# ARC and CCCC cross section file format names
COMPXS = "COMPXS"
PMATRX = "PMATRX"
GAMISO = "GAMISO"
PMATRX_EXT = "pmatrx"
GAMISO_EXT = "gamiso"
ISOTXS = "ISOTXS"
DIF3D = "DIF3D"

# Constants for neutronics calculation types
ADJOINT_CALC = "adjoint"
REAL_CALC = "real"
ADJREAL_CALC = "both"

# Constants for boundary conditions

# All external boundary conditions are set to zero outward current
INFINITE = "Infinite"

# "Planar" external boundaries conditions are set to zero outward current
REFLECTIVE = "Reflective"

# Generalized boundary conditions D * PHI PRIME + A * PHI = 0 where A is user-specified constant,
# D is the diffusion coefficient, PHI PRIME and PHI are the outward current and flux at the
# external boundaries.
GENERAL_BC = "Generalized"

# The following boundary conditions are three approximations of the vacuum boundary condition
# in diffusion theory.
#    'Extrapolated': sets A to 0.4692 (in generalized BC) to have the flux vanishing at
#                    0.7104*transport mean free path through linear extrapolation. Derived for plane
#                    geometries - should be valid for complex geometries unless radius of curvature is
#                    comparable to the mean free path.
#    'ZeroSurfaceFlux': flux vanishes at the external boundary.
#    'ZeroInwardCurrent': set A to 0.5 (in generalized BC) to have Jminus = 0 at the external boundaries.
EXTRAPOLATED = "Extrapolated"
ZEROFLUX = "ZeroSurfaceFlux"
ZERO_INWARD_CURRENT = "ZeroInwardCurrent"


# Common settings checks
def gammaTransportIsRequested(cs):
    """
    Check if gamma transport was requested by the user.

    Arguments
    ---------
    cs : ARMI settings object
        Object containing the default and user-specified ARMI settings controlling the simulation

    Returns
    -------
    flag : bool
        Returns true if gamma transport is requested.
    """
    from armi.physics.neutronics.settings import CONF_GLOBAL_FLUX_ACTIVE

    return GAMMA in cs[CONF_GLOBAL_FLUX_ACTIVE]


def gammaXsAreRequested(cs):
    """
    Check if gamma cross-sections generation was requested by the user.

    Arguments
    ---------
    cs : ARMI settings object
        Object containing the default and user-specified ARMI settings controlling the simulation.

    Returns
    -------
    flag : bool
        Returns true if gamma cross section generation is requested.
    """
    from armi.physics.neutronics.settings import CONF_GEN_XS

    return GAMMA in cs[CONF_GEN_XS]


def adjointCalculationRequested(cs):
    """Return true if an adjoint calculation is requested based on the ``CONF_NEUTRONICS_TYPE`` setting."""
    from armi.physics.neutronics.settings import CONF_NEUTRONICS_TYPE

    return cs[CONF_NEUTRONICS_TYPE] in [ADJOINT_CALC, ADJREAL_CALC]


def realCalculationRequested(cs):
    """Return true if a real calculation is requested based on the ``CONF_NEUTRONICS_TYPE`` type setting."""
    from armi.physics.neutronics.settings import CONF_NEUTRONICS_TYPE

    return cs[CONF_NEUTRONICS_TYPE] in ["real", "both"]


class LatticePhysicsFrequency(IntEnum):
    """
    Enumeration for lattice physics update frequency options.

    NEVER = never automatically trigger lattice physics (a custom script could still trigger it)
    BOL = Beginning-of-life (c0n0)
    BOC = Beginning-of-cycle (c*n0)
    everyNode = Every interaction node (c*n*)
    firstCoupledIteration = every node + the first coupled iteration at each node
    all = every node + every coupled iteration

    Notes
    -----
    firstCoupledIteration only updates the cross sections during the first coupled iteration, but
    not on any subsequent iterations. This may be an appropriate approximation in some cases to save
    compute time, but each individual user should give careful consideration to whether this is the
    behavior they want for a particular application. The main purpose of this setting is to capture
    a large change in temperature distribution when running a snapshot at a different power/flow
    condition than the original state being loaded from the database.
    """

    never = 0
    BOL = 1
    BOC = 2
    everyNode = 3
    firstCoupledIteration = 4
    all = 5
