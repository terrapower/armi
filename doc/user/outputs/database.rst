*****************
The Database File
*****************

The **database** file is a self-contained complete (or nearly complete) binary
representation of the ARMI composite model state during a case. The database contains
the text of the input files that were used to create the case, and for each time node,
the values of all composite parameters as well as layout information to help fully
reconstruct the structure of the reactor model.

File format
===========

The database file format is built on top of the HDF5 format. There are many tools
available for viewing, editing, and scripting HDF5 files. The ARMI database uses the
`h5py` package for interacting with the underlying data and metadata.
At a high level there are 3 things to know about HDF5:

1. Groups - groups are named collections of datasets. You might think of a group as a
   filesystem folder.
2. Datasets - Datasets are named values. If a group is a folder, a dataset
   is a file. Values are
   strongly typed (think `int`, `float`, `double`, but also whether it is big endian,
   little endian so that the file is portable across different systems). Values can be
   scalar, vector, or N-dimensional arrays.
3. Attributes - attributes can exist on a dataset or a group to provide supplemental
   information about the group or dataset. We use attributes to indicate the ARMI
   database version that was used to create the database, the time the case was
   executed, and whether or not the case completed successfully. We also sometimes apply
   attributes to datasets to indicate if any special formatting or layout was used to
   store Parameter values or the like.

There are many other features of HDF5, but from a usability standpoint that is enough
information to get started.

Database Structure
==================
The database structure is outlined below. This shows the broad strokes of how the
database is put together, but many more details may be gleaned from the in-line
documentation of the database modules.

.. list-table:: Database structure
   :header-rows: 1

   * - Name
     - Type
     - Description
   * - ``/``
     - H5Group
     - root node
   * - ``/inputs/``
     - H5Group
     - A group that contains all inputs
   * - ``/inputs/settings``
     - string
     - A representation of the settings file that was used to create the case
   * - ``/inputs/geomFile``
     - string
     - A representation of the geometry file used to create the case
   * - ``/inputs/blueprints``
     - string
     - A representation of the blueprints file that used to create the case
   * -
     -
     -
   * - ``/c{CC}n{NN}/``
     - H5Group
     - A group that contains the ARMI model for a specific cycle {CC} and time node
       {NN}. For the following, there may be a bit of pseudo-code to explain the origin
       of data. ``comp`` is any old component within the ARMI model hierarchy.

       Also, it is important to note that all components are flattened and then grouped
       by type.
   * - ``/c{CC}n{NN}/hierarchy/``
     - H5Group
     - A group that contains  a description of the ARMI model within this timenode
   * - ``/c{CC}n{NN}/hierarchy/name``
     - list of strings
     - ``comp.name``
   * - ``/c{CC}n{NN}/hierarchy/type``
     - list of strings
     - ``type(comp).__name__`` -- The name of the component type. We can use this to
       construct a new object when reading. You could also use it to filter down to data
       that you care about using hdf5 directly.
   * - ``/c{CC}n{NN}/hierarchy/serialNum``
     - list of int
     - ``comp.p.serialNum`` -- Serial number of the component. This number is unique
       within a component type.
   * - ``/c{CC}n{NN}/hierarchy/location``
     - list of 3-tuple floats
     - ``tuple(comp.spatialLocator) or (0, 0, 0)`` -- Gives the location indices for a
       given component. Note these are relative, so there are duplicates.
   * - ``/c{CC}n{NN}/hierarchy/locationType``
     - list of strings
     - ``type(comp.spatialLocator).__name__ or "None"`` -- The type name of the
       location.
   * - ``/c{CC}n{NN}/hierarchy/indexInData``
     - list of int
     - The components are grouped by ``type(comp).__name__``. The integers are a mapping
       between the component and its index in the ``/c{CC}n{NN}/{COMP_TYPE}/`` group.
   * - ``/c{CC}n{NN}/hierarchy/numChildren``
     - list of int
     - ``len(comp)`` -- The number of direct child composites this composite has.
       Notably, this is not a summation of all the children.
   * - ``/c{CC}n{NN}/hierarchy/temperatures``
     - list of 2-tuple floats
     - ``(comp.InputTemperatureInC, comp.TemperatureInC) or (-900, -900)`` --
       Temperatures in for Component objects.
   * - ``/c{CC}n{NN}/hierarchy/material``
     - list of string
     - ``type(comp.material).__name__ or ""`` -- Name of the associated material for an
       Component.
   * -
     -
     -
   * - ``/c{CC}n{NN}/{COMP_TYPE}/``
     - H5Group
     - ``{COMP_TYPE}`` corresponds to the ``type(comp).__name__``.
   * - ``/c{CC}n{NN}/{COMP_TYPE}/{PARAMETER}``
     - list of inferred data
     - Values for all parameters for a specific component type, in the order defined by
       the ``/c{CC}n{NN}/hierarchy/``. See the next table to see a description of the
       attributes.


Python supports a rich and dynamic type system, which is sometimes difficult to
represent with the HDF5 format. Namely, HDF5 only supports dense, homogeneous
N-dimensional collections of data in any given dataset. Some parameter values do not fit
into this mold. Examples of tricky cases are:

* Representing ``None`` values interspersed among a bunch of ``floats``
* Jagged arrays, where each "row" of a matrix has a different number of entries (or
  higher-dimensional analogs)
* Dictionaries

None of these have a direct representation in HDF5. Therefore, the parameter values on
the composite model sometimes need to be manipulated to fit into the HDF5 format, while
still being able to faithfully reconstruct the original data. To accomplish this, we use
HDF5 dataset attributes to indicate when some manipulation is necessary. Writing
such special data to the HDF5 file and reading it back again is accomplished with the
:py:func:`armi.bookkeeping.db.database3.packSpecialData` and
:py:func:`armi.bookkeeping.db.database3.packSpecialData`. Refer to their implementations
and documentation for more details.
