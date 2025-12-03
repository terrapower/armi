*******
Outputs
*******

ARMI output files are described in this section. Many outputs may be generated during an ARMI run.
They fall into various categories:

Framework outputs
    Files like the **stdout** and the **database** are produced in nearly all runs.

Interface outputs
    Certain plugins/interfaces produce intermediate output files.

Physics kernel outputs
    If ARMI executes an external physics kernel during a run, its associated output files are often available in the
    working directory. These files are typically read by ARMI during the run, and relevant data is transferred onto the
    reactor model (and ends up in the ARMI **database**). If the user desires to retain all of the inputs and outputs
    associated with the physics kernel runs for a given time step, this can be specified with the ``savePhysicsIO``
    setting. For any time step specified in the list under ``savePhysicsIO``, a ``cXnY/`` folder will be created, and
    ARMI will store all inputs and outputs associated with each physics kernel executed at this time step in a folder
    inside of ``cXnY/``. The format for specifying a state point is 00X00Y for cycle X, step Y.

Together the output fully define the analyzed ARMI case.


The Standard Output
===================
The Standard Output (or **stdout**) is a running log of things an ARMI run prints out as it executes
a case. It shows what happened during a run, which inputs were used, which warnings were issued, and
in some cases, what the summary results are. Here is an excerpt::

        =========== Completed BOL Event ===========

        =========== Triggering BOC - cycle 0 Event ===========
        =========== 01 - main                 BOC - cycle 0 ===========
        [impt] Beginning of Cycle 0
        =========== 02 - fissionProducts      BOC - cycle 0 ===========
        =========== 03 - xsGroups             BOC - cycle 0 ===========
        [xtra] Generating representative blocks for XS
        [xtra] Cross section group manager summary

In a standard run, the various interfaces will loop through and print out messages according to the `verbosity`
setting. In multi-processing runs, the **stdout** shows messages from the primary node first and then shows information
from all other nodes below (with verbosity set by the `branchVerbosity` setting). Sometimes a user will want to set the
verbosity of just one module (.py file) in the code higher than the rest of ARMI, to do so they can set up a custom
logger by placing this line at the top of the file::

    runLog = logging.getLogger(__name__)

These single-module (file) loggers can be controlled using a the `moduleVerbosity` setting. All of
these logger verbosities can be controlled from the settings file, for example::

    branchVerbosity: debug
    moduleVerbosity:
        armi.reactor.reactors: info
    verbosity: extra

If there is an error, a useful message may be printed in the **stdout**, and a full traceback will
be provided in the associated **stderr** file.

Some Linux users tend to use the **tail** command to monitor the progress of an ARMI run::

    tail -f myRun.stdout

This provides live information on the progress.

.. _database-file:

The Database File
=================
The **database** file is a self-contained, binary representation of the state of the ARMI composite
model state during a simulation. The database contains full, plain-text of the input files that were
used to create the case. And for each time node, the values of all composite parameters as well as
layout information to help fully reconstruct the reactor data model.

Loading Reactor State
---------------------
Among other things, the database file can be used to recover an ARMI reactor model from any of the
time nodes that it contains. This can be useful for performing restart runs, or for doing custom
post-processing analysis. To load a reactor state, you will need to open the database file into a
``Database`` object. From there, you can call the :py:meth:`armi.bookkeeping.db.Database.load()`
method to get a recovered ``Reactor`` object. For instance, given a database file called
``myDatabase.h5``, we could load the reactor state at cycle 5, time node 2 with the following::

   from armi.bookkeeping.db import databaseFactory

   db = databaseFactory("myDatabase.h5", "r")

   # The underlying file is not left open unless necessary. Use the
   # handy context manager to temporarily open the file and
   # interact with the data:
   with db:
       r = db.load(5, 2)

.. note:: The cycles are 0-indexed, but the time nodes, in practice, are not. Therefore, cycle 5 above is actually the 6th cycle in the simulation. For cycle 5 with two time nodes, there will be three time steps saved to the database: c5n0 (BOC), c5n1 (time node 1), and c5n2 (time node 2).

Extracting Reactor History
--------------------------
Not only can the database reproduce reactor state for a given time node, it can also
extract a history of specific parameters for specific objects through the
:py:meth:`armi.bookkeeping.db.Database.getHistory()` and
:py:meth:`armi.bookkeeping.db.Database.getHistories()` methods.
For example, given the reactor object, ``r`` from the example above, we could get the
entire history of an assembly's ring, position and areal power density with the
following::

   from armi.reactor.flags import Flags

   # grab a fuel assembly from the reactor
   a = r.core.getAssemblies(Flags.FUEL)

   # Don't forget to open the database!
   with db:
       aHist = db.getHistory(a, ["ring", "pos", "arealPd"])


