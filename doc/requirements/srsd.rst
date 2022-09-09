**************************************************
Software Requirement Specification Document (SRSD)
**************************************************


---------------
Business Impact
---------------

#. The ``database`` package is used to restart runs, analyze results, and determine when changes are introduced to otherwise identical cases in ARMI. The ``database`` package is considered high risk.
#. The ``report`` package is one of many tools available for viewing case details and is intended purely for developer or analyst feedback on run specifications and results, not as a means of altering the run. Thus the ``report`` package is low risk.
#. The ``blueprints`` package interprets user input into an ARMI reactor model. If done incorrectly, ARMI simulations would be unreliable and inaccurate. ARMI is used for informing core designs, engineering calculations, and safety bases; therefore, the bluperints package is considered high risk.
#. The ``settings`` package contains a substantive amount of the run's definition. Problems in the settings system can invalidate runs. If a user supplies one piece of input, say the setting value that dictates which reactor-defining loading blueprints files to use, and the system performs misleadingly then any subsequent analysis would be invalidated. As this is the principle system of user interaction with ARMI, poor system design choices would aggravate the user experience and decrease user engagement. Fortunately, the errors are easily traced and replicated as the system itself is not complicated. Therefore, the settings package is considered high risk.
#. The ``operator`` package is paramount to every facility the code offers, affecting every aspect of design. Thus, the data model modules are high risk.
#. The ``fissionProductModel`` package has substantial impact on the results of the neutronic calculations that affect the plant design. Thus, it falls under the **high risk** impact level.
#. The ``reactor`` package contains the majority of state information throughout a case. Issues in it
could propagate and invalidate results derived from ARMI to perform design and analysis. Therefore, the ``reactor`` package is considered *high risk*.


--------------------
Applicable Documents
--------------------

..
   TODO: Do this by topic


-----------------------
Functional Requirements
-----------------------

.. req:: The database shall maintain fidelity of data.
   :id: REQ_DB_FIDELITY
   :status: implemented, needs test

The database shall faithfully represent the possessed information and not alter its contents, retrieving the data exactly as input.

.. req:: The database shall allow case restarts.
   :id: REQ_DB_RESTARTS
   :status: implemented, needs test

The state information representing as near as possible the entirety of the run when the database write was executed, shall be retrievable to restore the previous case to a particular point in time for further use by analysts.

.. req:: The database shall accept all pythonic primitive data types.
   :id: REEQ_DB_PRIMITIVES
   :status: implemented, needs test

To facilitate the storage of data, any Pythonic primitive data type shall be valid as an entrant into the database.

.. req:: The database shall not accept abstract data types excluding pythonic ``None``.
   :id: REQ_DB_NONE
   :status: implemented, needs test

Given the ubiquity of Python's ``None`` the database shall support its inclusion as a valid entry for data. There will be no support for any abstract data type beyond None.

.. req:: The report package shall maintain data fidelity.
   :id: REQ_REPORT_FIDELITY
   :status: implemented, needs more tests

The report package shall not modify or subvert data integrity as it reports the information out to the user.


..
   TODO: blueprints need some interface and I/O reqs

.. req:: The settings package shall not accept ambiguous setting definitions.
   :id: REQ_SETTINGS_UNAMBIGUOUS
   :status: implemented, needs more tests

Settings defined in the system must have both the intended data type and default value defined, or it is considered incomplete and therefore invalid. Additionally the system shall not accept multiple definitions of the same name.

TODO: This may be tested by a unit test loading in duplicate setting definitions or cases where a definition does not provide adequate details.

   .. req:: Settings shall have unique, case-insensitive names.
      :id: REQ_SETTINGS_UNAMBIGUOUS_NAME
      :status: implemented, needs more tests

   No two settings may share names.

   TODO: This may be tested by a unit test loading two similar names

   .. req:: Settings shall not allow dynamic typing.
      :id: REQ_SETTINGS_UNAMBIGUOUS_TYPE
      :status: implemented, needs more tests

   Settings shall exist exclusively as a single, primitive datatype, as chosen by the setting definition.

   TODO: This may be tested by unit tests attempting to subvert the contained data type

.. req:: Settings shall support more complex rule association to further customize each setting's behavior.
   :id: REQ_SETTINGS_RULES
   :status: implemented, needs more tests

It shall be possible to support a valid list or range of values for any given setting.

TODO: This may be tested by attempting to disobey specified maximums and minimums on numerical settings in a unit test

.. req:: Setting addition, renaming, and removal shall be supported.setting's behavior.
   :id: REQ_SETTINGS_CHANGES
   :status: implemented, needs more tests

The setting package shall accomodate the introduction of new settings, renaming of old settings, and support the complex deprecation behaviors of settings.

TODO: This may be tested by a unit test containing removed settings references in both input and code references, as well as an additional definition load and use

.. req:: The settings package shall contain a default state of all settings.
   :id: REQ_SETTINGS_DEFAULTS
   :status: implemented, needs more tests

