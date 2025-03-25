.. _armi_reactors:

Reactors Package
----------------

This section provides requirements for the :py:mod:`armi.reactors` package within the framework, unsurprisingly this is the largest package in ARMI. In this package are sub-packages for fully defining a nuclear reactor, starting from blueprints and all the way through defining the full reactor data model. It is this reactor data object that is critical to the framework; this is how different reactor modeling tools share information.



Functional Requirements
+++++++++++++++++++++++

.. ## reactors ######################

.. req:: The reactor data model shall contain one core and a collection of ex-core objects, all composites.
    :id: R_ARMI_R
    :status: accepted
    :basis: A shared reactor data model is a fundamental concept in ARMI.
    :acceptance_criteria: Build a reactor data model from a blueprint file, and show it has a core and a spent fuel pool.
    :subtype: functional

.. req:: Assemblies shall be retrievable from the core object by name and location.
    :id: R_ARMI_R_GET_ASSEM
    :status: accepted
    :basis: Useful for analysis, particularly mechanical and control rod analysis.
    :acceptance_criteria: Retrieve assemblies from the core by name and location.
    :subtype: functional

.. req:: The core shall be able to construct a mesh based on its blocks.
    :id: R_ARMI_R_MESH
    :status: accepted
    :basis: Preservation of material and geometry boundaries is needed for accurate physics calculations.
    :acceptance_criteria: Construct a mesh from a core object.
    :subtype: functional

.. req:: ARMI shall support third-core symmetry for hexagonal cores.
    :id: R_ARMI_R_SYMM
    :status: accepted
    :basis: Symmetric model definitions allow for easier user setup and reduced computational expense.
    :acceptance_criteria: Construct a core of full or 1/3-core symmetry.
    :subtype: functional

.. req:: The core shall be able to provide assemblies that are neighbors of a given assembly.
    :id: R_ARMI_R_FIND_NEIGHBORS
    :status: accepted
    :basis: Useful for analysis, particularly mechanical and control rod analysis.
    :acceptance_criteria: Return neighboring assemblies from a given assembly in a core.
    :subtype: functional


.. ## parameters ######################

.. req:: The parameters package shall provide the capability to define parameters that store values of interest on any Composite.
    :id: R_ARMI_PARAM
    :status: accepted
    :basis: The capability to define new parameters is a common need for downstream analysis or plugins.
    :acceptance_criteria: Ensure that new parameters can be defined and accessed on a Reactor, Core, Assembly, Block, and Component.
    :subtype: functional

.. req:: The parameters package shall allow for some parameters to be defined such that they are not written to the database.
    :id: R_ARMI_PARAM_DB
    :status: accepted
    :basis: Users will require some parameters to remain unwritten to the database file.
    :acceptance_criteria: A parameter can be filtered from inclusion into the list of parameters written to the database.
    :subtype: functional

.. req:: The parameters package shall provide a way to signal if a parameter needs updating across multiple processes.
    :id: R_ARMI_PARAM_PARALLEL
    :status: accepted
    :basis: Parameters updated on compute nodes must be propagated to the head node.
    :acceptance_criteria: A parameter has an attribute which signals its last updated status among the processors.
    :subtype: functional

.. req:: The parameters package shall allow for a parameter to be serialized for reading and writing to database files.
    :id: R_ARMI_PARAM_SERIALIZE
    :status: accepted
    :basis: Users need to be able to understand what parameters were involved during a given run after it is completed, both for QA purposes and to begin a new analysis using data from previous analyses.
    :acceptance_criteria: The Serializer construct can pack and unpack parameter data.
    :subtype: functional

.. ## zones ######################

.. req:: The zones module shall allow for a collection of reactor core locations (a Zone).
    :id: R_ARMI_ZONE
    :status: accepted
    :basis: This is a basic feature of ARMI and is useful for reactivity coefficients analysis.
    :acceptance_criteria: Store and retrieve locations from a zone that corresponds to a reactor. Also, store and retrieve multiple Zone objects from a Zones object.
    :subtype: functional

.. ## blocks ######################

