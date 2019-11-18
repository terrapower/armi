==========================================
Building input files for a thermal reactor
==========================================

In the :doc:`previous tutorial </user/tutorials/walkthrough_inputs>`,
we introduced the basic input files and made a full
input for a sodium-cooled fast reactor. In this tutorial, we will build simple
inputs for the light-water reactor (LWR) benchmark problem called C5G7 as defined
in `NEA/NSC/DOC(2003)16 <https://www.oecd-nea.org/science/docs/2003/nsc-doc2003-16.pdf>`_.

.. tip:: The full inputs created in this tutorial are available for download at the bottom of
	this page.

Setting up the blueprints
=========================
This tutorial is shorter than the previous, focusing mostly on the new information.

Custom isotopic vectors
-----------------------
When using materials that differ in properties or composition from the
materials in the ARMI material library, you can use custom isotopics
to specify their composition.

The C5G7 benchmark problem does not define specific compositions. Instead, it
specifies multigroup macroscopic cross sections in a few regions. For the purposes
of this tutorial, we will ignore the cross sections and just input the
geometry. Thus, rather than specifying the actual composition, we will
start by defining dummy isotopic vectors (using U-235 for every material). Feel
free to add more realistic compositions to these definitions.

.. literalinclude:: ../../../armi/tests/tutorials/c5g7-blueprints.yaml
    :language: yaml
    :start-after: start-custom-isotopics
    :end-before: end-custom-isotopics

.. tip:: Scripts that load the prescribed cross sections from the benchmark
    into the ARMI cross section model could be written fairly easily, allowing
    users to quickly evaluate this full benchmark problem with various global
    solvers.

The UO2 block
-------------
Now we define the pins and other components of the UO2 block.
What's new here is that we're pointing to custom isotopics
in many cases, and we're using the ``latticeIDs`` input to add
textual specifiers, which will be used in the ``grids`` input section
below to count and place the pins into a square-pitch lattice. Note that
the ``latticeIDs`` section is a list. The component will fill every
position in the grid that has any of the specifiers in this list.

.. literalinclude:: ../../../armi/tests/tutorials/c5g7-blueprints.yaml
    :language: yaml
    :start-after: end-custom-isotopics
    :end-before: end-block-uo2

.. note:: The dummy pitch component has no material and is simply used to
    define the assembly pitch. In a future upgrade, this information will
    be taken directly from the ``lattice pitch`` grid definition below.

The MOX block
-------------
The next assembly is very similar. We define three separate fuel pins,
each with different ``latticeIDs``, and then use YAML anchors to just
copy the moderator, guide tube, and fission chamber from the previous assembly.

.. literalinclude:: ../../../armi/tests/tutorials/c5g7-blueprints.yaml
    :language: yaml
    :start-after: end-block-uo2
    :end-before: end-block-mox

The moderator block
-------------------
The moderator block for the radial and axial reflectors is very simple:

.. literalinclude:: ../../../armi/tests/tutorials/c5g7-blueprints.yaml
    :language: yaml
    :start-after: end-block-mox
    :end-before: end-block-mod

The 3-D Assembly definitions
----------------------------
Now that the pins are defined, we stack them into assemblies, very similar
to what we did in the SFR tutorial. There are three distinct assembly definitions.

.. literalinclude:: ../../../armi/tests/tutorials/c5g7-blueprints.yaml
    :language: yaml
    :start-after: end-block-mod
    :end-before: end-assemblies

The Systems definition
----------------------
This problem only considers a core, so we will only have a core system in this
problem. If pumps, heat exchangers, spent fuel pools, etc were to be modeled,
they would be here alongside the core. We also anchor the core at the global
coordinates (0,0,0). If we wanted the core at some other elevation, we could
adjust that here.

.. literalinclude:: ../../../armi/tests/tutorials/c5g7-blueprints.yaml
    :language: yaml
    :start-after: end-assemblies
    :end-before: end-systems

The Grids definitions
---------------------
Now we define the core map and the assembly pin maps using the
generic grid input section. In the previous tutorial, we loaded the grid definition
from an XML file. In this tutorial, we define the grid directly with an
textual ``lattice map`` input section. The core map is particularly simple; it
only has 9 assemblies.

.. literalinclude:: ../../../armi/tests/tutorials/c5g7-blueprints.yaml
    :language: yaml
    :start-after: end-systems
    :end-before: end-grid-core

The pin map for the UO2 assembly is larger, but still relatively straightforward.
Recall that on the ``uo2`` block above we said that we want to apply the grid
with the name ``UO2 grid``, and wanted to fill any ``U`` position with
the ``fuel`` component defined up there. Here's where we define that grid.

.. literalinclude:: ../../../armi/tests/tutorials/c5g7-blueprints.yaml
    :language: yaml
    :start-after: end-grid-core
    :end-before: end-grid-UO2

Similarly, we define the ``MOX grid`` as follows:

.. literalinclude:: ../../../armi/tests/tutorials/c5g7-blueprints.yaml
    :language: yaml
    :start-after: end-grid-UO2
    :end-before: end-grid-MOX

This grid is more complex in that it has different enrichment zones throughout
the assembly.

Nuclide Flags
-------------
.. literalinclude:: ../../../armi/tests/tutorials/c5g7-blueprints.yaml
    :language: yaml
    :start-after: end-grid-MOX
    :end-before: end-nucflags

The default nuclide flags provided do not contain oxygen or hydrogen, but
these elements are present in the ``SaturatedWater`` material. Thus,
we list them in this input section, and specifically leave out
the trace isotope, ``O18``.

The settings file
=================
Really, the only thing the settings file does in this case is point to the blueprints
file. As we turn this case into an actual run, we may add various cross section
and neutrons options to evaluate the benchmark.

.. literalinclude:: ../../../armi/tests/tutorials/c5g7-settings.yaml
    :language: yaml

Defining fuel management
========================
By not defining any fuel management settings, we skip fuel management for
this benchmark problem entirely.

There! You have now created all the ARMI inputs, from scratch, needed to
represent the C5G7 benchmark problem.

Here are the full files used in this example:

* :download:`Blueprints <../../../armi/tests/tutorials/c5g7-blueprints.yaml>`
* :download:`Settings <../../../armi/tests/tutorials/c5g7-settings.yaml>`
