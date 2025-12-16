******************
Spatial block data
******************

Many parameters assigned on a ``Block`` are scalar quantities that are useful for visualization and
simple queries (e.g., block with the maximum burnup in an assembly). Spatial parameters in a block,
such as power produced by each pin, is also of interest. Especially when communicating data to
physics codes that support sub-block geometric modeling. This page will talk about how spatial
information is assigned to components on a block, how spatial data can be assigned and accessed, and
how those data may or may not be updated by the framework.

Sub-block spatial grid
======================

There are two ways to create the block grid: explicitly via blueprints or via an automated builder.
The former is recommended, but the later can work in some specific circumstances.

Blueprints
----------

In your blueprints file, you likely have a core grid that defines where assemblies reside in the reactor. Assemblies
are assigned to locations on that grid according to their ``specifier`` blueprint attribute. Below is an example
of a "flats up" hexagonal core grid of fuel assemblies with 1/3 symmetry.

.. code:: yaml

    grids:
      core:
        geom: hex
        symmetry: third periodic
        lattice map: |
          F
           F
          F F
           F
          F F

We can similarly define a grid for the block with a similar entry in the ``grids`` portion of the blueprints.

.. code:: yaml

    pins:
      geom: hex_corners_up
      symmetry: full
      lattice map: |
         - - - - - - - - - 1 1 1 1 1 1 1 1 1 1
          - - - - - - - - 1 1 1 1 1 1 1 1 1 1 1
           - - - - - - - 1 1 1 1 1 1 1 1 1 1 1 1
            - - - - - - 1 1 1 1 1 1 1 1 1 1 1 1 1
             - - - - - 1 1 1 1 1 1 1 1 1 1 1 1 1 1
              - - - - 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1
               - - - 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1
                - - 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1
                 - 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1
                  1 1 1 1 1 1 1 1 1 0 1 1 1 1 1 1 1 1 1
                   1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1
                    1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1
                     1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1
                      1 1 1 1 1 1 1 1 1 1 1 1 1 1 1
                       1 1 1 1 1 1 1 1 1 1 1 1 1 1
                        1 1 1 1 1 1 1 1 1 1 1 1 1
                         1 1 1 1 1 1 1 1 1 1 1 1
                          1 1 1 1 1 1 1 1 1 1 1
                           1 1 1 1 1 1 1 1 1 1

This creates a ten-ring hexagonal lattice in a "corners up" orientation. While the resulting geometry
may look like a flats up lattice, the individual hexagons that make up a lattice site are corners up.

.. note::

    The sub-block grid does not need to be of a different orientation of the parent block. A flats up
    hex block can have a flats up pin lattice. In most cases, an assembly full of pins will have a pin
    lattice that is off a different type to maximally load pins into the block.

Say we wanted to have a guide tube at the center lattice site with cladding surrounding void and every other lattice
site to contain a fuel pin. We need to add the following items to our block definition to link the grid, and to
assign components to sites on the grid.

1. The block needs a ``grid name`` entry that points to the grid we want to use for this block.
2. Each component that wants to be placed on a lattice site needs a ``latticeIDs`` entry that contains
   the IDs, like assembly specifiers in the core grid, for that component.

In the example above, we have two lattice IDs: ``0`` for the center site and ``1`` for the other pins. These
are chosen for brevity but we could have also done ``fuel`` and ``guide`` or ``F`` and ``G``. Do what makes sense
for you.

.. note::

    Like with assembly specifiers, keeping the lattice IDs to have the same number of characters
    will help the grid render nicer in text editors. This is not a requirement, but it may make life
    easier for you and your team.

Our complete block definition would start like::

    blocks: &block_fuel
        grid name: pins
        fuel:
            shape: Circle
            material: UO2
            Tinput: 20
            Thot: 20
            od: 0.819
            latticeIDs: [1]
        clad:
            shape: Circle
            material: UO2
            Tinput: 20
            Thot: 20
            id: 0.819
            od: 0.9
            latticeIDs: [0, 1]
        void:
            shape: Circle
            material: Void
            Tinput: 20
            Thot: 20
            od: 0.819
            latticeIDs: [0]

Note that we can assign the same component to multiple lattice sites with multiple entries in the
``latticeIDs`` list. Also note that we do not need to assign a ``mult`` entry to these components.
Their multiplicity will be determined based on the number of lattice sites they occupy!

.. seealso::

    The :ref:`LWR tutorial <walkthrough-lwr>` contains additional examples for working with sub-block grids.

Auto grid
---------