.. req:: The blocks module shall be able to homogenize the components of a hexagonal block.
    :id: R_ARMI_BLOCK_HOMOG
    :status: accepted
    :basis: Homogenizing blocks can improve performance of the uniform mesh converter.
    :acceptance_criteria: A homogenized hexagonal block has the same mass, dimensions, and pin locations as the block from which it is derived.
    :subtype: functional

.. req:: Blocks shall include information on their location.
    :id: R_ARMI_BLOCK_POSI
    :status: accepted
    :basis: Simulations and post-simulation analysis both require block-level physical quantities.
    :acceptance_criteria: Any block can be queried to get absolute location and position.
    :subtype: functional

.. req:: The blocks module shall define a hex-shaped block.
    :id: R_ARMI_BLOCK_HEX
    :status: accepted
    :basis: Hexagonal blocks are used in some pin-based reactors.
    :acceptance_criteria: Verify a block can be created that declares a hexagonal shape.
    :subtype: functional

.. req:: The blocks module shall return the number of pins in a block, when applicable.
    :id: R_ARMI_BLOCK_NPINS
    :status: accepted
    :basis: This is a common need for analysis of pin-based reactors.
    :acceptance_criteria: Return the number of pins in a valid block.
    :subtype: functional

.. ## assemblies ######################

.. req:: The assemblies module shall define an assembly as a composite type that contains a collection of blocks.
    :id: R_ARMI_ASSEM_BLOCKS
    :status: accepted
    :basis: ARMI must be able to represent assembly-based reactors.
    :acceptance_criteria: Validate an assembly's type and the types of its children.
    :subtype: functional

.. req:: Assemblies shall include information on their location.
    :id: R_ARMI_ASSEM_POSI
    :status: accepted
    :basis: Assemblies are an important part of pin-type reactor cores, and almost any analysis that uses assemblies will want to know the location of the assemblies.
    :acceptance_criteria: Any assembly can be queried to get absolute location and position.
    :subtype: functional

.. ## flags ######################

.. req:: The flags module shall provide unique identifiers (flags) to enable disambiguating composites.
    :id: R_ARMI_FLAG_DEFINE
    :subtype: functional
    :basis: Flags are used to determine how objects should be handled.
    :acceptance_criteria: No two existing flags have equivalence.
    :status: accepted

.. req:: The set of unique flags in a run shall be extensible without user knowledge of existing flags' values.
    :id: R_ARMI_FLAG_EXTEND
    :subtype: functional
    :basis: Plugins are able to define their own flags.
    :acceptance_criteria: After adding a new flag, no two flags have equivalence.
    :status: accepted

.. req:: Valid flags shall be convertible to and from strings.
    :id: R_ARMI_FLAG_TO_STR
    :subtype: functional
    :basis: Flags need to be converted to strings for serialization.
    :acceptance_criteria: A string corresponding to a defined flag is correctly converted to that flag, and show that the flag can be converted back to a string.
    :status: accepted

.. ## geometryConverters ######################

.. req:: ARMI shall be able to convert a hexagonal one-third-core geometry to a full-core geometry, and back again.
    :id: R_ARMI_THIRD_TO_FULL_CORE
    :subtype: functional
    :basis: Useful to improve modeling performance, if the analysis can accept the approximation.
    :acceptance_criteria: Convert a hexagonal 1/3 core reactor to full, and back again.
    :status: accepted

.. req:: ARMI shall be able to add and remove assemblies along the 120 degree line in a 1/3 core reactor.
    :id: R_ARMI_ADD_EDGE_ASSEMS
    :subtype: functional
    :basis: Helpful for analysis that are using 1/3 core hex reactors
    :acceptance_criteria: Add and then remove assemblies in a 1/3 core reactor.
    :status: accepted

.. req:: ARMI shall be able to convert a hex core to a representative RZ core.
    :id: R_ARMI_CONV_3DHEX_TO_2DRZ
    :subtype: functional
    :basis: Some downstream analysis requires a 2D R-Z geometry.
    :acceptance_criteria: Convert a hex core into an RZ core.
    :status: accepted

