**************************************************
Software Requirement Specification Document (SRSD)
**************************************************


---------------
Business Impact
---------------

#. The ``database`` package is used to restart runs, analyze results, and determine when changes are introduced to otherwise identical cases in ARMI. The ``database`` package is considered high risk.
#. The ``report`` package is one of many tools available for viewing case details and is intended purely for developer or analyst feedback on run specifications and results, not as a means of altering the run. Thus the ``report`` package is low risk.
#. The ``blueprints`` package interprets user input into an ARMI reactor model. If done incorrectly, ARMI simulations would be unreliable and inaccurate. ARMI is used for informing core designs, engineering calculations, and safety bases; therefore, the ``bluperints`` package is considered high risk.
#. The ``settings`` package contains a substantive amount of the run's definition. Problems in the settings system can invalidate runs. If a user supplies one piece of input, say the setting value that dictates which reactor-defining loading blueprints files to use, and the system performs misleadingly then any subsequent analysis would be invalidated. As this is the principle system of user interaction with ARMI, poor system design choices would aggravate the user experience and decrease user engagement. Fortunately, the errors are easily traced and replicated as the system itself is not complicated. Therefore, the ``settings`` package is considered high risk.
#. The ``operator`` package is paramount to every facility the code offers, affecting every aspect of design. Thus, the ``operator`` packages is high risk.
#. The ``fissionProductModel`` package has substantial impact on the results of the neutronic calculations that affect the plant design. Thus, it falls under the **high risk** impact level.
#. The ``reactor`` package contains the majority of state information throughout a case. Issues in it
could propagate and invalidate results derived from ARMI to perform design and analysis. Therefore, the ``reactor`` package is considered *high risk*.
#. The ``nucDirectory`` package contains nuclide-level information including names, weights, symbols, decay-chain, and transmutation information. This information is used for converting mass fractions to number densities, and identifying specific nuclides to be used in used in performing flux and burn-up calculations. Therefore, the ``nucDirectory`` package is considered high risk.
#. The ``nuclearDataIO`` package is used to read and write nuclear data files which are used as input to global flux solvers, and eventually input into safety calculations via reactivity coefficients. Therefore, the ``nuclearDataIO`` package is considered high risk.


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
   :status: needs implementation, needs test

The database shall faithfully represent the possessed information and not alter its contents, retrieving the data exactly as input.

.. req:: The database shall allow case restarts.
   :id: REQ_DB_RESTARTS
   :status: needs implementation, needs test

The state information representing as near as possible the entirety of the run when the database write was executed, shall be retrievable to restore the previous case to a particular point in time for further use by analysts.

.. req:: The database shall accept all pythonic primitive data types.
   :id: REEQ_DB_PRIMITIVES
   :status: needs implementation, needs test

To facilitate the storage of data, any Pythonic primitive data type shall be valid as an entrant into the database.

.. req:: The database shall not accept abstract data types excluding pythonic ``None``.
   :id: REQ_DB_NONE
   :status: needs implementation, needs test

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
   :status: needs implementation, needs test

   The state shale be made available to users and modules, which may in turn modify the
   state (e.g. for analysis or based on the results of a physical calculation). ARMI
   shall fully define how all aspects of state may be accessed and modified and shall
   reflect any new state after it is applied.

   State shall be represented as evolving either through time (i.e. in a typical cycle-
   by-cycle analysis) or through a series of control configurations.

.. req:: The operator package shall provide a means by which to communicate inputs and results between analysis modules.
   :id: REQ_operator_io
   :status: needs implementation, needs test

The operator package shall receive output from calculation modules and store the results on a well-defined central model. A composite pattern shall be used, with a Reactor containing Assemblies containing Blocks, etc.

.. req:: The operator package shall provide a means to perform computations in parallel on a high performance computer.
   :id: REQ_operator_parallel
   :status: needs implementation, needs test

Many analysis tasks require high performance computing (HPC), and the operator package shall contain utilities and routines to communicate with an HPC and to facilitate execution of simulations in parallel.