In some cases, you may have an assembly that contains one pin type. The framework provides a
mechanism for automatically constructing a spatial grid for the block based only on the multiplicity
of pin-like components. When constructing a block from blueprints, a grid may be added to the block
depending on:

1. The existence of an explicitly defined block grid, like in the previously discussed section, and
2. If the ``autoGenerateBlockGrids`` setting is active.

Should either of these conditions be met, the framework will attempt to add a grid by calling
:meth:`armi.reactor.blocks.Block.autoCreateSpatialGrids`. However, this behavior is not generalized
and only implemented on :class:`armi.reactor.blocks.HexBlock`, which makes the following assumptions:

1. You want a corners up hexagonal lattice grid.
2. The pitch of your hexagonal lattice is determined by :meth:`armi.reactor.blocks.HexBlock.getPinPitch`
   which may place restrictions on what constitutes a pin.
3. The number of pins is determined by :meth:`armi.reactor.blocks.HexBlock.getNumPins` which may
   place similar restrictions on what constitutes a pin.

If the auto grid creation is successful, components with a multiplicity equal to the number of pins
will be assigned locations on the lattice grid.

.. warning::

    Consider subclassing :class:`~armi.reactor.blocks.HexBlock` with specific pin-like methods and
    overriding the :meth:`~armi.reactor.blocks.HexBlock.autoCreateSpatialGrids` if you want complete
    control over this process. Alternatively, use an explicit grid in blueprints.


Interacting with spatial data
=============================

This section will focus on accessing locations of components in the block, locations of specifically
pins, and examples of some pin data that may be assigned to a block's parameter set.

Component locations
-------------------

Components that live on a spatial grid have a ``spatialLocator`` attribute to help indicate where
that component exists in space. If we grab the fuel component from the UO2 block in the
:ref:`ANL AFCI 177 example <walkthrough-inputs>` we can see where it exists in the block::

    >>> import armi
    >>> armi.configure()
    >>> from armi.reactor.flags import Flags
    >>> r = armi.init(fName="anl-afci-177.yaml").r
    >>> fuelAssem = r.core[5]
    >>> fuelBlock = fuelAssem[1]
    >>> fuelBlock.spatialGrid
    <HexGrid -- 2046645914880
    Bounds:
    None
    None
    None
    Steps:
    [ 0.4444 -0.4444  0.    ]
    [0.76972338 0.76972338 0.        ]
    [0. 0. 0.]
    Anchor: <fuel B0009-001 at 008-040-001 XS: C ENV GP: A>
    Offset: [0. 0. 0.]
    Num Locations: 400>
    >>> fuel = fuelBlock.getChildrenWithFlags(Flags.FUEL)[0]
    >>> fuel.getDimension("mult")
    271
    >>> fuel.spatialLocator
    <MultiIndexLocation with 271 locations>

This :class:`~armi.reactor.grids.MultiIndexLocation` is a way to indicate this Component exists at multiple
sites. Each item in this locator is one location on the underlying grid where we could find this component::

    >>> fuel.spatialLocator[0]
    <IndexLocation @ (0,0,0)>
    >>> fuel.spatialLocator[0].getLocalCoordinates()
    array([0., 0., 0.])
    >>> coordsFromFuel = fuel.spatialLocator.getLocalCoordinates()
    >>> coordsFromFuel.shape
    (271, 3)

We get a ``(271, 3)`` array because we have 271 of these fuel components in the block, and each row contains one
(x, y, z) location for that component. We can do this for every component, though some may only exist at a single
site on the grid and be assigned a :class:`~armi.reactor.grids.CoordinateLocation` spatial locator instead. The API
is mostly the same, but attempts to signify such an object does not live on the grid e.g., duct or derived shape
objects::

    >>> duct = fuelBlock.getChildrenWithFlags(Flags.DUCT)[0]
    >>> duct.spatialLocator
    <CoordinateLocation @ (0.0,0.0,0.0)>

Pin locations
-------------

Everything in the before section works for finding center points of pins in your assembly. But often
times you have multiple components that may exist at the same lattice site (e.g., fuel, gap, clad,
maybe a wire?). Or you may have multiple cladded-things that count as pins and but exist in multiple
components. In some circumstances, :meth:`armi.reactor.blocks.HexBlock.getPinCoordinates` may be
useful to find the unique centroids of pins in a block. Using our example above, we get a very
similar set of coordinates when comparing to the coordinates of the fuel pin::

    >>> coordsFromPin = fuel.spatialLocator.getLocalCoordinates()
    >>> coordsFromBlock = fuelBlock.getPinCoordinates()
    >>> (coordsFromPin == coordsFromBlock).all()
    True