.. ## axialExpansionChanger ######################

.. req:: The axial expansion changer shall perform axial thermal expansion and contraction on solid components within a compatible ARMI assembly according to a given axial temperature distribution.
    :id: R_ARMI_AXIAL_EXP_THERM
    :subtype: functional
    :basis: Axial expansion is used to conserve mass and appropriately capture the reactor state under temperature changes.
    :acceptance_criteria: Perform thermal expansion due to an applied axial temperature distribution.
    :status: accepted

.. req:: The axial expansion changer shall perform axial expansion/contraction given a list of components and corresponding expansion coefficients.
    :id: R_ARMI_AXIAL_EXP_PRESC
    :subtype: functional
    :basis: Axial expansion is used to conserve mass and appropriately capture the reactor state under temperature changes.
    :acceptance_criteria: Perform axial expansion given a list of components from an assembly and corresponding expansion coefficients.
    :status: accepted

.. req:: The axial expansion changer shall perform expansion during core construction based on block heights at a user-specified temperature.
    :id: R_ARMI_INP_COLD_HEIGHT
    :subtype: functional
    :basis: The typical workflow in ARMI applications is to transcribe component dimensions, which are generally given at room temperatures.
    :acceptance_criteria: Perform axial expansion during core construction based on block heights at user-specified temperature.
    :status: accepted

.. req:: The axial expansion changer shall allow user-specified target axial expansion components on a given block.
    :id: R_ARMI_MANUAL_TARG_COMP
    :subtype: functional
    :basis: The target axial expansion component influences the conservation of mass in a block.
    :acceptance_criteria: Set a target component and verify it was set correctly.
    :status: accepted

.. req:: The axial expansion changer shall preserve the total height of a compatible ARMI assembly.
    :id: R_ARMI_ASSEM_HEIGHT_PRES
    :subtype: functional
    :basis: Many physics solvers require that the total height of each assembly in the core is consistent.
    :acceptance_criteria: Perform axial expansion and confirm that the height of the compatible ARMI assembly is preserved.
    :status: accepted

.. ## uniformMesh ######################

.. req:: The uniform mesh converter shall make a copy of the reactor where the new reactor core has a uniform axial mesh.
    :id: R_ARMI_UMC
    :subtype: functional
    :basis: This is used in the global flux calculations.
    :acceptance_criteria: Convert a reactor to one where the core has a uniform axial mesh.
    :status: accepted

.. req:: The uniform mesh converter shall map select parameters from composites on the original mesh to composites on the new mesh.
    :id: R_ARMI_UMC_PARAM_FORWARD
    :subtype: functional
    :basis: This is used in the global flux calculations.
    :acceptance_criteria: Create a new reactor with the uniform mesh converter and ensure that the flux and power density block-level parameters are mapped appropriately to the new reactor.
    :status: accepted

.. req:: The uniform mesh converter shall map select parameters from composites on the new mesh to composites on the original mesh.
    :id: R_ARMI_UMC_PARAM_BACKWARD
    :subtype: functional
    :basis: This is used in the global flux calculations.
    :acceptance_criteria: Create a new reactor with the uniform mesh converter and ensure that the flux and power density block-level parameters are mapped appropriately back to the original reactor.
    :status: accepted

.. req:: The uniform mesh converter shall try to preserve the boundaries of fuel and control material.
    :id: R_ARMI_UMC_NON_UNIFORM
    :subtype: functional
    :basis: Regions with extremely small axial size can cause difficulties for the deterministic neutronics solvers.
    :acceptance_criteria: Create a reactor with slightly non-uniform mesh and verify after the uniform mesh converter the mesh is still non-uniform.
    :status: accepted

.. req:: The uniform mesh converter shall produce a uniform axial mesh with a size no smaller than a user-specified value.
    :id: R_ARMI_UMC_MIN_MESH
    :subtype: functional
    :basis: Regions with extremely small axial size can cause difficulties for the deterministic neutronics solvers.
    :acceptance_criteria: Create a reactor with a mesh that is smaller than the minimum size. After the uniform mesh conversion the new mesh conforms to the user-specified value.
    :status: accepted

