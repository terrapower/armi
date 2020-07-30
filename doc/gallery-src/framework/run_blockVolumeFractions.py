"""
Computing Component Volume Fractions on a Block
===============================================

Given an :py:mod:`Block <armi.reactor.blocks.Block>`, compute
the component volume fractions. Re-assess these fractions 
as the temperatures of the fuel and structure components are 
increased uniformly.
"""

import collections

import tabulate
import matplotlib.pyplot as plt

import armi
armi.configure()

from armi import runLog
from armi.reactor.flags import Flags
from armi.reactor.tests.test_blocks import buildSimpleFuelBlock


def writeInitialVolumeFractions(b):
    """Write out the initial temperatures and component volume fractions."""
    runLog.info(f"Volume fractions of {len(b)} components within {b}:")
    headers = ["Component", "Temperature (C)", "Volume Fraction"]
    data = [(c, c.temperatureInC, volFrac) for c, volFrac in b.getVolumeFractions()]
    runLog.info(tabulate.tabulate(tabular_data=data, headers=headers))

def plotVolFracsWithComponentTemps(b, uniformTemps):
    """Plot the percent change in vol. fractions as fuel/structure temperatures are uniformly increased."""
    # Perform uniform temperature modifications of the fuel and structural
    # components.
    componentsToModify = b.getComponents([Flags.FUEL, Flags.CLAD, Flags.DUCT])
    
    initialVolFracs = {}
    relativeVolFracs = collections.defaultdict(list)
    for temp in uniformTemps:
    
        # Modify the fuel/structure components to the
        # same uniform temperature
        for c in componentsToModify:
            c.setTemperature(temp)
    
        # Iterate over all components and calculate the mass
        # and volume fractions
        for c in b:
            # Set the initial volume fractions at the first uniform temperature
            if temp == uniformTemps[0]:
                initialVolFracs[c] = c.getVolume()/b.getVolume()
            relativeVolFracs[c].append((c.getVolume()/b.getVolume() - initialVolFracs[c])/initialVolFracs[c] * 100.0)
            
    fig, ax = plt.subplots()
    
    for c in b.getComponents():
        ax.plot(uniformTemps, relativeVolFracs[c], label=c.name)
    
    ax.set_ylabel(f"% Change in Vol. Fraction from {uniformTemps[0]} C")
    ax.set_xlabel("Uniform Fuel/Structure Temperature, C")
    ax.legend()
    ax.grid()
    
    fig.show()

uniformTemps = [400.0, 500.0, 600.0, 700.0, 800.0, 900.0, 1200.0]
b = buildSimpleFuelBlock()

writeInitialVolumeFractions(b)
plotVolFracsWithComponentTemps(b, uniformTemps)