.. req:: The operator package shall allow physics coupling between analysis modules.
   :id: REQ_operator_coupling
   :status: needs implementation, needs test

For coupled physics (e.g. neutronics depends on thermal hydraulics depends on neutronics), the operator package shall allow loose and/or tight coupling. Loose coupling is using the values from the previous timestep to update the next timestep. Tight is an operator-splitting iteration until convergence between one or more modules.

.. req:: The operator package shall allow analysis modules to be replaced without affecting interfaces in other modules.
   :id: REQ_operator_analysis
   :status: needs implementation, needs test

Often, a module is replaced with a new module fulfilling some new requirement. When this happens, the operator package shall isolate required changes to the new module. For example, if a fuel performance module needs temperatures but the temperature-computing module is replaced, the fuel performance module should require no changes to work with the drop-in replacement. This requires modular design and standardization in state names.

.. req:: The operator package shall coordinate calls to the various modules.
   :id: REQ_operator_coord
   :status: needs implementation, needs test

Based on user settings, the ordering, initialization, and calls to other modules shall be coordinated by the operator package. The operator package must therefore be aware of dependencies of each module.

.. req:: The latticePhysics package will execute the lattice physics code in a parallel, serial, or distributed fashion depending on the mode.
   :id: REQ_lattice_execute
   :status: needs implementation, needs test

.. req:: The nucDirectory package shall contain basic nuclide information for a wide range of nuclides.
   :id: REQ_NUCDIR_DATA
   :status: needs implementation, needs test

The nucDirectory package shall contain the following general information for each nuclide:

- name
- symbol
- natural isotopic abundance of elements
- atomic number (Z)
- mass number (A)
- atomic weight
- meta stable state

.. req:: The nucDirectory package shall store data separately from code.
   :id: REQ_NUCDIR_FILES
   :status: needs implementation, needs test

The software shall be made flexible such that the definition of specific nuclides available (i.e. those used in a version of MCC), can be updated without modifying the code.

TODO: This can be tested by inspecting the logic of the code to retrieve data from a resource file, or by modifying the resource file to create an expected outcome.

.. req:: The nucDirectory package shall enforce unique nuclide names.
   :id: REQ_NUCDIR_UNIQUE
   :status: needs implementation, needs test

The nuclides names shall be unique, and consist of the nuclide's symbol, mass number, and an indication if it is in a meta-stable state. Elemental nuclides shall omit the mass number, since they represent more than a single mass number. Lumped nuclides shall also have unqiue, user-data identified names.

TODO: A unit test can be used to demonstrate that all nuclide names are unique.

.. req:: The nucDirectory package shall be capable of generating unique 4-character labels.
   :id: REQ_NUCDIR_LABELS
   :status: needs implementation, needs test

Versions 2 and 3 of MCC allow for unique 6 character labels to be used to reference nuclides. Two characters need to be used to describe the differen cross section sets used by the problem. Therefore, every nuclide in ARMI needs to have a unique 4 character representation to use in MCC and the downstream global flux solver.

TODO: A unit test can be used to demonstrate that all nuclides have unique 4-character labels.

.. req:: The nucDirectory package shall allow for use of lumped nuclides.
   :id: REQ_NUCDIR_LUMPED
   :status: needs implementation, needs test

Lumped nuclides are bulk defined nuclides that are typically used when modeling fission products. Lumping the nuclides during burnup calculations lowers the problem size without having a significant impact on the results. Consequently, they do not always need to be modeled individually, but can be grouped.

A unit test can be used to demonstrate that lumped nuclides can be used and created.

.. req:: The nucDirectory package shall allow for elemental nuclides.
   :id: REQ_NUCDIR_ELEMENTALS
   :status: needs implementation, needs test

The nuclear data libraries available in versions 2 and 3 of MCC do not always allow for nuclide input, and some materials are grouped into elemental nuclides. Iron is an example of this in MCC version 2. Consequently, ARMI needs to be able to model elemental nuclides which represent the entire element, as well as the individual nuclides.

