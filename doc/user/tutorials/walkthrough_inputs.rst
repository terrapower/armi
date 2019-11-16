=======================================
Building input files for a fast reactor
=======================================

The true power of ARMI comes when you have a reactor at your fingertips. To get this,
you must describe the reactor via input files.
This tutorial will walk you through building input files from scratch for a reactor.
We will model the CR=1.0 sodium-cooled fast reactor documented in `ANL-AFCI-177
<https://publications.anl.gov/anlpubs/2008/05/61507.pdf>`_.

.. tip:: The full inputs created in this tutorial are available for download at the bottom of 
	this page.

Setting up the blueprints
=========================
First we'll set up the fuel assembly design in the blueprints input. Make a new
file called ``anl-acfi-177-blueprints.yaml``. We'll be entering information
based on Table 4.4 of the reference. To define the pin cell we need dimensions
of the fuel pin, cladding, ducts, wire wrap, and so on. 

The cladding dimensions are clear from the table. The outer diameter is given
as the pin diameter, and the inner diameter is simply that minus twice the
cladding thickness. We will use the ``Circle`` shape, and make the material
``HT9`` steel. Since we're inputting cold dimensions, we'll set ``Tinput`` to
room temperature and let ARMI thermally expand the clad up to an average
operating temperature of 450 °C. Lastly, since there are 271 pins in the
assembly, we'll set the ``mult`` (short for *multiplicity*) to 271:


.. literalinclude:: ../../../armi/tests/tutorials/anl-afci-177-blueprints.yaml
    :language: yaml
    :start-after: start-block-clad
    :end-before: end-block-clad


.. note:: In fast reactors, neutrons aren't as affected by spatial details at a
    pin level, and compositions are often quite spatially flat across an assembly.
    Thus we can often just copy a component using the ``mult`` input equal to the
    number of pins, and neutronic modeling is sufficient. For subchannel T/H, the
    spatial details are of course much more important. 

.. note:: The ``&block_fuel`` is a YAML anchor which will be discussed more below. 

Next, let's enter the wire wrap. This is a helical wire used in fast reactors
to mix coolant and keep pins separate (used in lieu of a grid spacer). ARMI has
a special shape for this, called a ``Helix``. Helices are defined by their
axial pitch (how much linear distance between two wrappings axially), the wire
diameter, and the diameter of the pin they're wrapping around (called
``helixDiameter``).  Thus, we input the wire wrap into the blueprints as
follows. 

.. note:: The wire axial pitch isn't specified in the table so we just use a typical value of 30 cm. 

.. literalinclude:: ../../../armi/tests/tutorials/anl-afci-177-blueprints.yaml
    :language: yaml
    :start-after: end-block-clad
    :end-before: end-block-wire


We set the wire inner diameter to 0 to make it a solid wire. If we set it to
something non-zero, the wire itself would be hollow on the inside, which would
be crazy.

Now, it's time to do the fuel. This example reactor uses UZr metal fuel with a
liquid sodium thermal bond in the large gap between the fuel and the cladding.
The fraction of space inside the clad that is fuel is called the "smeared
density", so we can figure out the actual fuel slug dimensions from the
information in the table. 

Specifically, the smeared density is 75%, which means that 75% of the area
inside the circle made by the inner diameter of the cladding (0.6962 cm) is
fuel. Thus, the fuel outer diameter is given by solving:

.. math:: 
       0.75 = \frac{\pi d^2}{\pi 0.6962^2}

which gives :math:`d = 0.6029`, our fuel outer diameter. Now we can enter our
fuel slug component into blueprints:

.. literalinclude:: ../../../armi/tests/tutorials/anl-afci-177-blueprints.yaml
    :language: yaml
    :start-after: end-block-wire
    :end-before: end-block-fuel


.. note:: We upped the hot temperature to 500 °C, indicative of the fact that fuel will be running a bit hotter than
        cladding.

Let's enter a description of the thermal bond next. This is an annulus of
sodium between the fuel and the cladding.  Since those dimensions are already
set, we will use **linked dimensions**. Thus, no numbers (beyond temperatures)
are needed! 


.. literalinclude:: ../../../armi/tests/tutorials/anl-afci-177-blueprints.yaml
    :language: yaml
    :start-after: end-block-fuel
    :end-before: end-block-bond


