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

:py:mod:`~armi.physics.neutronics.crossSectionGroupManager`
    Handles the management of different cross section "groups"

.. warning:: There is also some legacy and question-raising code in this module that
    is here temporarily while we finish untangling some of the neutronics
    plugins outside of ARMI.

"""
import os

import yamlize
import numpy
import tabulate

from armi import plugins
from armi.physics.neutronics.const import CONF_CROSS_SECTION
from armi.utils import directoryChangers
from armi import runLog


class NeutronicsPlugin(plugins.ArmiPlugin):
    """
    The built-in neutronics plugin with a few capabilities and a lot of state parameter definitions.
    """

    @staticmethod
    @plugins.HOOKIMPL
    def exposeInterfaces(cs):
        """
        Collect and expose all of the interfaces that live under the built-in neutronics package
        """
        from armi.physics.neutronics import crossSectionGroupManager
        from armi.physics.neutronics.fissionProductModel import fissionProductModel

        interfaceInfo = []
        for mod in (crossSectionGroupManager, fissionProductModel):
            interfaceInfo += plugins.collectInterfaceDescriptions(mod, cs)

        return interfaceInfo

    @staticmethod
    @plugins.HOOKIMPL
    def defineParameters():
        from . import parameters as neutronicsParameters

        return neutronicsParameters.getNeutronicsParameterDefinitions()

    @staticmethod
    @plugins.HOOKIMPL
    def defineEntryPoints():
        from armi.physics.neutronics import diffIsotxs

        entryPoints = [diffIsotxs.CompareIsotxsLibraries]

        return entryPoints

    @staticmethod
    @plugins.HOOKIMPL
    def defineSettings():
        from . import settings as neutronicsSettings
        from armi.physics.neutronics import crossSectionSettings
        from armi.physics.neutronics.fissionProductModel import (
            fissionProductModelSettings,
        )

        settings = [
            crossSectionSettings.XSSettingDef(
                CONF_CROSS_SECTION,
            )
        ]
        settings += neutronicsSettings.defineSettings()
        settings += fissionProductModelSettings.defineSettings()

        return settings

    @staticmethod
    @plugins.HOOKIMPL
    def defineSettingsValidators(inspector):
        """
        Check neutronics settings.
        """
        from armi.operators import settingsValidation  # avoid cyclic import
        from armi.scripts.migration.crossSectionBlueprintsToSettings import (
            migrateCrossSectionsFromBlueprints,
        )

        queries = []

        def blueprintsHasOldXSInput(path):
            with directoryChangers.DirectoryChanger(inspector.cs.inputDirectory):
                with open(os.path.expandvars(path)) as f:
                    for line in f:
                        if line.startswith("cross sections:"):
                            return True
            return False

        queries.append(
            settingsValidation.Query(
                lambda: inspector.cs["loadingFile"]
                and blueprintsHasOldXSInput(inspector.cs["loadingFile"]),
                "The specified blueprints input file '{0}' contains compound cross section settings. "
                "".format(inspector.cs["loadingFile"]),
                "Automatically move them to the settings file, {}? WARNING: if multiple settings files point "
                "to this blueprints input you must manually update the others.".format(
                    inspector.cs.path
                ),
                lambda: migrateCrossSectionsFromBlueprints(inspector.cs),
            )
        )
        return queries

    @staticmethod
    @plugins.HOOKIMPL
    def onProcessCoreLoading(core, cs):
        applyEffectiveDelayedNeutronFractionToCore(core, cs)


from .const import (
    GAMMA,
    NEUTRON,
    NEUTRONGAMMA,
    ALL,
    RESTARTFILES,
    INPUTOUTPUT,
    FLUXFILES,
)


# ARC and CCCC cross section file format names
COMPXS = "COMPXS"
PMATRX = "PMATRX"
GAMISO = "GAMISO"
ISOTXS = "ISOTXS"

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
    return GAMMA in cs["globalFluxActive"]


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
    return GAMMA in cs["genXS"]


def adjointCalculationRequested(cs):
    """Return true if an adjoint calculation is requested based on the ``neutronicsType`` setting."""
    return cs["neutronicsType"] in [ADJOINT_CALC, ADJREAL_CALC]


def realCalculationRequested(cs):
    """Return true if a real calculation is requested based on the ``neutronicsType`` type setting."""
    return cs["neutronicsType"] in ["real", "both"]


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