.. req:: The nucDirectory package shall allow for dummy nuclides.
   :id: REQ_NUCDIR_DUMMY
   :status: needs implementation, needs test

Dummy nuclides, typically written in all capitals as "DUMMY", are used to truncate the burn chain in order to reduce the problem size without compromising the results.

.. req:: The nucDirectory package shall allow for indexing of nuclide information.
   :id: REQ_NUCDIR_INDEX
   :status: needs implementation, needs test

The nuclear data files created by physics codes such as MCC and DIF3D may not necessary correspond to the name used within ARMI, it will be necessary to load nuclide information based on a non-ARMI name. The software shall provide lookup mechanisms for nuclide objects based on:

- Name
- 4-character label
- MCC versions 2 and 3 IDs

.. req:: The nucDirectory package shall contain decay chain data.
   :id: REQ_NUCDIR_DECAY_CHAIN
   :status: needs implementation, needs test

The decay chain is an important step in performing burn-up calculations. The nucDirectory shall contain necessary decay mechanisms:

- `\beta^-`
- `\beta^+`
- `\alpha`
- Electron capture
- Spontaneous fission

The nucDirectory shall contain the half-life, decay mode(s) with corresponding branch ratio(s) and daughter nuclide(s) of each decay mode being modeled. Since it is possible for the user to define specific nuclides to be modeled, the nucDirectory shall allow for use of different daughter nuclides.

TODO: A unit test can be generated to test that the correct decay chain is present, and that the data matches other resources.

.. req:: The nucDirectory package shall contain transmutation data.
   :id: REQ_NUCDIR_TRANSMUTE
   :status: needs implementation, needs test

In addition to the decay chain, nuclides may transmute through interactions into other nuclides. The nucDirectory shall contain the transmutations necessary for modeling a TWR, including:

- `n,2n`
- `n,p`
- `n,t`
- fission
- `n,\gamma`
- `n,\alpha`

The nucDirectory shall contain the transmutation mechanism, branch ratio, and product nuclides of each transmutation being modeled. The nucDirectory shall not contain the cross sections, as these are calculated using lattice physics codes, such as MCC. Since it is possible for the user to define specific nuclides to be modeled, the nucDirectory shall allow optional daughter nuclides.

TODO: A unit test can be generated to test that the correct transmutations are present, and corresponding data matches other resources.

.. req:: The nucDirectory package shall warn the user if there are potential burn-chain faults.
   :id: REQ_NUCDIR_BURN_CHAIN
   :status: needs implementation, needs test

The user supplies the nuclides to be modeled in the simulation; therefore, it is possible that the user may inadvertently describe a burn-chain that is not complete. The software shall be capable of detecting erroneous user input and terminate the program.

TODO: A unit test can be generated with faulty decay chains to determine that they do not work.

.. req:: The nuclearDataIO package shall read and write ISOTXS files.
   :id: REQ_NUCDATA_ISOTXS
   :status: needs implementation, needs test

ISOTXS files contain the multi-group microscopic cross sections, and other nuclear data, for each nuclide being modeled. The multi-group cross sections are used throughout ARMI.

The software shall be capable of reading an ISOTXS file, as defined in `CCCC-IV <https://code.terrapower.com/terrapower/tparmi/blob/develop/doc/reference/nuclearDataIO.rst#cccc-iv>`_, into memory, and writing it out to a file that is exactly the same as the original.

TODO: A unit test can be created with reads an ISOTXS file generated by MCC, and then writes out the file to another name. The two files can then be compared using a binary file comparison to demonstrate that the contents of the files are identical.

.. req:: The nuclearDataIO package shall read and write GAMISO files.
   :id: REQ_NUCDATA_GAMISO
   :status: needs implementation, needs test

GAMISO files are generated by MCC-v3, and are the same format as an ISOTXS file. The file contains photon interaction cross sections instead of neutron cross sections.

