"""
Hex block to RZ geometry conversion
===================================
Often, parts of a reactor model must be transformed to a different geometry in order to
perform a certain type of physics calculation. For example, in some fast reactor lattice
physics calculations, detailed descriptions of control assemblies must be mapped to
equivalent 1-D cylindrical models.

This example shows how a control assembly defined in full hex-pin detail can be
automatically converted to an equivalent 1-D RZ case, including an outer ring of fuel to
drive the case.

This conversion includes rings for control material, gap, cladding (on both sides of each
ring of control material), coolant, duct, and fuel. The color of the plot is proportional
to the mass density.

Given this transformation, a 1-D lattice physics solver can be executed to compute
accurate cross sections.

By automating these kinds of geometry conversions, ARMI allows core designers to maintain
the design in real geometry while still performing appropriate approximations for
efficient analysis.

.. warning::
    This uses :py:mod:`armi.reactor.converters.blockConverters`, which
    currently only works on a constrained set of hex-based geometries. For your systems,
    consider these an example and starting point and build your own converters as
    appropriate.

"""
import logging

from armi.reactor.tests import test_reactors
from armi.reactor.flags import Flags
from armi.reactor.converters import blockConverters
from armi import configure, runLog

# init ARMI logging tools
logging.setLoggerClass(runLog.RunLogger)

# configure ARMI
configure(permissive=True)

_o, r = test_reactors.loadTestReactor()

bFuel = r.core.getBlocks(Flags.FUEL)[0]
bControl = r.core.getBlocks(Flags.CONTROL)[0]
converter = blockConverters.HexComponentsToCylConverter(
    sourceBlock=bControl, driverFuelBlock=bFuel, numExternalRings=1
)
converter.convert()
converter.plotConvertedBlock()

# revert back to std library logging
logging.setLoggerClass(logging.Logger)
