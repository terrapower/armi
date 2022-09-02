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

..
   TODO: Do this by topic


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