The software shall be capable of reading a GAMISO file into memory, and writing it out into a file that is exactly the same as the original.

TODO: This can be covered in a unit test; the unit test can be the same as described for ISOTXS files.

.. req:: The nuclearDataIO package shall read and write PMATRX files.
   :id: REQ_NUCDATA_PMATRX
   :status: needs implementation, needs test

PMATRX files contain the gamma production matrix resulting from fission or capture events. Given a neutron flux distribution, and a PMATRX file, the gamma source can be computed and then used to determine gamma transport and heating.

.. req:: The nuclearDataIO package shall be capable of reading a PMATRX file into memory, and writing it out into a file that is exactly the same as the original.

TODO: This can be covered in a unit test; the unit test can be the same as described for ISOTXS files.

.. req:: The nuclearDataIO package shall read and write DLAYXS files
DLAYXS files contain delayed neutron data, such as precursor decay constants and number of neutrons emitted, :math:`\nu_{\mathrm{delay}}`. The DLAYXS data is used to calculate :math:`\beta_{\rm{eff}}`, which is used to calculate reactivity coefficients, and consequently in AOO and accident simulations.

The software shall be capable of reading a DLAYXS, as defined in `CCCC-IV <https://code.terrapower.com/terrapower/tparmi/blob/develop/doc/reference/nuclearDataIO.rst#cccc-iv>`_, file into memory, and writing it out into a file that is exactly the same as the original.

TODO: This can be covered in a unit test; the unit test can be the same as described for ISOTXS files.

.. req:: The nuclearDataIO package shall merge files of the same type.
   :id: REQ_NUCDATA_MERGE
   :status: needs implementation, needs test

The software shall be capable merging multiple files of the same type (ISOTXS, PMATRX, etc.) into a single file meeting the specifications. The software shall fail with a descriptive error message if any two nuclides have the same name.

This can be covered in a unit test which runs 3 MCC-v3 cases.

1. Generate cross sections for a set of nuclides with the xsID=AA 1. Generate cross sections for a set of nuclides with the xsID=AB 1. Generate cross sections with two regions using an input file containing the nuclides of the above two cases.

The third MCC-v3 case will produce a merged ISOTXS file which can be compared to an ISOTXS file generated by merging the output ISOTXS from cases 1 and 2.

.. req:: The nuclearDataIO package shall make the data programmatically available.
   :id: REQ_NUCDATA_AVAIL
   :status: needs implementation, needs test

The software shall make the nuclear data provided in ISOTXS, GAMISO, PMATRX and DLAYXS available in the form of Python objects, such that it can be used elsewhere in the code, such as in the depletion, nuclear uncertainty quantification, and `\beta` calculations.

   .. req:: The nuclearDataIO package shall key nuclear data based on nuclide label and xsID.
      :id: REQ_NUCDATA_AVAIL_LABEL
      :status: needs implementation, needs test

When nuclear data files are read, they should be made available in a container object, such as a dictionary, and keyed on the nuclide label (a unique four character nuclide identifier) and the cross section ID, a two character identifier for block type and burnup group.

TODO: This can be covered by a unit test which reads an ISOTXS into a container object, and then obtaining cross sections by using the nuclide label and xsID.

   .. req:: The nuclearDataIO package shall be able to remove nuclides from specifc nuclear data files.
      :id: REQ_NUCDATA_AVAIL_FILES
      :status: needs implementation, needs test

ARMI has a concept of "lumped fission products" that result in more nuclides being in ISOTXS, GAMISO, and PMATRX files than are needed for subsequent calculations. The software shall be capable of removing the unused nuclides from ISOTXS, GAMISO, and PMATRX files. This generally does not apply to DLAYXS files, because they typically only contain nuclides that fission.

TODO: This can be covered by a unit test where a file is read in, a nuclide removed, and then rewritten and reread. The reread file should not contain the removed nuclides.

   .. req:: The nuclearDataIO package shall be able to modify the nuclear data.
      :id: REQ_NUCDATA_AVAIL_MODIFY
      :status: needs implementation, needs test

