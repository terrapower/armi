.. _armi_physics:

Physics Package
---------------

This section provides requirements for the :py:mod:`armi.physics` package within the framework, which contains interfaces for important physics modeling and analysis in nuclear reactors. It is important to note that ARMI is a framework, and as such does not generally include the actual science or engineering calculations for these topics. For instance, ARMI has an interface for "safety analysis", but this interface is just a *place* for developers to implement their own safety analysis code. It would be inappropriate to include the actual science or engineering calculations for a detailed safety analysis of a particular reactor in ARMI because ARMI is meant only to house the code to let nuclear modeling and analysis work, not the analysis itself.



Functional Requirements
+++++++++++++++++++++++

.. ## globalFlux ######################

.. req:: ARMI shall ensure that the computed block-wise power is consistent with the power specified in the reactor data model.
    :id: R_ARMI_FLUX_CHECK_POWER
    :subtype: functional
    :status: accepted
    :basis: This requirement ensures that neutronics solver scales the neutron flux appropriately such that the computed block-wise power captures the specified global power.
    :acceptance_criteria: Test that throws an error when the summed block-wise powers does not match the specified total power.

.. req:: ARMI shall provide an interface for querying options relevant to neutronics solvers.
    :id: R_ARMI_FLUX_OPTIONS
    :subtype: functional
    :status: accepted
    :basis: Reactor analysts will want to use popular neutronics solvers, e.g. DIF3D-Variant.
    :acceptance_criteria: The interface correctly returns specified neutronics solver options.

.. req:: ARMI shall allow modification of the reactor geometry when needed for neutronics solver execution.
    :id: R_ARMI_FLUX_GEOM_TRANSFORM
    :subtype: functional
    :status: accepted
    :basis: Axial expansion can cause a disjointed mesh which cannot be resolved by deterministic neutronics solvers.
    :acceptance_criteria: Geometry transformations are performed before executing a neutronics solve.

.. req:: ARMI shall calculate neutron reaction rates for a given block.
    :id: R_ARMI_FLUX_RX_RATES
    :subtype: functional
    :status: accepted
    :basis: This is a generic ARMI feature implemented to aid in calculating dose, converting results calculated on one mesh to another, and for comparing reaction rates against experiments.
    :acceptance_criteria: Calculate accurate reaction rates for a given multigroup flux and cross section library for a wide collection of Blocks.

.. req:: ARMI shall be able to calculate DPA and DPA rates from a multigroup neutron flux and DPA cross sections.
    :id: R_ARMI_FLUX_DPA
    :subtype: functional
    :status: accepted
    :basis: DPA rates are necessary for fuel performance calculations.
    :acceptance_criteria: The DPA rate is calculated for a composite with an associated multi-group neutron flux.

.. ## isotopicDepletion ######################

.. req:: The isotopicDepletion package shall have the ability to generate cross-section tables from a CCCC-based library in a user-specified format.
    :id: R_ARMI_DEPL_TABLES
    :subtype: functional
    :status: accepted
    :basis: Depletion solvers require cross-sections to be supplied from external sources if not using built-in cross sections.
    :acceptance_criteria: Produce a table with the specified formatting containing the appropriate cross sections.

.. req:: The isotopicDepletion package shall provide a base class to track depletable composites.
    :id: R_ARMI_DEPL_ABC
    :subtype: functional
    :status: accepted
    :basis: Depletion analysis may want a way to track depletable composites.
    :acceptance_criteria: Store and retrieve depletable objects.

.. ## energyGroups ######################

.. req:: The neutronics package shall provide the neutron energy group bounds for a given group structure.
    :id: R_ARMI_EG_NE
    :subtype: functional
    :basis: The bounds define the energy groupings.
    :acceptance_criteria: Return the correct energy bounds.
    :status: accepted

