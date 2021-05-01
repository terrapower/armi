"""
This subpackage reads and writes CCCC standard interface files for reactor physics codes.

Starting in the late 1960s, the computational nuclear analysis community recognized a need to
establish some standard file formats to exchange reactor descriptions and reactor physics
quantities. They formed the Committee on Computer Code Coordination (CCCC) and issued
several versions of their standards. The latest was issued in 1977 as [CCCC-IV]_. Many
reactor codes to this day use these files. This package provides a Python abstraction to
read many (though not necessarily all) of these files, manipulate the data, and
write them back out to disk.

.. [CCCC-IV] R. Douglas O'Dell, "Standard Interface Files and Procedures for Reactor Physics
             Codes, Version IV," LA-6941-MS, Los Alamos National Laboratory (September 1977).
             Web. doi:10.2172/5369298. (`OSTI <https://www.osti.gov/biblio/5369298>`_)

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
from .cccc import *