.. ## blockConverters ######################

.. req:: The block converter module shall be able to convert one or more given hexagonal blocks into a single user-configurable representative cylindrical block.
    :id: R_ARMI_BLOCKCONV_HEX_TO_CYL
    :subtype: functional
    :basis: Needed, for example, for generating 1D cross sections for control rods.
    :acceptance_criteria: Create a cylindrical block from one or more given hexagonal blocks and confirm that the cylindrical block has the appropriate volume fractions and temperatures.
    :status: accepted

.. req:: The block converter module shall be able to homogenize one component into another on a block.
    :id: R_ARMI_BLOCKCONV
    :subtype: functional
    :basis: Needed, for example, for merging wire into coolant or gap into clad to simplify the model.
    :acceptance_criteria: Homogenize one component into another from a given block and confirm the new components are appropriate.
    :status: accepted

.. ## components ######################

.. req:: The components package shall define a composite corresponding to a physical piece of a reactor.
    :id: R_ARMI_COMP_DEF
    :subtype: functional
    :basis: This is a fundamental design choice in ARMI, to describe a physical reactor.
    :acceptance_criteria: Create components, and verify their attributes and parameters.
    :status: accepted

.. req:: A component's dimensions shall be calculable for any temperature.
    :id: R_ARMI_COMP_DIMS
    :subtype: functional
    :basis: Users require access to dimensions at perturbed temperatures.
    :acceptance_criteria: Calculate a components dimensions at a variety of temperatures.
    :status: accepted

.. req:: Components shall be able to compute dimensions, areas, and volumes that reflect its current state.
    :id: R_ARMI_COMP_VOL
    :subtype: functional
    :basis: It is necessary to be able to compute areas and volumes when state changes.
    :acceptance_criteria: Calculate volumes/areas, clear the cache, change the temperature, and recalculate volumes/areas.
    :status: accepted

.. req:: Components shall allow for constituent nuclide fractions to be modified.
    :id: R_ARMI_COMP_NUCLIDE_FRACS
    :subtype: functional
    :basis: The ability to modify nuclide fractions is a common need in reactor analysis.
    :acceptance_criteria: Modify nuclide fractions on a component.
    :status: accepted

.. req:: Components shall be made of one-and-only-one material or homogenized material.
    :id: R_ARMI_COMP_1MAT
    :subtype: functional
    :basis: This is an ARMI design choice.
    :acceptance_criteria: Create a component with a given material, and retrieve that material.
    :status: accepted

.. req:: Components shall be associated with material properties.
    :id: R_ARMI_COMP_MAT
    :subtype: functional
    :basis: Users require access to material properties for a given component.
    :acceptance_criteria: Get material properties from a component material.
    :status: accepted

.. req:: Components shall enable an ordering based on their outermost component dimensions.
    :id: R_ARMI_COMP_ORDER
    :subtype: functional
    :basis: It is desirable to know which components are located physically inside of others.
    :acceptance_criteria: Order a collection of components, based on their dimensions.
    :status: accepted

.. req:: The components package shall define components with several basic interrogable shapes.
    :id: R_ARMI_COMP_SHAPES
    :subtype: functional
    :basis: Modeling real-world reactor geometries requires a variety of shapes.
    :acceptance_criteria: Create a variety of components with different shapes and query their shape information.
    :status: accepted

.. req:: The components package shall handle radial thermal expansion of individual components.
    :id: R_ARMI_COMP_EXPANSION
    :subtype: functional
    :basis: Users need the ability to model thermal expansion of a reactor core.
    :acceptance_criteria: Calculate radial thermal expansion for a variety components.
    :status: accepted

.. req:: The components package shall allow the dimensions of fluid components to change based on the solid components adjacent to them.
    :id: R_ARMI_COMP_FLUID
    :subtype: functional
    :basis: The shapes of fluid components are defined externally.
    :acceptance_criteria: Determine the dimensions of a fluid component, bounded by solids.
    :status: accepted