Many of the settings will not be altered by the user of a run, and there will likely be too many for a user to deal with on an individual basis. Therefore, most settings will need to function sensibly with their default value. This default value shall always be accessible throughout the runs life cycle.

TODO: This may be tested by unit tests loading and checking values on each setting.

.. req:: The settings package shall support version tracking.
   :id: REQ_SETTINGS_VERSION
   :status: implemented, needs more tests

The input files generated by the settings system will most often exist outside of the developer's reach to alter to keep in consistency with expected results. Each of these files is only genuinely valid with the compatible version of ARMI that generated the file, as any change within ARMI can alter how settings are interpreted in hard to track ways. Therefore consistent behavior across ARMI versions and the generated inputs cannot be relied upon. Given this the settings system must alert the user to the potential difference and put the onus on the user to be responsible with their given analysis.

TODO: This may be tested by unit tests with out of date or omitted version information

.. req:: The settings system shall raise an error if the same setting is defined twice.
   :id: REQ_SETTINGS_DUPLICATES
   :status: implemented, needs more tests

When a user defines a setting twice, it shall be detected as an error which is raised to the user.

TODO: This may be tested by unit tests loading and checking settings that have a setting defined twice, and failing.

.. req:: ARMI shall be able to represent a user-specified reactor.
   :id: REQ_REACTOR
   :status: implemented, needs more tests

   Given user input describing a reactor system, ARMI shall construct with equivalent
   fidelity a software model of the reactor. In particular, ARMI shall appropriately
   represent the shape, arrangement, connectivity, dimensions, materials (including
   thermo-mechanical properties), isotopic composition, and temperatures of the
   reactor.

   .. req:: ARMI shall represent the reactor hierarchically.
      :id: REQ_REACTOR_HIERARCHY
      :status: completed

      To maintain consistency with the physical reactor being modeled, ARMI shall
      maintain a hierarchical definition of its components. For example, all the
      fuel pins in a single fuel assembly in a solid-fuel reactor shall be
      collected such that they can be queried or modified as a unit as well as
      individuals.

   .. req:: ARMI shall automatically handle thermal expansion.
      :id: REQ_REACTOR_THERMAL_EXPANSION
      :status: completed

      ARMI shall automatically compute and applied thermal expansion and contraction
      of materials.

   .. req:: ARMI shall support a reasonable set of basic shapes.
      :id: REQ_REACTOR_SHAPES
      :status: implemented, needs more tests

      ARMI shall support the following basic shapes: Hexagonal prism (ducts in fast
      reactors), rectangular prism (ducts in thermal reactors), cylindrical prism
      (fuel pins, cladding, etc.), and helix (wire wrap).

   .. req:: ARMI shall support a number of structured mesh options.
      :id: REQ_REACTOR_MESH
      :status: completed

      ARMI shall support regular, repeating meshes in hexagonal, radial-zeta-theta (RZT),
      and Cartesian structures.

   .. req:: ARMI shall support the specification of symmetry options and boundary conditions.
      :id: REQ_REACTOR_4
      :status: implemented, need impl/test

      ARMI shall support symmetric models including 1/4, 1/8 core models for Cartesian meshes
      and 1/3 and full core for Hex meshes. For Cartesian 1/8 core symmetry, the core axial
      symmetry plane (midplane) will be located at the top of the reactor.

   .. req:: ARMI shall check for basic correctness.
      :id: REQ_REACTOR_5
      :status: implemented, need impl/test

      ARMI shall check its input for certain obvious errors including unphysical densities
      and proper fit.

   .. req:: ARMI shall allow for the definition of limited one-dimensional translation paths.
      :id: REQ_REACTOR_6
      :status: implemented, need impl/test

      ARMI shall allow the user specification of translation pathways for certain objects to
      follow, to support moving control mechanisms.

   .. req:: ARMI shall allow the definition of fuel management operations (i.e. shuffling)
      :id: REQ_REACTOR_7
      :status: implemented, need impl/test

      ARMI shall allow for the modeling of a reactor over multiple cycles.

.. req:: ARMI shall represent and reflect the evolving state of a reactor.
   :id: REQ_1
   :status: implemented, needs test

   The state shale be made available to users and modules, which may in turn modify the
   state (e.g. for analysis or based on the results of a physical calculation). ARMI
   shall fully define how all aspects of state may be accessed and modified and shall
   reflect any new state after it is applied.

   State shall be represented as evolving either through time (i.e. in a typical cycle-
   by-cycle analysis) or through a series of control configurations.

.. req:: The operator package shall provide a means by which to communicate inputs and results between analysis modules.
   :id: REQ_operator_io
   :status: implemented, needs test

The operator package shall receive output from calculation modules and store the results on a well-defined central model. A composite pattern shall be used, with a Reactor containing Assemblies containing Blocks, etc.

.. req:: The operator package shall provide a means to perform computations in parallel on a high performance computer.
   :id: REQ_operator_parallel
   :status: implemented, needs test

