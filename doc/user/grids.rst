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

Example grid definitions are shown below

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


There is another kind of lattice map that ARMI supports; third-core lattice maps. These are a special case of hexagonal
lattice maps, where instead of drawing out the entire lattice (as above) only one third of the hexagonal lattice is
drawn.

This is a common practice in modeling hexagonal reactor cores. To speed up a model run, for a quick study, only one-
third of the reactor core is fully modeled, and boundary conditions are set to model this as if it were part of a full
reactor core. This only works if the reactor core is exactly symmetric of course.

While this may be a niche case, it is fully supported in ARMI lattice maps, and elsewhere. The only tricky point is that
it is not always obvious how to draw the ASCII map to represent these third-core hex grids. To help with that, below are
examples of third-core hex grids shown from two rings to eleven. So if you need to make such a lattice map yourself, you
should be able to start by copy/pasting the examples below.


Two-Ring, Third-Core Hex Maps
"""""""""""""""""""""""""""""
First, let us start with a very simple case; the two-ring hexagonal lattice map. The YAML ASCII map to draw such a
lattice is shown below

.. code-block:: yaml

    geom: hex
    symmetry: third periodic
    lattice map: |
      A
       B
       C

Figure 3 below shows the third-core map plotted out. Also shown is the full-core plotted to represent what an ARMI
simulation thinks the entire lattice map looks like, based on the third of the core provided in the ASCII art

.. figure:: /.static/lattice_map_two_ring_hex_flats_up.png
    :align: center

    Figure 3: Two-ring, third-core, flats-up hexagonal lattice map.

There is another possibility not shown above in Figure 3. A hexagonal grid can be represented with flats or corners
pointing up on the plot. In ARMI, we represent the "corners up" version by specifying a slight change to the ``geom``
field: ``hex_corners_up`` as opposed to just ``hex``

.. code-block:: yaml

    geom: hex_corners_up
    symmetry: third periodic
    lattice map: |
      A
       B
       C

Figure 4 below is a quick plot of the above, corners up version of the two-ring lattice map

.. figure:: /.static/lattice_map_two_ring_hex_corners_up.png
    :align: center

    Figure 4: Two-ring, third-core, corners-up hexagonal lattice map.

Notice that the two ASCII maps above have three items specified: ``A``, ``B``, and ``C``. The center hex is ``C`` and
the others represent the first ring. The full core map shown has seven elements, the center plus six hexagons in the
first ring. So, to calculate the number of hexagons in the full core map from the number of hexagons shown in a third-
core map there is a simple relation

.. math::
    N_full = 3 * (N_third - 1) + 1

Three-Ring, Third-Core Hex Maps
"""""""""""""""""""""""""""""""
Continuing the logical progression, below is an ASCII map of a three-ring, flats-up, third-core hexagonal lattice

.. code-block:: yaml

    geom: hex
    symmetry: third periodic
    lattice map: |
      D
       E
      A F
       B
      C G

Figure 5 shows third-core and full-core plots of the above YAML

.. figure:: /.static/lattice_map_three_ring_hex_flats_up.png
    :align: center

    Figure 5: Three-ring, third-core, flats-up hexagonal lattice map.

And just one more time, let us show the YAML for the corners-up version of the above three-ring lattice

.. code-block:: yaml

    geom: hex_corners_up
    symmetry: third periodic
    lattice map: |
      D
       E
      A F
       B
      C G

Figure 6 below shows the third-core and full-core plots for the three-ring, corners up lattice

.. figure:: /.static/lattice_map_three_ring_hex_corners_up.png
    :align: center

    Figure 6: Three-ring, third-core, corners-up hexagonal lattice map.


Four-Ring, Third-Core Hex Maps
""""""""""""""""""""""""""""""
From here on out, the examples will only show the "flats-up" versions of the lattice maps and plots, to reduce
duplication.

The four-ring, third-core lattice map is starting to get larger and more complicated than the above examples

.. code-block:: yaml

    geom: hex
    symmetry: third periodic
    lattice map: |
         D
         D   D
           C   D
             C   D
           B   C
             B   D
           A   C 

Figure 7 shows a plot of the above four-ring example. If you are copying from this example, please note that each ring
is filled with a different letter. Hopefully this makes your translation easier.

.. figure:: /.static/lattice_map_four_ring_hex.png
    :align: center

    Figure 7: Four-ring, third-core, flats up hexagonal lattice map.


Five-Ring, Third-Core Hex Maps
""""""""""""""""""""""""""""""
Five-ring and above ASCII maps start to require a special ``-`` character. This does not represent a hexagon, but is
just a piece of cruft to help lay out larger ASCII maps

.. code-block:: yaml

    geom: hex
    symmetry: third periodic
    lattice map: |
         -   E
           E   E
             D   E
           D   D   E
             C   D   E
               C   D
             B   C   E
               B   D
             A   C   E 

Figure 8 shows a plot of the five-ring, third core lattice map above. Again, each hexagonal ring is filled with a
different letter / symbol, to hopefully help make the map more clear.

.. figure:: /.static/lattice_map_five_ring_hex.png
    :align: center

    Figure 8: Five-ring, third-core, flats up hexagonal lattice map.


Six-Ring, Third-Core Hex Maps
"""""""""""""""""""""""""""""
From six-rings and up, the third-core lattice maps start to look a lot more similar to each other. There is a noticable
pattern emerging that should make it easier to add or remove one hexagonal ring from the map