.. ## composites ######################

.. req:: The composites module shall define an arbitrary physical piece of a reactor with retrievable children in a hierarchical data model.
    :id: R_ARMI_CMP
    :subtype: functional
    :basis: This is a fundamental aspect of the ARMI framework.
    :acceptance_criteria: Create a composite with children.
    :status: accepted

.. req:: Composites shall be able to be associated with flags.
    :id: R_ARMI_CMP_FLAG
    :subtype: functional
    :basis: Flags are used to provide context as to what a composite object represents.
    :acceptance_criteria: Give a composite one or more flags.
    :status: accepted

.. req:: Composites shall have their own parameter collections.
    :id: R_ARMI_CMP_PARAMS
    :subtype: functional
    :basis: Parameters should live on the part of the model which they describe.
    :acceptance_criteria: Query a composite's parameter collection.
    :status: accepted

.. req:: The total mass of specified nuclides in a composite shall be retrievable.
    :id: R_ARMI_CMP_GET_MASS
    :subtype: functional
    :basis: Downstream analysis will want to get masses.
    :acceptance_criteria: Return the mass of specified nuclides in a composite.
    :status: accepted

.. req:: Composites shall allow synchronization of state across compute nodes.
    :id: R_ARMI_CMP_MPI
    :subtype: functional
    :basis: Parallel executions of ARMI require synchronization of reactors on different nodes.
    :acceptance_criteria: Synchronize a reactor's state across compute processes.
    :status: accepted

.. req:: The homogenized number densities of specified nuclides in a composite shall be retrievable.
    :id: R_ARMI_CMP_GET_NDENS
    :subtype: functional
    :basis: The ability to retrieve homogenized number densities is a common need in reactor analysis.
    :acceptance_criteria: Retrieve homogenized number densities of specified nuclides from a composite.
    :status: accepted

.. req:: Composites shall be able to return number densities for all their nuclides.
    :id: R_ARMI_CMP_NUC
    :subtype: functional
    :basis: Analysts not using lumped fission products need this capability.
    :acceptance_criteria: Return the number densities for all nuclides for a variety of composites.
    :status: accepted

.. ## grids ######################

.. req:: The grids package shall allow for pieces of the reactor to be organized into regular-pitch hexagonal lattices (grids).
    :id: R_ARMI_GRID_HEX
    :subtype: functional
    :basis: This is necessary for representing reactor geometry.
    :acceptance_criteria: Construct a hex grid from pitch and number of rings, and return both.
    :status: accepted

.. req:: The grids package shall be able to represent 1/3-symmetry or full hexagonal grids.
    :id: R_ARMI_GRID_SYMMETRY
    :subtype: functional
    :basis: Analysts frequently want symmetrical representations of a reactor for efficiency reasons.
    :acceptance_criteria: Construct a 1/3 symmetry and full grid and show they have the correct number of constituents.
    :status: accepted

.. req:: A hexagonal grid with 1/3 symmetry shall be able to determine if a constituent object is in the first third.
    :id: R_ARMI_GRID_SYMMETRY_LOC
    :subtype: functional
    :basis: Helpful for analysts doing analysis on third-core hex grids.
    :acceptance_criteria: Correctly identify an object that is in the first 1/3 and one that is not.
    :status: accepted

.. req:: A hexagonal grid with 1/3 symmetry shall be capable of retrieving equivalent contents based on 1/3 symmetry.
    :id: R_ARMI_GRID_EQUIVALENTS
    :subtype: functional
    :basis: This is necessary for shuffle of 1/3-core symmetry reactor models.
    :acceptance_criteria: Return the zero or 2 elements which are in symmetric positions to a given element.
    :status: accepted

.. req:: Grids shall be able to nest.
    :id: R_ARMI_GRID_NEST
    :subtype: functional
    :basis: This is typical of reactor geometries, for instance pin grids are nested inside of assembly grids.
    :acceptance_criteria: Nest one grid within another.
    :status: accepted