In this specific case :meth:`~armi.reactor.blocks.HexBlock.getPinCoordinates` looks at components
with ``Flags.CLAD`` and obtains their locations, and we have one cladding component and it exists at
each of the 271 sites we care about. However, if you have multiple cladding components per lattice
site, such as in the :ref:`C5G7 example <walkthrough-lwr>`, you may see an incorrect number of
locations returned.

.. note::

    Consider making application-specific subclasses of ``Block``, ``HexBlock``, and/or ``CartesianBlock``
    with more targeted implementations of :meth:`~armi.reactor.blocks.Block.getNumPins`,
    :meth:`~armi.reactor.blocks.Block.getPinPitch`, :meth:`~armi.reactor.blocks.Blocks.getPinLocations`
    and other pin-specific methods.


Pin parameter data
------------------

The ARMI framework defines a few parameters that live on the block, but define data for each of the
child pin components. Two examples are ``Block.p.linPowByPin`` and ``Block.p.pinMgFluxes``. These
parameters are structured and related to the output of ``getPinCoordinates`` such that

1. Pin ``i`` can be found at ``Block.getPinCoordinates()[i]``.
2. Parameter data for pin ``i`` can be found at location ``i`` in the parameter array, e.g.,
   ``Block.p.linPowByPin[i]``.

Parameters like ``Block.p.pinMgFluxes`` may be higher dimensional, storing mutli-group flux for each
pin. In this case, the parameter data array has shape ``(nPins, nGroups)`` such that
``Block.p.pinMgFluxes[i, g]`` has the group ``g`` flux in pin ``i``, found at
``Block.getPinCoordinates()[i]``.

Block rotation
==============

.. warning:: 
    
    Rotation is currently only supported for hexagonal blocks

Using the logic from the previous section on pin parameter data, it may be useful to know how
rotating a block changes the data stored on that block.

Spatial locators
----------------

First, rotating a block will update the ``spatialLocator`` attribute on every child of the block.
For objects defined at the center of the block, they will still be located at the center. Objects
with a ``MultiIndexLocator`` will have new locations such that ``spatialLocator[i]`` will be
consistent before and after rotation::

    >>> import math
    >>> # zeroth location is the origin so pick a location that
    >>> # changes through rotation
    >>> fuel.spatialLocator[1]
    <IndexLocation @ (1,0,0)>
    >>> fuel.spatialLocator[1].getLocalCoordinates()
    array([0.4444    , 0.76972338, 0.        ]))
    >>> fuelBlock.rotate(math.radians(60))
    >>> fuel.spatialLocator[1]
    <IndexLocation @ (0,1,0)>
    >>> fuel.spatialLocator[1].getLocalCoordinates()
    array([-0.4444    ,  0.76972338,  0.        ])

Because this sub-block grid is a corners up hex grid, to tightly fit inside the flats up hex block,
one rotation from the north east location, ``(1,0,0)``, reflects this pin across the y-axis.

Pin parameters
--------------

Parameter data that are defined on children of the block are not updated. Therefore data for pin
``i`` will be found in e.g., ``Block.p.pinMgFluxes[i]`` before and after rotation.

Corners and edges
-----------------

Parameters defined on the edges and corners of the block, i.e., those with
:attr:`armi.reactor.parameters.ParamLocation.CORNERS` and
:attr:`~armi.reactor.parameters.ParamLocation.EDGES` will be shuffled in place to reflect the new
rotation. For hexagonal blocks, these parameters should have six entries, e.g., one value for each
corner, starting at the upper right and moving counter clockwise. Let's assign some fake data to our
fuel block from above and see what happens::

    >>> import numpy as np
    >>> fuelBlock.p.cornerFastFlux = np.arange(6, dtype=float)
    >>> fuelBlock.p.cornerFastFlux
    array([0., 1., 2., 3., 4., 5.])
    >>> # Two clockwise rotations of 60 degrees
    >>> fuelBlock.rotate(math.radians(-120))
    >>> fuelBlock.p.cornerFastFlux
    array([2., 3., 4., 5., 0., 1.])

Visually, the upper right corner, number ``0``, has been rotated to the lower right corner, number ``4``.
And the corner ``2``, the leftmost corner, has been moved to corner ``0``, the upper right corner.

Other rotated parameters
------------------------

Other parameters may be updated to reflect some geometric state. The second position of
``Block.p.orientation`` reflects the cumulative rotation around the z-axis and is updated through
rotation. Displacement parameters like ``Block.p.displacementX`` are updated as the displacement
vector rotates through space.
