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

Neutronics encompasses the modeling of nuclear chain reactions and their associated transmutation and decay.

The ARMI Framework comes with a neutronics plugin that introduces two
independent interfaces:

:py:mod:`~armi.physics.neutronics.fissionProductModel`
    Handles fission product modeling

.. warning:: There is also some legacy and question-raising code in this module that
    is here temporarily while we finish untangling some of the neutronics
    plugins outside of ARMI.
"""
# ruff: noqa: F401, E402

import numpy
import tabulate

from armi import plugins
from armi import runLog


class NeutronicsPlugin(plugins.ArmiPlugin):
    """The built-in neutronics plugin with a few capabilities and a lot of state parameter definitions."""

    @staticmethod
    @plugins.HOOKIMPL
    def exposeInterfaces(cs):
        """Collect and expose all of the interfaces that live under the built-in neutronics package."""
        from armi.physics.neutronics.fissionProductModel import fissionProductModel

        return plugins.collectInterfaceDescriptions(fissionProductModel, cs)

    @staticmethod
    @plugins.HOOKIMPL
    def defineParameters():
        """Define parameters for the plugin."""
        from armi.physics.neutronics import parameters as neutronicsParameters

        return neutronicsParameters.getNeutronicsParameterDefinitions()

    @staticmethod
    @plugins.HOOKIMPL
    def defineEntryPoints():
        """Define entry points for the plugin."""
        from armi.physics.neutronics import diffIsotxs

        entryPoints = [diffIsotxs.CompareIsotxsLibraries]

        return entryPoints

    @staticmethod
    @plugins.HOOKIMPL
    def defineSettings():
        """Define settings for the plugin."""
        from armi.physics.neutronics import settings as neutronicsSettings
        from armi.physics.neutronics.fissionProductModel import (
            fissionProductModelSettings,
        )

        settings = []
        settings += neutronicsSettings.defineSettings()
        settings += fissionProductModelSettings.defineSettings()

        return settings

    @staticmethod
    @plugins.HOOKIMPL
    def defineSettingsValidators(inspector):
        """Implementation of settings inspections for neutronics settings."""
        from armi.physics.neutronics.settings import getNeutronicsSettingValidators
        from armi.physics.neutronics.fissionProductModel.fissionProductModelSettings import (
            getFissionProductModelSettingValidators,
        )

        settingsValidators = getNeutronicsSettingValidators(inspector)
        settingsValidators.extend(getFissionProductModelSettingValidators(inspector))
        return settingsValidators

    @staticmethod
    @plugins.HOOKIMPL
    def onProcessCoreLoading(core, cs, dbLoad):
        """Called whenever a Core object is newly built."""
        applyEffectiveDelayedNeutronFractionToCore(core, cs)

    @staticmethod
    @plugins.HOOKIMPL
    def getReportContents(r, cs, report, stage, blueprint):
        """Generates the Report Content for the Neutronics Report."""
        from armi.physics.neutronics import reports

        return reports.insertNeutronicsReport(r, cs, report, stage)


from armi.physics.neutronics.const import (
    ALL,
    FLUXFILES,
    GAMMA,
    INPUTOUTPUT,
    NEUTRON,
    NEUTRONGAMMA,
    RESTARTFILES,
)


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


def applyEffectiveDelayedNeutronFractionToCore(core, cs):
    """Process the settings for the delayed neutron fraction and precursor decay constants."""
    # Verify and set the core beta parameters based on the user-supplied settings
    beta = cs["beta"]
    decayConstants = cs["decayConstants"]

    # If beta is interpreted as a float, then assign it to
    # the total delayed neutron fraction parameter. Otherwise, setup the
    # group-wise delayed neutron fractions and precursor decay constants.
    reportTableData = []
    if isinstance(beta, float):
        core.p.beta = beta
        reportTableData.append(("Total Delayed Neutron Fraction", core.p.beta))

    elif isinstance(beta, list) and isinstance(decayConstants, list):
        if len(beta) != len(decayConstants):
            raise ValueError(
                f"The values for `beta` ({beta}) and `decayConstants` "
                f"({decayConstants}) are not consistent lengths."
            )

        core.p.beta = sum(beta)
        core.p.betaComponents = numpy.array(beta)
        core.p.betaDecayConstants = numpy.array(decayConstants)

        reportTableData.append(("Total Delayed Neutron Fraction", core.p.beta))
        reportTableData.append(
            ("Group-wise Delayed Neutron Fractions", core.p.betaComponents)
        )
        reportTableData.append(
            ("Group-wise Precursor Decay Constants", core.p.betaDecayConstants)
        )

    # Report to the user the values were not applied.
    if not reportTableData and (beta is not None or decayConstants is not None):
        runLog.warning(
            f"Delayed neutron fraction(s) - {beta} and decay constants"
            " - {decayConstants} have not been applied."
        )
    else:
        runLog.extra(
            tabulate.tabulate(
                tabular_data=reportTableData,
                headers=["Component", "Value"],
                tablefmt="armi",
            )
        )


def getXSTypeNumberFromLabel(xsTypeLabel: str) -> int:
    """
    Convert a XSID label (e.g. 'AA') to an integer.

    Useful for visualizing XS type in XTVIEW.

    2-digit labels are supported when there is only one burnup group.
    """
    return int("".join(["{:02d}".format(ord(si)) for si in xsTypeLabel]))


def getXSTypeLabelFromNumber(xsTypeNumber: int) -> int:
    """
    Convert a XSID label (e.g. 65) to an XS label (e.g. 'A').

    Useful for visualizing XS type in XTVIEW.

    2-digit labels are supported when there is only one burnup group.
    """
    try:
        if xsTypeNumber > ord("Z"):
            # two digit. Parse
            return chr(int(str(xsTypeNumber)[:2])) + chr(int(str(xsTypeNumber)[2:]))
        else:
            return chr(xsTypeNumber)
    except ValueError:
        runLog.error("Error converting {} to label.".format(xsTypeNumber))
        raise
