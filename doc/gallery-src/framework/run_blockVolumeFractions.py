# -*- coding: utf-8 -*-
"""
Computing Component Volume Fractions on a Block with Automatic Thermal Expansion
================================================================================

Given an :py:mod:`Block <armi.reactor.blocks.Block>`, compute
the component volume fractions. Assess the change in volume
of these components within the block as the temperatures of 
the fuel and structure components are uniformly increased.

Note: Thermal expansion is automatically considered with
material data defined within :py:mod:`materials <armi.materials>`.
"""

import collections

import tabulate
import matplotlib.pyplot as plt

from armi import configure

configure(permissive=True)

from armi.reactor.flags import Flags
from armi.reactor.tests.test_blocks import buildSimpleFuelBlock


def writeInitialVolumeFractions(b):
    """Write out the initial temperatures and component volume fractions."""
    headers = ["Component", "Temperature, °C", "Volume Fraction"]
    data = [(c, c.temperatureInC, volFrac) for c, volFrac in b.getVolumeFractions()]
    print(tabulate.tabulate(tabular_data=data, headers=headers) + "\n")


def plotVolFracsWithComponentTemps(b, uniformTemps):
    """Plot the percent change in vol. fractions as fuel/structure temperatures are uniformly increased."""
    # Perform uniform temperature modifications of the fuel and structural
    # components.
    componentsToModify = b.getComponents([Flags.FUEL, Flags.CLAD, Flags.DUCT])

    initialVols = {}
    relativeVols = collections.defaultdict(list)
    for tempInC in uniformTemps:

        print(f"Updating fuel/structure components to {tempInC} °C")
        # Modify the fuel/structure components to the
        # same uniform temperature
        for c in componentsToModify:
            c.setTemperature(tempInC)

        writeInitialVolumeFractions(b)

        # Iterate over all components and calculate the mass
        # and volume fractions
        for c in b:
            # Set the initial volume fractions at the first uniform temperature
            if tempInC == uniformTempsInC[0]:
                initialVols[c] = c.getVolume()

            relativeVols[c].append(
                (c.getVolume() - initialVols[c]) / initialVols[c] * 100.0
            )

    fig, ax = plt.subplots()

    for c in b.getComponents():
        ax.plot(uniformTempsInC, relativeVols[c], label=c.name)

    ax.set_title("Component Volume Fractions with Automatic Thermal Expansion")
    ax.set_ylabel(f"% Change in Volume from {uniformTempsInC[0]} °C")
    ax.set_xlabel("Uniform Fuel/Structure Temperature, °C")
    ax.legend()
    ax.grid()

    plt.show()


uniformTempsInC = [400.0, 500.0, 600.0, 700.0, 800.0, 900.0, 1200.0]
b = buildSimpleFuelBlock()

writeInitialVolumeFractions(b)
plotVolFracsWithComponentTemps(b, uniformTempsInC)