In order to calculate the uncertainties of our methodology introduced by nuclear data uncertainty, it is necessary to be able to perturb (i.e. modify) specific values within the nuclear data files.

TODO: This can be covered by a unit test where a file is read in, a cross section or relevant piece of data modified, and then rewritten and reread. The reread file should contain the modified data.

------------------------
Performance Requirements
------------------------

.. req:: The database representation on disk shall be smaller than the the in-memory Python representation
   :id: REQ_DB_PERFORMANCE
   :status: needs implementation, needs test

The database implementation shall use lossless compression to reduce the database size.

.. req:: The report package shall present no burden.
   :id: REQ_REPORT_PERFORMANCE
   :status: needs implementation, needs test

As the report package is a lightweight interface to write data out to a text based format, and render a few images, the performance costs are entirely negligible and should not burden the run, nor the user's computer in both memory and processor time.

.. req:: The reactor package shall allow rapid synchronization of state across the network to parallel processors.
   :id: REQ_REACTOR_PARALLEL
   :status: needs implementation, needs test

For performance, many physics calculations are done in parallel. The reactor must be able to synchronize
the state on multiple processors efficiently.

.. req:: The nucDirectory package shall, wherever possible, the software shall prevent duplication of data to limit the memory footprint of this information.
   :id: REQ_NUCDIR_DUPLICATION
   :status: needs implementation, needs test

TODO: Is this testable?


-------------------
Software Attributes
-------------------

.. req:: The database produced shall be easily accessible in a variety of operating systems.
    :id: REQ_DB_OS
    :status: needs implementation, needs test

.. req:: The database produced shall be easily accessible in a variety of programming environments beyond Python.
    :id: REQ_DB_LANGUAGE
    :status: needs implementation, needs test

.. req:: The report package shall be easily accessible in a variety of operating systems.
    :id: REQ_REPORT_OS
    :status: needs implementation, needs test


.. req:: The settings package shall use human-readable, plain-text files as input.
   :id: REQ_SETTINGS_READABLE
   :status: implemented, needs more tests

The user must be able to read and edit their settings file as plain text in broadly any typical text editor.


---------------------------
Software Design Constraints
---------------------------

.. req:: The database package shall provide compatability with all previously generated databases.
    :id: REQ_DB_BACKWARDS_COMPAT
    :status: needs implementation, needs test

With very few redesign exceptions, as qualified cases are produced for analysis and rerunning, it is imperative the data always be in an accesible form.

.. req:: The report package shall not burden new developers with grasping a complex system.
    :id: REQ_REPORT_TECH
    :status: needs implementation, needs test

Given the functional requirements of the report package, new developers should be able to understand how to contribute to a report nigh instantly. No new technologies should be introduced to the system as HTML and ASCII are both purely text-based.

.. req:: The reactor package shall not exhibit any stochastic behavior.
    :id: REQ_REACTOR_STOCHASTIC
    :status: needs implementation, needs test

Given a set of input the same reactor design and run should be proceed in a fixed fashion for reproduction.

The nucDirectory package shall use nuclear data that is contained within the ARMI code base. That is, the data will not be retrieved from online sources. The intent here is to prevent inadvertent security risks.

The nucDirectory package shall follow a particular naming convention. Other physics codes use the name Am-242 for the metastable state of Am-242, and use Am-242g for the ground state.


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
   :status: needs implementation, needs test

.. req:: The latticePhysics package will use the output(s) to create a reactor library, ``ISOTXS`` or ``COMPXS``, used in the global flux solution.
   :id: REQ_lattice_outputs
   :status: needs implementation, needs test

.. reg:: The reactor package shall check input for basic correctness.
   :id: REQ_reator_correctness
   :status: needs implementation, needs test

The reactor package shall check its input for certain obvious errors including unphysical densities and proper fit.



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