.. req:: Hexagonal grids shall be either x-type or y-type.
    :id: R_ARMI_GRID_HEX_TYPE
    :subtype: functional
    :basis: This is typical of reactor geometries, for instance pin grids inside of assembly grids.
    :acceptance_criteria: Construct a "points-up" and a "flats-up" grid.
    :status: accepted

.. req:: The grids package shall be able to store components with multiplicity greater than 1.
    :id: R_ARMI_GRID_MULT
    :subtype: functional
    :basis: The blueprints system allows for components with multiplicity greater than 1, when there are components that are compositionally identical.
    :acceptance_criteria: Build a grid with components with multiplicity greater than 1.
    :status: accepted

.. req:: The grids package shall be able to return the coordinate location of any grid element in a global coordinate system.
    :id: R_ARMI_GRID_GLOBAL_POS
    :subtype: functional
    :basis: This is a common need of a reactor analysis system.
    :acceptance_criteria: Return a hexagonal grid element's location.
    :status: accepted

.. req:: The grids package shall be able to return the location of all instances of grid components with multiplicity greater than 1.
    :id: R_ARMI_GRID_ELEM_LOC
    :subtype: functional
    :basis: This is a necessary result of having component multiplicity.
    :acceptance_criteria: Return a hexagonal grid element's locations when its multiplicity is greater than 1.
    :status: accepted


I/O Requirements
++++++++++++++++

.. req:: The blueprints package shall allow the user to define a component using a custom text file.
    :id: R_ARMI_BP_COMP
    :subtype: io
    :basis: This is a basic ARMI feature, that we have custom text blueprint files.
    :acceptance_criteria: Read a blueprint file and verify a component was correctly created.
    :status: accepted

.. req:: The blueprints package shall allow the user to define a block using a custom text file.
    :id: R_ARMI_BP_BLOCK
    :subtype: io
    :basis: This is a basic ARMI feature, that we have custom text blueprint files.
    :acceptance_criteria: Read a blueprint file and verify a block was correctly created with shape, material, and input temperature.
    :status: accepted

.. req:: The blueprints package shall allow the user to define an assembly using a custom text file.
    :id: R_ARMI_BP_ASSEM
    :subtype: io
    :basis: This is a basic ARMI feature, that we have custom text blueprint files.
    :acceptance_criteria: Read a blueprint file and verify a assembly was correctly created.
    :status: accepted

.. req:: The blueprints package shall allow the user to define a core using a custom text file.
    :id: R_ARMI_BP_CORE
    :subtype: io
    :basis: This is a basic ARMI feature, that we have custom text blueprint files.
    :acceptance_criteria: Read a blueprint file and verify a core was correctly created.
    :status: accepted

.. req:: The blueprints package shall allow the user to define a lattice map in a reactor core using a custom text file.
    :id: R_ARMI_BP_GRID
    :subtype: io
    :basis: This is a basic ARMI feature, that we have custom text blueprint files.
    :acceptance_criteria: Read a blueprint file and verify a lattice grid was correctly created at the assembly and pin levels.
    :status: accepted

.. req:: The blueprints package shall allow the user to define a reactor, including both a core and a spent fuel pool using a custom text file.
    :id: R_ARMI_BP_SYSTEMS
    :subtype: io
    :basis: This is a basic ARMI feature, that we have custom text blueprint files.
    :acceptance_criteria: Read a blueprint file and verify a reactor was correctly created.
    :status: accepted

.. req:: The blueprints package shall allow the user to define isotopes which should be depleted.
    :id: R_ARMI_BP_NUC_FLAGS
    :subtype: io
    :basis: This is a basic ARMI feature, that we have custom text blueprint files.
    :acceptance_criteria: Read a blueprint file and verify the collection of depleted nuclide flags.
    :status: accepted

.. req:: The blueprints package shall allow the user to produce a valid blueprints file from an in-memory blueprint object.
    :id: R_ARMI_BP_TO_DB
    :subtype: io
    :basis: The capability to export custom blueprints input files from an in-memory blueprints object is a fundamental ARMI feature.
    :acceptance_criteria: Write a blueprint file from an in-memory blueprint object.
    :status: accepted