Many analysis tasks require high performance computing (HPC), and the operator package shall contain utilities and routines to communicate with an HPC and to facilitate execution of simulations in parallel.

.. req:: The operator package shall allow physics coupling between analysis modules.
   :id: REQ_operator_coupling
   :status: implemented, needs test

For coupled physics (e.g. neutronics depends on thermal hydraulics depends on neutronics), the operator package shall allow loose and/or tight coupling. Loose coupling is using the values from the previous timestep to update the next timestep. Tight is an operator-splitting iteration until convergence between one or more modules.

.. req:: The operator package shall allow analysis modules to be replaced without affecting interfaces in other modules.
   :id: REQ_operator_analysis
   :status: implemented, needs test

Often, a module is replaced with a new module fulfilling some new requirement. When this happens, the operator package shall isolate required changes to the new module. For example, if a fuel performance module needs temperatures but the temperature-computing module is replaced, the fuel performance module should require no changes to work with the drop-in replacement. This requires modular design and standardization in state names.

.. req:: The operator package shall coordinate calls to the various modules.
   :id: REQ_operator_coord
   :status: implemented, needs test

Based on user settings, the ordering, initialization, and calls to other modules shall be coordinated by the operator package. The operator package must therefore be aware of dependencies of each module.

.. req:: The latticePhysics package will execute the lattice physics code in a parallel, serial, or distributed fashion depending on the mode.
   :id: REQ_lattice_execute
   :status: implemented, needs test


.. reg:: The reactor package shall represent the user-specified reactor.
   :id: REQ_reator_user
   :status: implemented, needs test

Given user input describing a reactor system, the reactor package shall construct with equivalent fidelity
a software model of the reactor. In particular, the reactor package
shall appropriately represent the shape, arrangement, connectivity, dimensions,
materials (including thermo-mechanical properties), isotopic composition, and temperatures of the reactor.

TODO: This may be tested by:

#. Evidence that input quantities are accessible from the reactor model
#. Validation that an input benchmark performs within measured quantities


------------------------
Performance Requirements
------------------------

.. req:: The database representation on disk shall be smaller than the the in-memory Python representation
   :id: REQ_DB_PERFORMANCE
   :status: implemented, needs test

The database implementation shall use lossless compression to reduce the database size.

.. req:: The report package shall present no burden.
   :id: REQ_REPORT_PERFORMANCE
   :status: implemented, needs test

As the report package is a lightweight interface to write data out to a text based format, and render a few images, the performance costs are entirely negligible and should not burden the run, nor the user's computer in both memory and processor time.

..
   TODO: Let's do a top-level redesign of the performance requirements.


-------------------
Software Attributes
-------------------

.. req:: The database produced shall be easily accessible in a variety of operating systems.
    :id: REQ_DB_OS
    :status: implemented, needs test

.. req:: The database produced shall be easily accessible in a variety of programming environments beyond Python.
    :id: REQ_DB_LANGUAGE
    :status: implemented, needs test

.. req:: The report package shall be easily accessible in a variety of operating systems.
    :id: REQ_REPORT_OS
    :status: implemented, needs test


.. req:: The settings package shall use human-readable, plain-text files as input.
   :id: REQ_SETTINGS_READABLE
   :status: implemented, needs more tests

The user must be able to read and edit their settings file as plain text in broadly any typical text editor.


---------------------------
Software Design Constraints
---------------------------

.. req:: The database package shall provide compatability with all previously generated databases.
    :id: REQ_DB_BACKWARDS_COMPAT
    :status: implemented, needs test

With very few redesign exceptions, as qualified cases are produced for analysis and rerunning, it is imperative the data always be in an accesible form.

.. req:: The report package shall not burden new developers with grasping a complex system.
    :id: REQ_REPORT_TECH
    :status: implemented, needs test

Given the functional requirements of the report package, new developers should be able to understand how to contribute to a report nigh instantly. No new technologies should be introduced to the system as HTML and ASCII are both purely text-based.

--------------------------
Interface I/O Requirements
--------------------------

..
   TODO: blueprints need some interface and I/O reqs

.. req:: The setting system shall render a view of every defined setting as well as the key attributes associated with it
   :id: REQ_SETTINGS_REPORT
   :status: implemented, needs more tests

Utilizing the documentation of the ARMI project the settings system shall contribute a page containing a table summary of the settings included in the system.

TODO: This is completed by the :doc:`Settings Report </user/inputs/settings_report>`.

.. req:: The latticePhysics package will write input files for the desired code for each representative block to be modeled.
   :id: REQ_lattice_inputs
   :status: implemented, needs test

.. req:: The latticePhysics package will use the output(s) to create a reactor library, ``ISOTXS`` or ``COMPXS``, used in the global flux solution.
   :id: REQ_lattice_outputs
   :status: implemented, needs test


--------------------
Testing Requirements
--------------------

..
   TODO: Do this by topic


--------------------------
Open-Items and Assumptions
--------------------------

..
   TODO: Do this by topic


----------
Appendices
----------

..
   TODO
