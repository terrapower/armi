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
The Physics Packages are where the magic of physical simulation happens in an ARMI run.

.. tip:: The vast majority of physics capabilities are provided by :py:mod:`Plugins <armi.plugins>`.
    Thus, this package contains some fairly generic physics-related code that belongs in a reactor
    analysis framework.

Besides providing some generic physics-related capabilities, this package also provides a recommended
*physics namespace* for all ARMI plugins to follow. The physics namespaces we've come up with is
as follows:

fuelCycle
    Fuel management, fabrication, reprocessing, mass flow, etc.

neutronics
    Radiation transport, nuclear depletion, nuclear cross sections, reactivity coefficients,
    kinetics, etc.

safety
    Systems analysis in accident scenarios, source term, dose conversion, etc.

fuelPerformance
    Changes in fuel systems vs. burnup and time, including thermophysical modeling of
    fuel, cladding, fuel salt, etc.

thermalHydraulics
    Heat transfer, fluid flow, pressure drop, power cycles, you name it.

economics
    Economic modeling and cost estimation.

    .. important:: Yeah, we know that it is kind of a stretch to call economics a kind of physics.

We have found it very useful to use `Python namespace packages <https://packaging.python.org/guides/packaging-namespace-packages/>`_
to mirror this exact namespace in physics plugins that are outside of the ARMI framework. Thus, there can
be two totally separate plugins::

    IAEA/
        physics/
            neutronics/
                superSourceTerm/
                    __init__.py
                    plugin.py

and::

    IAEA/
        physics/
            economics/
                magwoodsbrain/
                    __init__.py
                    plugin.py


And then the associated ARMI-based app could import both ``IAEA.physics.neutronics.superSourceTerm`` and
``IAEA.physics.economics.magwoodsbrain``. Having a consistency in namespace along these lines is
quite nice.
"""