.. code-block:: yaml

    geom: hex
    symmetry: third periodic
    lattice map: |
        -    F
           F   F
         F   E   F
           E   E   F
             D   E   F
           D   D   E   F
             C   D   E
               C   D   F
             B   C   E
               B   D   F
             A   C   E 

Figure 9 shows the six-ring, third-core, flats-up, hexagonal lattice map, with each ring filled with a different symbol
for clarity.

.. figure:: /.static/lattice_map_six_ring_hex.png
    :align: center

    Figure 9: Six-ring, third-core, flats up hexagonal lattice map.


Seven-Ring, Third-Core Hex Maps
"""""""""""""""""""""""""""""""
The seven-ring map looks much like the six-ring map, exact we have added a new ring filled with ``G`` symbols. And from
here on out, even extra ring added to the map requires adding exactly one more ``-`` symbol, to correctly space out the
ASCII letters and make them more readable

.. code-block:: yaml

    geom: hex
    symmetry: third periodic
    lattice map: |
       -     G
       -   G   G
         G   F   G
           F   F   G
         F   E   F   G
           E   E   F   G
             D   E   F   G
           D   D   E   F
             C   D   E   G
               C   D   F
             B   C   E   G
               B   D   F
             A   C   E   G

Figure 10 shows the seven-ring, third-core, flats-up hexagonal lattice map, each ring filled with a different symbol.

.. figure:: /.static/lattice_map_seven_ring_hex.png
    :align: center

    Figure 10: Seven-ring, third-core, flats up hexagonal lattice map.


Eight-Ring, Third-Core Hex Maps
"""""""""""""""""""""""""""""""
TODO

.. code-block:: yaml

    geom: hex
    symmetry: third periodic
    lattice map: |
       -  -   G
       -    G   G
          G   F   G
        G   F   F   G
          F   E   F   G
            E   E   F   G
          E   D   E   F   G
            D   D   E   F   G
              C   D   E   F
            C   C   D   E   G
              B   C   D   F
                B   C   E   G
              G   B   D   F
                G   C   E   G
              A   B   D   F

Figure 11 shows the eight-ring, third-core, flats-up hexagonal lattice map, each ring filled with a different symbol.

.. figure:: /.static/lattice_map_eight_ring_hex.png
    :align: center

    Figure 11: Eight-ring, third-core, flats up hexagonal lattice map.


Nine-Ring, Third-Core Hex Maps
""""""""""""""""""""""""""""""
TODO

.. code-block:: yaml

    geom: hex
    symmetry: third periodic
    lattice map: |
      -  -        G
      -         G   G
      -       G   F   G
            G   F   F   G
              F   E   F   G
            F   E   E   F   G
              E   D   E   F   G
            D   D   E   F   G
          D   C   D   E   F   G
            C   C   D   E   F
              B   C   D   E   G
            B   B   C   D   F
              E   B   C   E   G
                E   B   D   F
              F   E   C   E   G
                F   B   D   F
              A   E   C   E   G

Figure 12 shows the nine-ring, third-core, flats-up hexagonal lattice map, each ring filled with a different symbol.

.. figure:: /.static/lattice_map_nine_ring_hex.png
    :align: center

    Figure 12: Nine-ring, third-core, flats up hexagonal lattice map.


Ten-Ring, Third-Core Hex Maps
"""""""""""""""""""""""""""""
TODO

.. code-block:: yaml

    geom: hex
    symmetry: third periodic
    lattice map: |
      -  -     C
      -  -   C   C
      -    C   B   C
         C   B   B   C
       C   B   A   B   C
         B   A   A   B   C
           A   G   A   B   C
         A   G   G   A   B   C
           G   F   G   A   B   C
             F   F   G   A   B   C
           F   E   F   G   A   B
             E   E   F   G   A   C
               D   E   F   G   B
             D   D   E   F   A   C
               C   D   E   G   B
                 C   D   F   A   C
               B   C   E   G   B
                 B   D   F   A   C
               A   C   E   G   B

Figure 13 shows the 10-ring, third-core, flats-up hexagonal lattice map, each ring filled with a different symbol.

.. figure:: /.static/lattice_map_ten_ring_hex.png
    :align: center

    Figure 13: Ten-ring, third-core, flats up hexagonal lattice map.


Eleven-Ring, Third-Core Hex Maps
""""""""""""""""""""""""""""""""
TODO

.. code-block:: yaml

    geom: hex
    symmetry: third periodic
    lattice map: |
      -  -  -  D
      -  -   D   D
      -    D   C   D
      -  D   C   C   D
       D   C   B   C   D
         C   B   B   C   D
       C   B   A   B   C   D
         B   A   A   B   C   D
           A   G   A   B   C   D
         A   G   G   A   B   C   D
           G   F   G   A   B   C   D
             F   F   G   A   B   C
           F   E   F   G   A   B   D
             E   E   F   G   A   C
               D   E   F   G   B   D
             D   D   E   F   A   C
               C   D   E   G   B   D
                 C   D   F   A   C
               B   C   E   G   B   D
                 B   D   F   A   C
               A   C   E   G   B   D

Figure 14 shows the eleven-ring, third-core, flats-up hexagonal lattice map, each ring filled with a different symbol.

.. figure:: /.static/lattice_map_eleven_ring_hex.png
    :align: center

    Figure 14: Eleven-ring, third-core, flats up hexagonal lattice map.

TODO: Gotta stop somewhere...
