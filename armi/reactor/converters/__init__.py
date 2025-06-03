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
Contains code that can convert reactor models from one geometry to another.

Conversions between geometries are often needed in advance of a certain type of physics
calculation that cannot be done on the full 3-D detailed geometry. For example, sometimes
an analyst wants to convert a reactor from 3-D to R-Z in advance of a very fast running
neutronics solution.

Converting from one geometry to another while properly conserving mass or some other
parameter manually is tedious and error prone. So it's well-suited for automation with
ARMI.

This subpackage contains code that does a certain subset of conversions along those lines.

.. warning::
    Geometry conversions are relatively design-specific, so the converters in this
    subpackage are relatively limited in scope as to what they can convert, largely
    targeting hexagonal pin-type assemblies. If your geometry is different from this, this
    code is best considered as examples and starting points, as you will likely need to
    write your own converters in your own plugin. Of course, if your converter is
    sufficiently generic, we welcome it here.

    In other words, some of these converters may at some point migrate to a more
    design-specific plugin.


See Also
--------
armi.cases.inputModifiers
    Modify input files and re-write them.
"""
