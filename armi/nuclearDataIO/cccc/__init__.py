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
This subpackage reads and writes CCCC standard interface files for reactor physics codes.

Starting in the late 1960s, the computational nuclear analysis community recognized a need to
establish some standard file formats to exchange reactor descriptions and reactor physics
quantities. They formed the Committee on Computer Code Coordination (CCCC) and issued
several versions of their standards. The latest was issued in 1977 as [CCCC-IV]_. Many
reactor codes to this day use these files. This package provides a Python abstraction to
read many (though not necessarily all) of these files, manipulate the data, and
write them back out to disk.

Section IV of [CCCC-IV]_ defines the standard interface files that were created by the
CCCC. In addition to the standard files listed in this document, software like DIF3D,
PARTISN, and other reactor physics codes may have their own code-dependent interface files.
In most cases, they follow a similar structure and definition as the standardized formats,
but were not general enough to be used and implemented across all codes. The following
are listed as the standard interface files:

* ISOTXS (:py:mod:`armi.nuclearDataIO.cccc.isotxs`) - Nuclide (isotope) - ordered, multigroup
  neutron cross section data
* GRUPXS - Group-ordered, isotopic, multigroup neutron cross section data.
* BRKOXS - Bondarenko (Russian format) self-shielding data
* DLAYXS (:py:mod:`armi.nuclearDataIO.cccc.dlayxs`) - Delayed neutron precursor data
* ISOGXS (:py:mod:`armi.nuclearDataIO.cccc.gamiso`) - Nuclide (isotope) - ordered, multigroup
  gamma cross section data
* GEODST (:py:mod:`armi.nuclearDataIO.cccc.geodst`) - Geometry description
* NDXSRF - Nuclear density and cross section referencing data
* ZNATDN - Zone and subzone atomic densities
* SEARCH - Criticality search data
* SNCON - Sn (Discrete Ordinates) constants
* FIXSRC (:py:mod:`armi.nuclearDataIO.cccc.fixsrc`) - Distributed and surface fixed sources
* RTFLUX (:py:mod:`armi.nuclearDataIO.cccc.rtflux`) - Regular total (scalar) neutron flux
* ATFLUX (:py:mod:`armi.nuclearDataIO.cccc.rtflux`) - Adjoint total (scalar) neutron flux
* RCURNT - Regular neutron current
* ACURNT - Adjoint neutron current
* RAFLUX - Regular angular neutron flux
* AAFLUX - Adjoint angular neutron flux
* RZFLUX (:py:mod:`armi.nuclearDataIO.cccc.rzflux`) - Regular, zone-avearged flux by neutron group
* PWDINT (:py:mod:`armi.nuclearDataIO.cccc.pwdint`) - Power densitiy by mesh interval
* WORTHS - Reactivity (per cc) by mesh interval

Other code-dependent interface files may also be included in this package but should be
documented which software they are created from and used for. The file structures should
also be provided in the module-level docstrings.

.. [CCCC-IV] R. Douglas O'Dell, "Standard Interface Files and Procedures for Reactor Physics
             Codes, Version IV," LA-6941-MS, Los Alamos National Laboratory (September 1977).
             Web. doi:10.2172/5369298. (`OSTI <https://www.osti.gov/biblio/5369298>`__)

Using the system
----------------
Most supported files are in their own module. Each has their own :py:class:`cccc.DataContainer` to
hold the data and one or more :py:class:`cccc.Stream` objects representing different I/O formats.
The general pattern is to use any of the following methods on a ``Stream`` object:

* :py:meth:`cccc.Stream.readBinary`
* :py:meth:`cccc.Stream.readAscii`
* :py:meth:`cccc.Stream.writeBinary`
* :py:meth:`cccc.Stream.writeAscii`

For example, to get an RTFLUX data structure from a binary file named ``RTFLUX``, you run::

>>> from armi.nuclearDataIO.cccc import rtflux
>>> rtfluxData = rtflux.RtfluxStream.readBinary("RTFLUX")

Then if you want to write that data to an ASCII file named ``rtflux.ascii``, you run:

>>> rtflux.RtfluxStream.writeAscii(rtfluxData, "rtflux.ascii")

Implementation details
----------------------
We have come up with a powerful but somewhat confusing-at-first implementation that allows
us to define the structure of the files in code just once, in a way that can both read and write
the files. Many methods start with the prefix ``rw`` to indicate that they are used
during both reading and writing.

Normal users of this code do not need to know the implementation details.

Discussion
----------
While loading from stream classmethods is explicit and nice and all, there has been some
talk about moving the read/write ascii/binary methods to the data classes for
implementations that use data structures. This would hide the Stream subclasses from
users, which may be appropriate. On the other hand, logic to select which stream
subclass to user (e.g. adjoint vs. real) will have to be moved into the
data classes.

Notes
-----
A CCCC record consists of a leading and ending integer, which indicates the size of the record in
bytes. (This is actually just FORTRAN unformatted sequential files are written, see e.g.
https://gcc.gnu.org/onlinedocs/gfortran/File-format-of-unformatted-sequential-files.html)
As a result, it is possible to perform a check when reading in a record to determine if it
was read correctly, by making sure the record size at the beginning and ending of a record are
always equal.

There are similarities between this code and that in the PyNE cccc subpackage.
This is the original source of the code. TerraPower authorized the publication
of some of the CCCC code to the PyNE project way back in the 2011 era. This code
has since been updated significantly to both read and write the files.

This was originally inspired by Prof. James Paul Holloway's alpha
release of ccccutils written in c++ from 2001.
"""
from armi.nuclearDataIO.cccc.cccc import *  # noqa: F403
