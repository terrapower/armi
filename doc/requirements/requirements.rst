************
Requirements
************


Software Requirement Specification Document (SRSD)
==================================================

Functional Requirements
-----------------------


.. req:: ARMI shall be able to represent a user-specified reactor.
   :id: REQ_0
   :status: implemented

   Given user input describing a reactor system, ARMI shall construct with equivalent
   fidelity a software model of the reactor. In particular, ARMI shall appropriately
   represent the shape, arrangement, connectivity, dimensions, materials (including
   thermo-mechanical properties), isotopic composition, and temperatures of the
   reactor.

   .. req:: ARMI shall represent the reactor heirarchically.
      :id: REQ_0_0
      :status: implemented

      To maintain consistency with the physical reactor being modeled, ARMI shall
      maintain a heirarchical definition of its components. For example, all the
      fuel pins in a single fuel assembly in a solid-fuel reactor shall be
      collected such that they can be queried or modified as a unit as well as
      individuals.

   .. req:: ARMI shall automatically handle thermal expansion.
      :id: REQ_0_1
      :status: implemented

      ARMI shall automatically compute and applied thermal expansion and contraction
      of materials.

   .. req:: ARMI shall support a reasonable set of basic shapes.
      :id: REQ_0_2
      :status: implemented

      ARMI shall support the following basic shapes: Hexagonal prism (ducts in fast
      reactors), rectangular prism (ducts in thermal reactors), cylindrical prism
      (fuel pins, cladding, etc.), and helix (wire wrap).

   .. req:: ARMI shall support a number of structured mesh options.
      :id: REQ_0_3
      :status: completed

      ARMI shall support regular, repeating meshes in hexagonal, triangular, radial-
      zeta-theta (RZT), and Cartesian structures.

   .. req:: ARMI shall support the specification of symmetry options and boundary conditions.
      :id: REQ_0_4
      :status: completed

      ARMI shall support symmetric models including 1/4, 1/8 core models for Cartesian meshes
      and 1/3 and full core for Hex meshes. For Cartesian 1/8 core symmetry, the core axial
      symmetry plane (midplane) will be located at the top of the reactor.

   .. req:: ARMI shall check for basic correctness.
      :id: REQ_0_5
      :status: completed

      ARMI shall check its input for certain obvious errors including unphysical densities
      and proper fit.

   .. req:: ARMI shall allow for the definition of limited one-dimensional translation paths.
      :id: REQ_0_6
      :status: completed

      ARMI shall allow the user specification of translation pathways for certain objects to
      follow, to support moving control mechanisms.

   .. req:: ARMI shall allow the definition of fuel management operations (i.e. shuffling)
      :id: REQ_0_7
      :status: completed

      ARMI shall allow for the modeling of a reactor over multiple cycles.

.. req:: ARMI shall represent and reflect the evolving state of a reactor.
   :id: REQ_1
   :status: implemented

   The state shale be made available to users and modules, which may in turn modify the
   state (e.g. for analysis or based on the results of a physical calculation). ARMI
   shall fully define how all aspects of state may be accessed and modified and shall
   reflect any new state after it is applied.

   State shall be represented as evolving eitehr through time (i.e. in a typical cycle-
   by-cycle analysis) or through a series of control configurations.
