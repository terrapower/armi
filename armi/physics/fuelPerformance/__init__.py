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
Generic fuel performance plugin package.

Fuel performance deals with addressing fuel system limits and predicting
behaviors that are coupled to other physics within the reactor. Often
fuel performance models address chemical, thermal and mechanical behaviors
of the fuel system.

The following general phenomena fall into the fuel performance category 
of physics for solid fuel (e.g., SFR, LWR, TRISO):

* chemical degradation on the inside of fuel cladding such as
  fuel-clad chemical interaction (FCCI)
* corrosion or erosion processes on the outside of the fuel cladding
* the fuel-clad mechanical interaction (FCMI) resulting in cladding stress 
  and strain
* pressurization of the fuel pin due to released fission gases
* high temperatures of the fuel which affect material properties and feedback
  during accident scenarios

Fuel performance is typically coupled with thermal analysis because the thermal
conditions of the fuel affects the performance and properties of the fuel
change with temperature and burnup.

In many cases, fuel performance is coupled with neutronic analysis as well,
because the fission gases are strong neutron absorbers. In some reactors,
significant composition changes during irradiation can influence neutronics
as well (e.g. sodium thermal bond being squeezed out of pins). Finally, 
fuel temperatures impact the Doppler reactivity coefficient.
"""
from .plugin import FuelPerformancePlugin