Extracting Settings and Blueprints
----------------------------------
As well as the reactor states for each time node, the database file also stores the
input files (blueprints and settings files) used to run the case that generated it.
These can be recovered using the `extract-inputs` ARMI entry point. Use `python -m armi
extract-inputs --help` for more information.

File format
-----------
The database file format is built on top of the HDF5 format. There are many tools
available for viewing, editing, and scripting HDF5 files. The ARMI database uses the
`h5py` package for interacting with the underlying data and metadata.
At a high level there are 3 things to know about HDF5:

1. **Groups** - Groups are named collections of datasets. Think of a group as a filesystem folder.
2. **Datasets** - Datasets are named values. If a group is a folder, a dataset is a file. Values are
   strongly typed (think `int`, `float`, `double`, but also whether it is big endian, little endian
   so that the file is portable across different systems). Values can be scalar, vector, or
   N-dimensional arrays.
3. **Attributes** - Attributes can exist on a dataset or a group to provide supplemental
   information about the group or dataset. We use attributes to indicate the ARMI database version
   that was used to create the database, the time the case was executed, and whether or not the
   case completed successfully. We also sometimes apply attributes to datasets to indicate if any
   special formatting or layout was used to store Parameter values or the like.

There are many other features of HDF5, but this is enough information to get started.

Database Structure
------------------
The broad strokes of the database structure is outlined below.

.. list-table:: Database structure
   :header-rows: 1
   :class: longtable

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
   * - ``/c{CC}n{NN}EOL/``
     - H5Group
     - A special time node, like the one above, where {CC} is the last cycle and {NN} is the last
       node. If this exists, it is meant to represent the EOL, which is perhaps a few days after the
       end of the last cycle, where fuel is decaying non-operationally.
   * - ``/c{CC}n{NN}/layout/``
     - H5Group
     - A group that contains  a description of the ARMI model within this timenode
   * - ``/c{CC}n{NN}/layout/name``
     - list of strings
     - ``comp.name``
   * - ``/c{CC}n{NN}/layout/type``
     - list of strings
     - ``type(comp).__name__`` -- The name of the component type. We can use this to
       construct a new object when reading. You could also use it to filter down to data
       that you care about using hdf5 directly.
   * - ``/c{CC}n{NN}/layout/serialNum``
     - list of int
     - ``comp.p.serialNum`` -- Serial number of the component. This number is unique
       within a component type.
   * - ``/c{CC}n{NN}/layout/location``
     - list of 3-tuple floats
     - ``tuple(comp.spatialLocator) or (0, 0, 0)`` -- Gives the location indices for a
       given component. Note these are relative, so there are duplicates.
   * - ``/c{CC}n{NN}/layout/locationType``
     - list of strings
     - ``type(comp.spatialLocator).__name__ or "None"`` -- The type name of the
       location.
   * - ``/c{CC}n{NN}/layout/indexInData``
     - list of int
     - The components are grouped by ``type(comp).__name__``. The integers are a mapping
       between the component and its index in the ``/c{CC}n{NN}/{COMP_TYPE}/`` group.
   * - ``/c{CC}n{NN}/layout/numChildren``
     - list of int
     - ``len(comp)`` -- The number of direct child composites this composite has.
       Notably, this is not a summation of all the children.
   * - ``/c{CC}n{NN}/layout/temperatures``
     - list of 2-tuple floats
     - ``(comp.InputTemperatureInC, comp.TemperatureInC) or (-900, -900)`` --
       Temperatures in for Component objects.
   * - ``/c{CC}n{NN}/layout/material``
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
       the ``/c{CC}n{NN}/layout/``. See the next table to see a description of the
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
:py:func:`armi.bookkeeping.db.database.packSpecialData` and
:py:func:`armi.bookkeeping.db.database.unpackSpecialData`. Refer to their implementations
and documentation for more details.

Loading Reactor State as Read-Only
----------------------------------
Another option you have, though it will probably come up less often, is to lead a ``Reactor`` object
from a database file in read-only mode. Mostly what this does is set all the parameters loaded into
the reactor data model to a read-only mode. This can be useful to ensure that downstream analysts
do not modify the data they are reading. It looks much like the usual database load::

   from armi.bookkeeping.db import databaseFactory

   db = databaseFactory("myDatabase.h5", "r")

   with db:
       r = db.loadReadOnly(5, 2)

Another common use for ``Database.loadReadOnly()`` is when you want to build a tool for analysts
that can open an ARMI database file without the ``App`` that created it. Solving such a problem
generically is hard-or-impossible, but assuming you probably know a lot about the ``App`` that
created an ARMI output file, this is usually doable in practice. To do so, you will want to look at
the :py:class:`PassiveDBLoadPlugin <armi.bookkeeping.db.passiveDBLoadPlugin.PassiveDBLoadPlugin>`.
This tool allows you to passively load an output database even if there are parameters or blueprint
sections that are unknown.