.. req:: The neutronics package shall return the energy group index which contains the fast energy threshold.
    :id: R_ARMI_EG_FE
    :subtype: functional
    :basis: The energy groups are only useful if a developer can find the correct one easily.
    :acceptance_criteria: Identify the correct energy group for a given energy threshold.
    :status: accepted

.. ## macroXSGenerationInterface ######################

.. req:: The neutronics package shall be able to build macroscopic cross sections for all blocks.
    :id: R_ARMI_MACRO_XS
    :subtype: functional
    :basis: Most steady-state neutronics workflows will rely on this capability.
    :acceptance_criteria: Calculate the macroscopic cross sections for a block.
    :status: accepted

.. ## executers ######################

.. req:: The executers module shall provide the ability to run external calculations on an ARMI reactor with configurable options.
    :id: R_ARMI_EX
    :subtype: functional
    :basis: An ARMI plugin needs to be able to to wrap an external executable.
    :acceptance_criteria: Execute a mock external calculation based on an ARMI reactor.
    :status: accepted


.. ## fuelCycle ######################

.. req:: The fuel cycle package shall allow for user-defined assembly shuffling logic to update the reactor model based on reactor state.
    :id: R_ARMI_SHUFFLE
    :subtype: functional
    :basis: Shuffle operations can be based on assemblies' burnup state, which may not be known at the start of a run.
    :acceptance_criteria: Execute user-defined shuffle operations based on a reactor model.
    :status: accepted

.. req:: The fuel cycle package shall be capable of leaving user-specified blocks in place during shuffling operations.
    :id: R_ARMI_SHUFFLE_STATIONARY
    :subtype: functional
    :basis: It may be desirable to leave certain blocks, such as grid plates, in place.
    :acceptance_criteria: Shuffle an assembly while leaving a specified block in place.
    :status: accepted

.. req:: A hexagonal assembly shall support rotating around the z-axis in 60 degree increments.
    :id: R_ARMI_ROTATE_HEX
    :subtype: functional
    :basis: Rotation of assemblies is common during operation, and requires updating the location of physics data assigned on the assembly.
    :acceptance_criteria: After rotating a hexagonal assembly, spatial data corresponds to rotating the original assembly data.
    :status: accepted

.. req:: The framework shall provide an algorithm for rotating hexagonal assemblies to equalize burnup.
    :id: R_ARMI_ROTATE_HEX_BURNUP
    :subtype: functional
    :basis: Rotating of assemblies to minimize burnup helps maximize fuel utilization and reduces power peaking.
    :acceptance_criteria: After rotating a hexagonal assembly, confirm the pin with the highest burnup is in the same sector as pin with the lowest power in the high burnup pin's ring.
    :status: accepted

.. ## crossSectionGroupManager ######################

.. req:: The cross-section group manager package shall run before cross sections are calculated.
    :id: R_ARMI_XSGM_FREQ
    :subtype: functional
    :basis: The cross section groups need to be up to date with the core state at the time that the Lattice Physics Interface is called.
    :acceptance_criteria: Initiate the cross-section group manager by the same setting that initiates calculating cross sections. And ensure the cross-section group manager always runs before cross sections are calculated.
    :status: accepted

.. req:: The cross-section group manager package shall create separate collections of blocks for each combination of user-specified XS type and burnup/temperature environment group.
    :id: R_ARMI_XSGM_CREATE_XS_GROUPS
    :subtype: functional
    :basis: This helps improve the performance of downstream cross section calculations.
    :acceptance_criteria: Create cross section groups and their representative blocks.
    :status: accepted

.. req:: The cross-section group manager package shall provide routines to create representative blocks for each collection based on user-specified XS type and burnup/temperature environment group.
    :id: R_ARMI_XSGM_CREATE_REPR_BLOCKS
    :subtype: functional
    :basis: The Lattice Physics Interface needs a representative block from which to generate a lattice physics input file.
    :acceptance_criteria: Create representative blocks using volume-weighted averaging and custom cylindrical averaging.
    :status: accepted
