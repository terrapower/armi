.. _grids:

Grids
-----
Grids are described inside a blueprint file using ``lattice map`` or ``grid contents`` fields to define arrangements in
Hex, Cartesian, or R-Z-Theta. The optional ``lattice pitch`` entry allows you to specify spacing between objects that is
different from tight packing. This input is required in mixed geometry cases, for example if Hexagonal assemblies are to
be loaded into a Cartesian arrangement. The contents of a grid may defined using one of the following:

``lattice map:``
    A ASCII map representing the grid contents
``grid contents:``
    a direct YAML representation of the contents

Example grid definitions are shown below::

.. code-block:: yaml

    grids:
        control:
            geom: hex
            symmetry: full
            lattice map: |
               - - - - - - - - - 1 1 1 1 1 1 1 1 1 4
                - - - - - - - - 1 1 1 1 1 1 1 1 1 1 1
                 - - - - - - - 1 8 1 1 1 1 1 1 1 1 1 1
                  - - - - - - 1 1 1 1 1 1 1 1 1 1 1 1 1
                   - - - - - 1 1 1 1 1 1 1 1 1 1 1 1 1 1
                    - - - - 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1
                     - - - 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1
                      - - 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1
                       - 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1
                        7 1 1 1 1 1 1 1 1 0 1 1 1 1 1 1 1 1 1
                         1 1 1 1 1 1 1 1 2 1 1 1 1 1 1 1 1 1
                          1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1
                           1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1
                            1 1 1 1 1 1 1 1 1 1 1 1 1 1 1
                             1 1 1 1 1 1 1 1 1 1 1 1 1 1
                              1 1 1 1 1 1 1 1 1 3 1 1 1
                               1 1 1 1 1 1 1 1 1 1 1 1
                                1 6 1 1 1 1 1 1 1 1 1
                                 1 1 1 1 1 1 1 1 1 1
    sfp:
        symmetry: full
        geom: cartesian
        lattice pitch:
            x: 50.0
            y: 50.0
        grid contents:
            [0,0]: MC
            [1,0]: MC
            [0,1]: MC
            [1,1]: MC

.. tip:: We have gone through some effort to allow both pin and core grid definitions to share this input and it may
    improve in the future.

You may set up some kinds of grids (e.g. 1/3 and full core hex or Cartesian core loadings) using our interactive
graphical grid editor described more in :py:mod:`armi.utils.gridEditor`.

.. figure:: /.static/gridEditor.png
    :align: center

    An example of the Grid Editor being used on a FFTF input file


Lattice Maps
^^^^^^^^^^^^
TODO: Intro (and ASCII map code)

TODO: Full core cartesian examples

TODO: Full core hex examples, corners vs flats

TODO: Third Core maps are tricky

Two-Ring, Third-Core Hex Maps
"""""""""""""""""""""""""""""
TODO


Three-Ring, Third-Core Hex Maps
"""""""""""""""""""""""""""""""
TODO


Four-Ring, Third-Core Hex Maps
""""""""""""""""""""""""""""""
TODO

.. figure:: /.static/lattice_map/four_ring_hex.png
    :align: center

    Four-ring, third-core, flats up hexagonal lattice map.


Five-Ring, Third-Core Hex Maps
""""""""""""""""""""""""""""""
TODO

.. figure:: /.static/lattice_map/five_ring_hex.png
    :align: center

    Five-ring, third-core, flats up hexagonal lattice map.


Six-Ring, Third-Core Hex Maps
"""""""""""""""""""""""""""""
TODO

.. figure:: /.static/lattice_map/six_ring_hex.png
    :align: center

    Six-ring, third-core, flats up hexagonal lattice map.


Seven-Ring, Third-Core Hex Maps
"""""""""""""""""""""""""""""""
TODO

.. figure:: /.static/lattice_map/seven_ring_hex.png
    :align: center

    Seven-ring, third-core, flats up hexagonal lattice map.


Eight-Ring, Third-Core Hex Maps
"""""""""""""""""""""""""""""""
TODO

.. figure:: /.static/lattice_map/eight_ring_hex.png
    :align: center

    Eight-ring, third-core, flats up hexagonal lattice map.


Nine-Ring, Third-Core Hex Maps
""""""""""""""""""""""""""""""
TODO

.. figure:: /.static/lattice_map/nine_ring_hex.png
    :align: center

    Nine-ring, third-core, flats up hexagonal lattice map.


Ten-Ring, Third-Core Hex Maps
"""""""""""""""""""""""""""""
TODO

.. figure:: /.static/lattice_map/ten_ring_hex.png
    :align: center

    Ten-ring, third-core, flats up hexagonal lattice map.


Eleven-Ring, Third-Core Hex Maps
""""""""""""""""""""""""""""""""
TODO

.. figure:: /.static/lattice_map/eleven_ring_hex.png
    :align: center

    Eleven-ring, third-core, flats up hexagonal lattice map.