The next physical component we need to model is the hexagonal assembly duct.
This information is provided in Table 4.3 of ANL-AFCI-177. For the ``Hexagon``
shape, we enter inner and outer flat-to-flat distances ("pitch") instead of
diameters. The outer pitch is given as ``15.710``, and we can calculate the
inner pitch from that and the duct thickness. It ends up looking like this:


.. literalinclude:: ../../../armi/tests/tutorials/anl-afci-177-blueprints.yaml
    :language: yaml
    :start-after: end-block-bond
    :end-before: end-block-duct


It's essential to capture the spacing between adjacent ducts too (the assembly
pitch, also defined in Table 4.3), and we define this by defining a special
``Hexagon`` full of interstitial coolant outside the duct:


.. literalinclude:: ../../../armi/tests/tutorials/anl-afci-177-blueprints.yaml
    :language: yaml
    :start-after: end-block-duct
    :end-before: end-block-intercoolant


That defines everything in our assembly except for the coolant. The shape of
the coolant is geometrically complex, it's a hexagon with holes punched
through it (one for each cladding tube/wire wrap). Rather than explicitly
defining this shape, ARMI allows you to input a ``DerivedShape`` in certain
conditions (e.g. when the rest of the assembly is filled and only one
``DerivedComponents`` is defined. It can simply back-calculate the area of this
shape automatically. And that's just what we'll do with the coolant:


.. literalinclude:: ../../../armi/tests/tutorials/anl-afci-177-blueprints.yaml
    :language: yaml
    :start-after: end-block-intercoolant
    :end-before: end-block-coolant


And that completes our generic fuel block description.

Defining non-fuel blocks
------------------------
For this core model, we will need some reflectors, shields, and control blocks
as well. In detailed models, it can often be important to model these in
detail. For this example, we'll keep it simple. Control blocks will simply be
filled with sodium (representing an all-rods-out condition), reflectors will
just be full pins of HT9 steel with coolant around them, and shields will be
unclad B4C in sodium. Normally the pin sizes would be different, but again for
simplicity, we're just duplicating the pin dimensions.

For brevity, we will simply provide the definitions as described. 

Radial Shields
^^^^^^^^^^^^^^
Here is a very simplified radial shield:


.. literalinclude:: ../../../armi/tests/tutorials/anl-afci-177-blueprints.yaml
    :language: yaml
    :start-after: end-block-coolant
    :end-before: end-block-radialshield


Reflectors
^^^^^^^^^^
Here is a reflector block definition. We can use this for radial reflectors and
axial reflectors. We include wire wrap so the axial reflector will work with
our basic thermal hydraulic solver:

.. literalinclude:: ../../../armi/tests/tutorials/anl-afci-177-blueprints.yaml
    :language: yaml
    :start-after: end-block-radialshield
    :end-before: end-block-reflector


Control
^^^^^^^
Here is a big empty sodium duct (what you'd find below a control absorber bundle):


.. literalinclude:: ../../../armi/tests/tutorials/anl-afci-177-blueprints.yaml
    :language: yaml
    :start-after: end-block-reflector
    :end-before: end-block-control


Plenum
^^^^^^
We also need to define empty cladding tubes above the fuel for the fission
gasses to accumulate in. This just has a ``gap`` component made of the ``Void``
material, which is just empty space:

.. literalinclude:: ../../../armi/tests/tutorials/anl-afci-177-blueprints.yaml
    :language: yaml
    :start-after: end-block-control
    :end-before: end-block-plenum


That should be enough to define the whole core. 

Defining how the blocks are arranged into assemblies
----------------------------------------------------
With block cross-sections defined, we now set their heights and stack them up
into assemblies. While we're at it, we can conveniently adjust some
frequently-modified material parameters, such as the uranium enrichment. 

Defining the fuel assemblies
^^^^^^^^^^^^^^^^^^^^^^^^^^^^
There are three fuel assemblies defined in ANL-AFCI-177, each with different
enrichments. We can specify some assembly data to be shared across all
assemblies and just overlay the differences. We define the ``assemblies``
section of the blueprints input file. We get core and plenum height from table
4.4, and split the core into 5 equally-sized sections at 20.32 cm tall each.
This defines the depletion mesh. Each of these 5 blocks will deplete and
accumulate state independently. In the ``axial mesh points`` section, we
specify a roughly even neutronic/transport mesh, with slightly larger neutronic
mesh points in the very tall single-block plenum:


.. literalinclude:: ../../../armi/tests/tutorials/anl-afci-177-blueprints.yaml
    :language: yaml
    :start-after: end-block-plenum
    :end-before: end-assemblies-common


Now that the common heights and neutronic mesh are specified, we start applying
them to the various individual assemblies. We start with the inner core and
refer to the heights and mesh with YAML anchors. As described in Section 2.0 of
the reference, an enrichment splitting of 1.0, 1.25, and 1.5 was used for
inner, middle, and outer core in order to help minimize radial power peaking.
The specific enrichments of each zone are shown in Table 4.8. For simplicity,
let's just use these as uranium enrichments rather than the detailed material
from the paper. Specifying more details is possible via the **custom
isotopics** input fields.:


.. literalinclude:: ../../../armi/tests/tutorials/anl-afci-177-blueprints.yaml
    :language: yaml
    :start-after: end-assemblies-common
    :end-before: end-assemblies-ic


.. warning:: The weirdest thing about this input section is the use of YAML
    anchors for the blocks. Under the hood, this copies the entire block definition
    into each entry of that list. This is a bit strange, and we plan to switch this
    to a string-based block name rather than a full YAML anchor in the ``blocks``
    list.

.. note:: Notice the blank strings in the ``U235_wt_frac`` section? Those are
    placeholders indicating that the material in those blocks does not have uranium
    in it, and thus adjusting uranium enrichment doesn't make sense. These are the
    axial reflectors, plena, grid plates, etc.

For the middle core, we can use the same stack of blocks (using an anchor), but
we need different enrichments. We can choose whether or not to use the same
``xs types``. When composition is different, one often uses independent cross
section types so you get cross sections specific to different enrichments. This
is a trade-off, since more cross section types means more lattice physics
calculations, which can require either more time or more processors:


.. literalinclude:: ../../../armi/tests/tutorials/anl-afci-177-blueprints.yaml
    :language: yaml
    :start-after: end-assemblies-ic
    :end-before: end-assemblies-mc


Same deal for the outer core.

.. note:: The columnar form of YAML lists is very convenient when using text editors with column-edit capabilities. It
        is highly recommended to make sure you know how to column edit. 


.. literalinclude:: ../../../armi/tests/tutorials/anl-afci-177-blueprints.yaml
    :language: yaml
    :start-after: end-assemblies-mc
    :end-before: end-assemblies-oc


Defining the non-fuel assemblies
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Let's make some shield, reflector, and control assemblies. It's fine for these
to have different numbers of blocks. Some physics kernels (like DIF3D) have
some requirements of axial mesh boundaries at least lining up between
assemblies, but there are some ARMI features that can automatically adjust the
mesh if you have very complicated assemblies:

.. literalinclude:: ../../../armi/tests/tutorials/anl-afci-177-blueprints.yaml
    :language: yaml
    :start-after: end-assemblies-oc
    :end-before: end-assemblies-rr


.. note:: Here we just re-use the fuel block cross sections. In more precise models, a different approach
	may be used.

Here is the radial shield:

.. literalinclude:: ../../../armi/tests/tutorials/anl-afci-177-blueprints.yaml
    :language: yaml
    :start-after: end-assemblies-rr
    :end-before: end-assemblies-sh


Here are the control blocks:

.. literalinclude:: ../../../armi/tests/tutorials/anl-afci-177-blueprints.yaml
    :language: yaml
    :start-after: end-assemblies-sh
    :end-before: end-assemblies-section


And that's it! All blueprints are now defined.

Specifying the core map
=======================
With blueprints defined we can now arrange assemblies into the core. This is with the geometry input file. 

.. note:: There are GUI tools to help making the core map easy to set up.

.. note:: We plan to converge on consistent input between pin maps and core maps for the physics kernels
        and analyses that require finer detail of how the pins are arranged within blocks.

Geometry can be input various ways. The most straightforward is to provide a
simple ASCII-based map of the core.  For this problem, a 1/3 hexagonal model
can be input as follows (see Figure 4.3 in the reference). First, we refer to a
geometry file from the ``systems`` section of the ``blueprints`` file:


.. literalinclude:: ../../../armi/tests/tutorials/anl-afci-177-blueprints.yaml
    :language: yaml
    :start-after: end-assemblies-section
    :end-before: end-systems-section


And then, in the core map file (``anl-afci-177-coreMap.yaml``):

.. literalinclude:: ../../../armi/tests/tutorials/anl-afci-177-coremap.yaml
    :language: yaml


.. note:: The two-letter values here can be any contiguous strings, and
    correspond with the ``specifier`` field in the blueprints input. 

.. note:: GUI utilities are also useful for building core maps like this. 


Specifying settings
===================
Now we need to specify some **settings** that define fundamental reactor
parameters, as well as modeling approximation options. For this, we make a
**settings file**, called ``anl-acfi-177.yaml``. 

The thermal power in this reference is 1000 MWt. The thermal efficiency isn't
specified, so let's assume 0.38. From Table 4.8, the cycle length is 370 EFPD.
Let's also assume a 0.90 capacity factor which will gives full cycles of 411.1
days. 

.. literalinclude:: ../../../armi/tests/tutorials/anl-afci-177.yaml
    :language: yaml
    :start-after: begin-settings
    :end-before: end-section-1

We need to tell the system which other input files to load by bringing in the
blueprints and geometry (the shuffling and fuel handler info will be described
momentarily):

.. literalinclude:: ../../../armi/tests/tutorials/anl-afci-177.yaml
    :language: yaml
    :start-after: end-section-1
    :end-before: end-section-2

In terms of our simulation parameters, let's run it for 10 cycles, with 2 depletion time steps per cycle:

.. literalinclude:: ../../../armi/tests/tutorials/anl-afci-177.yaml
    :language: yaml
    :start-after: end-section-2
    :end-before: end-section-3

Set some physics kernel and environment options:

.. literalinclude:: ../../../armi/tests/tutorials/anl-afci-177.yaml
    :language: yaml
    :start-after: end-section-3


.. note:: The ARMI GUI is simply an optional frontend to this settings file. Behind the scenes it just reads and writes
        this. It is quite convenient for discovering important settings and describing what they do, however.

Defining fuel management
========================
Finally, let's specify the fuel management file that we referred to above by
creating the file ``anl-afci-177-fuelManagement.py``. Fuel management is very
wide-open, so we use Python scripts to drive it. It's generally overly
constraining to require any higher-level input for such a general problem. 

In ANL-AFCI-177, section 2 says no shuffling was modeled, and that the core is
in a batch shuffling mode, limited by a cladding fast fluence of 4.0e23 n/cm\
:sup:`2`. Often, SFR studies use the REBUS code's implicit equilibrium fuel
cycle mode. There is an ARMI equilibrium module at TerraPower that performs
this useful calculation (with different inputs), but for this sample problem,
we will simply model 10 cycles with explicit fuel management. 

The shuffling algorithm we'll write will simply predict whether or not the
stated fluence limit will be violated in the next cycle. If it will be, the
fuel assembly will be replaced with a fresh one of the same kind. 


.. literalinclude:: ../../../armi/tests/tutorials/anl-afci-177-fuelManagement.py
    :language: python


There! You have now created all the ARMI inputs, from scratch, needed to
perform a simplified reactor analysis of one of the SFRs in the ANL-AFCI-177
document. The possibilities from here are only limited by your creativity, (and
a few code limitations ;). 

As you load the inputs in ARMI it will provide some consistency checks and
errors to help identify common mistakes.

Here are the full files used in this example:

* :download:`Blueprints <../../../armi/tests/tutorials/anl-afci-177-blueprints.yaml>`
* :download:`Settings <../../../armi/tests/tutorials/anl-afci-177.yaml>`
* :download:`Core map <../../../armi/tests/tutorials/anl-afci-177-coremap.yaml>`
* :download:`Fuel management <../../../armi/tests/tutorials/anl-afci-177-fuelManagement.py>`

The next tutorial will guide you through inputs for a classic LWR benchmark problem (C5G7).
