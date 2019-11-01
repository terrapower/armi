Glossary
========

Here we define a few specialized terms used in this documentation.

.. glossary::

    ANL
        Argonne National Laboratory

    ARMI
        The Advanced Reactor Modeling Interface is a software system
        for nuclear reactor design and analysis.

    assembly
        a basic structural unit in the reactor core that is stacked together by
        a list of blocks. Assemblies typically move together in fuel management.

    block
        a vertical segment of the assembly consisting of components.

    burnup
        Amount of energy that has been extracted from fuel. Can be measured
        in megawatt-days per kilogram of heavy metal (MWd/kgHM) or
        in percent of fissionable atoms that have fissioned.

    BOC
        Beginning-of-cycle; the state of the core after an outage

    BOL
        Beginning-of-life; the fresh-core state of the reactor

    cladding
        Material that surrounds nuclear fuel in pins, keeping radionuclides contained.

    CLI
        Command Line Interface. The method of interacting with software from a command line.

    component
        the basic primitive geometrical body, such as a circle, hex, helix, etc. These have dimensions, 
        temperatures, material properties, and isotopic composition.

    FIMA  
        Fissions per initial metal atom. This is a unit of measuring burnup as a fraction
        of the fissionable nuclides that have fissioned.

    grid plate
        A reactor structure in a sodium-cooled fast reactor that all the fuel assemblies sit on.

    GUI
        Graphical User Interface. The method of interacting with software through a visual display.

    interface
        also named *code interface*; linked to an external program or an
        internal ARMI module to perform a specific calculation function. An example
        is the DIF3D interface that makes use of DIF3D diffusion code for core physics
        calculation. Interfaces are building blocks of ARMI calculations

    In-Use Tests
        Automated software test that shows many modules working together in a way that
        a user would typically use them.

    Liner
        A thin layer of material between fuel and cladding intended to impede chemical
        corrosion and wastage.

    LWR
        Light Water Reactor. The predominant kind of commercial nuclear plant in operation today.

    material
        an object that contains isotopic mass fractions and intrinsic material properties

    MPI
        Message passing interface. This is a protocol for exchanging data around a network to run a code in parallel.

    node
        a specific point in time in a ARMI case.

    operator
        an object that controls the calculation sequence for a specific purpose e.g. a multi-cycle
        quasi-static depletion calculation. Operators trigger interfaces.

    parameter
        A state variable on a reactor, assembly, block, or component object.

    plenum
        An empty space inside the cladding tube above the fuel that holds fission gasses and other things that are produced
        during irradiation.

    reactor
        an object consisting of a core full of assemblies and possibly other structures

    reactor state
        An instantaneous representation of the physical condition of all components of a reactor,
        including dimensions, temperatures, composition, material, shape, flux, dose, stress,
        strain, arrangement, orientation, and so on.

    smear density
        A term used to characterize how much room exists inside the cladding for the fuel to expand into. It is defined
        as the fraction of fuel area divided by total space inside the cladding.

    TWR
        Traveling wave reactor: a reactor that uses a breed-and-burn process to achieve most fast reactor advantages
        without requiring a reprocessing plant.

    Unit Tests
        Software tests that check small units of software.

    V&V
        Validation and Verification. Validation is showing that code results match physical reality (comparisons with known answers or experiments),
        and verification is demonstrating that software is built in a way that satisfies its requirements.

    XTVIEW
        A TerraPower-developed visualization tool that graphically shows ARMI results that
        have been added to a database.

