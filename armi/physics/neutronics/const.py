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
Constants and Enums.

In an independent file to minimize circular imports.
"""

CONF_CROSS_SECTION = "crossSectionControl"
#
# FAST_FLUX_THRESHOLD_EV is the energy threshold above which neutrons are considered "fast" [eV]
#
FAST_FLUX_THRESHOLD_EV = 100000.0  # eV

# CROSS SECTION LIBRARY GENERATION CONSTANTS
MAXIMUM_XS_LIBRARY_ENERGY = 1.4190675e7  # eV
ULTRA_FINE_GROUP_LETHARGY_WIDTH = 1.0 / 120.0

# LOWEST_ENERGY_EV cannot be zero due to integrating lethargy, and lethargy is undefined at 0.0
# The lowest lower boundary of many group structures such as any WIMS, SCALE or CASMO
# is 1e-5 eV, therefore it is chosen here. This number must be lower than all of the
# defined group structures. The chosen 1e-5 eV is rather arbitrary but expected to be low
# enough to support other group structures. For fast reactors, there will be
# no sensitivity at all to this value since there is no flux in this region.
LOWEST_ENERGY_EV = 1.0e-5


# Highest energy will typically depend on what physics code is being run, but this is
# a decent round number to use.
HIGH_ENERGY_EV = 1.5e07

# Particle types constants
GAMMA = "Gamma"
NEUTRON = "Neutron"
NEUTRONGAMMA = "Neutron and Gamma"

# Constants for neutronics setting controlling saving of files after neutronics calculation
# See setting 'neutronicsOutputsToSave'
ALL = "All"
RESTARTFILES = "Restart files"
INPUTOUTPUT = "Input/Output"
FLUXFILES = "Flux files"
