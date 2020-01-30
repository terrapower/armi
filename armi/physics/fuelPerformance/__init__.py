"""
Generic fuel performance plugin package.

Fuel performance deals with how nuclear fuel evolves chemically and mechanically with burnup.
It is often a key performance limiter in nuclear reactor design.

The following general phenomena fall into the fuel performance category of physics:

* the fission gas pressure build-up in a solid fuel pin
* the fuel-clad chemical interaction (FCCI) on the inside of fuel cladding
* the fuel-clad mechanical interaction (FCMI)

Fuel performance is always coupled with thermal analysis because the thermal
properties of the fuel change with burnup.

In many cases, fuel performance is coupled with neutronic analysis as well,
because the fission gases are strong neutron absorbers. In some reactors,
significant composition changes during irradiation can influence neutronics
as well (e.g. sodium thermal bond being squeezed out of pins.
"""
from .plugin import FuelPerformancePlugin
