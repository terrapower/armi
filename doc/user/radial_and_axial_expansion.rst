******************************************
Radial and Axial Expansion and Contraction
******************************************

ARMI natively supports linear expansion in both the radial and axial dimensions for pin-type reactors. These expansion
types function independently of one another and each have their own set of underlying assumptions and use-cases. Radial
expansion happens by default but there are several settings that control axial expansion:

* ``inputHeightsConsideredHot`` - Indicates whether blueprints heights have already been thermally expanded. If ``False``, ARMI will expand components at BOL consistent with provided temperatures.
* ``assemFlagsToSkipAxialExpansion`` - Assemblies with a flag in this list will not be axially expanded.
* ``detailedAxialExpansion`` - Allow each assembly to expand independently. This will result in a non-uniform mesh.

If they happen, ARMI runs radial and axial expansion when objects are created from blueprints. That is, when the reactor is
created from blueprints at BOL, these calculations are performed. But also at BOC if new assemblies are added to the
core, then expansion will happen again when the assembly object is created from blueprints.


Thermal Expansion
=================
ARMI treats thermal expansion as a linear phenomena using a standard linear expansion relationship,

.. math::
    \frac{\Delta L}{L_0} = \alpha(T) \Delta T,
    :label: linearExp

where, :math:`\Delta L` and :math:`\Delta T` are the change in length and temperature from the
reference state, respectively, and :math:`\alpha` is the thermal expansion coefficient relative to
:math:`T_0`. Expanding and rearranging Equation :eq:`linearExp`, we can obtain an expression for the
new length, :math:`L_1`,

.. math::
    L_1 = L_0\left[1 + \alpha(T_1)\left(T_1 - T_0\right) \right].
    :label: newLength

Given Equation :eq:`linearExp`, we can create expressions for the change in length between our "hot"
temperature (Equation :eq:`hotExp`)

.. math::
    \begin{aligned}
        \frac{L_h - L_0}{L_0} &= \alpha(T_h)\left(T_h - T_0\right),\\
        \frac{L_h}{L_0} &= 1 + \alpha(T_h)\left(T_h - T_0\right).
    \end{aligned}
    :label: hotExp

and "non-reference" temperature, :math:`T_c` (Equation :eq:`nonRefExp`),

.. math::
    \begin{aligned}
        \frac{L_c - L_0}{L_0} &= \alpha(T_c)\left(T_c - T_0\right),\\
        \frac{L_c}{L_0} &= 1 + \alpha(T_c)\left(T_c - T_0\right).
    \end{aligned}
    :label: nonRefExp

These are used within ARMI to enable thermal expansion and contraction with a temperature not equal
to the reference temperature, :math:`T_0`. By taking the difference between Equation :eq:`hotExp`
and :eq:`nonRefExp`, we can obtain an expression relating the change in length, :math:`L_h - L_c`,
to the reference length, :math:`L_0`,

.. math::
    \begin{aligned}
        \frac{L_h - L_0}{L_0} - \frac{L_c - L_0}{L_0} &= \frac{L_h}{L_0} - 1 - \frac{L_c}{L_0} + 1, \\
        &= \frac{L_h - L_c}{L_0}.
    \end{aligned}
    :label: diffHotNonRef

Using Equations :eq:`diffHotNonRef` and :eq:`nonRefExp`, we can obtain an expression for the change
in length, :math:`L_h - L_c`, relative to the non-reference temperature,

.. math::
    \frac{L_h - L_c}{L_c} &= \frac{L_h - L_c}{L_0} \frac{L_0}{L_c}\\
    &= \left( \frac{L_h}{L_0} - \frac{L_c}{L_0} \right) \left( 1 + \alpha(T_c)\left(T_c - T_0\right) \right)^{-1}.
    :label: expNewRelative

Using Equations :eq:`hotExp` and :eq:`nonRefExp`, we can simplify Equation :eq:`expNewRelative` to find,

.. math::
    \frac{L_h - L_c}{L_c} = \frac{\alpha(T_h) \left(T_h - T_0\right) - \alpha(T_c)\left(T_c - T_0\right)}{1 + \alpha(T_c)\left(T_c - T_0\right)}.
    :label: linearExpansionFactor

Equation :eq:`linearExpansionFactor` is the expression used by ARMI in
:py:meth:`linearExpansionFactor <armi.materials.material.Material.linearExpansionFactor>`.

.. note::
    :py:meth:`linearExpansionPercent
    <armi.materials.material.Material.linearExpansionPercent>` returns
    :math:`\frac{L - L_0}{L_0}` in %.

Given that thermal expansion (or contraction) of solid components must conserve mass throughout the
system, the density of the component is adjusted as a function of temperature based on Equation
:eq:`hot_density_general`, assuming isotropic thermal expansion.

.. math::
    \rho(T_h) = \frac{\rho(T_0)}{\left(1 + \frac{\Delta L}{L_0}\right)^3} = \frac{\rho(T_0)}{\left(1 + \alpha_m (T_h) (T_h - T_0)\right)^3}
    :label: hot_density_general

where, :math:`\rho(T_h)` is the component density in :math:`\frac{kg}{m^3}` at the given temperature
:math:`T_h`, :math:`\rho(T_0)` is the component density in :math:`\frac{kg}{m^3}` at the reference
temperature :math:`T_0`, and :math:`\alpha(T_h)` is the mean coefficient of thermal expansion at the
specified temperature :math:`T_h` relative to the material's reference temperature.

An update to mass densities is applied for all solid components given the assumption of isotropic
thermal expansion. Here we assume the masses of non-solid components (e.g., fluids or gases) are
allowed to change within the reactor core model based on changes to solid volume changes. For
instance, if solids change volume due to temperature changes, there is a change in the amount of
volume left for fluid components.

Implementation Discussion and Example of Radial and Axial Thermal Expansion
===========================================================================
This section provides an example thermal expansion calculation for a simple cylindrical component
from a reference temperature of 20°C to 1000°C with example material properties and dimensions as
shown in the table below.

.. list-table:: Example Component Properties for Thermal Expansion
   :widths: 50 50
   :header-rows: 1
   :name: thermal_exp_comp_properties

   * - Property
     - Example
   * - Material
     - Steel
   * - Radius
     - 0.25 cm
   * - Height
     - 5.0 cm
   * - Reference Temperature
     - 20°C
   * - Density
     - 1.0 g/cc
   * - Mean Coefficient Thermal Expansion
     - :math:`2\times 10^{-6}` 1/°C

The figure below illustrates the thermal expansion phenomena in both the radial and axial
directions.

.. figure:: /.static/axial_expansion_simple.png

    Illustration of radial and axial thermal expansion for a cylinder in ARMI.

Thermal expansion calculations are performed for each component in the ARMI reactor data model as
component temperatures change. Since components are constrained within blocks, the height of
components are determined by the height of their parent block. Equations :eq:`hot_radius` through
:eq:`hot_density` illustrate how the radius, height, volume, density, and mass are updated for
a Component during thermal expansion, respectively.

.. list-table:: Example Calculation of Radial and Axial Thermal Expansion for a Cylindrical Component
   :widths: 33 33 33
   :header-rows: 1

   * - Component Temperature
     - 20°C
     - 1000°C
   * - Radius
     - 0.25 cm
     - 0.251 cm
   * - Height
     - 5.0 cm
     - 5.01 cm
   * - Volume
     - 0.982 cc
     - 0.988 cc
   * - Density
     - 1.0 g/cc
     - 0.994 g/cc
   * - Mass
     - 0.982 g
     - 0.982 g

.. math::
   :name: hot_radius

    r(T_h) = 0.25 \left(1 + \left(2\times 10^{-6}(1000 − 20)\right)\right) = 0.251 cm

.. math::
   :name: hot_height

    h(T_h) = 5.0 \left(1 + \left(2\times 10^{-6}(1000 − 20)\right)\right) = 5.01 cm

.. math::
   :name: hot_volume

    V(T_h) = \pi (0.251)^2 5.01 = 0.988 cm^3

.. math::
   :name: hot_density

    \rho(T_h) = \frac{1.0}{\left(1 + 2\times 10^{-6}(1000 − 20)\right)^3} = 0.994 \frac{g}{cc}

.. math::
   :name: hot_mass

    m(T_h) = 0.994 \times 0.988 = 0.982 g

Radial thermal expansion occurs for each Component in a given Block. Mechanical contact between
components is not accounted for, meaning that the radial expansion of one Component is independent
from the radial expansion of the others. Solid components may be radially linked to gas/fluid components
(i.e., sodium bond, helium) and the gas/fluid area is allowed to radially expand and contract with changes in
Component temperature. It is worth noting that void components are allowed to have negative areas
in cases where the expansion of two solid components overlap each other.

Axial thermal expansion occurs for each solid Component with a given Block. Axial mechanical contact between components
is accounted for as the expansion or contraction of a Component affects the positions of components in mechanical
contact in axially neighboring blocks. The logic for determining Component-to-Component mechanical contact is
described in Section :ref:`axialLink`. When two or more solid components exist within the Block, the change in Block
height is driven by an axial expansion "target Component" (e.g., fuel). The logic for determining the axial
expansion "target Component" is provided in Section :ref:`axialExpTargetComp`.

Figures :ref:`components_for_exp_illustration` and :ref:`axial_exp_illustration` provide illustrations of the axial
thermal expansion process for an example core assembly. In this example there are four main block types defined: Shield,
Fuel, Plenum, and Dummy.

.. note::

  The "dummy" Block is necessary to maintain a consistent core-wide assembly height as this is a common necessity for
  physics solvers utilizing discrete-ordinates discretization methods.

.. figure:: /.static/axial_expansion_components.png
  :name: components_for_exp_illustration

  Illustration of Components for Axial Thermal Expansion Process

.. figure:: /.static/axial_expansion_process.png
  :name: axial_exp_illustration

  Simplified Illustration of Axial Thermal Expansion Process for a Core Assembly

The target components for each Block type are provided in the following table:

.. list-table:: Example Assignment of Target Components within Blocks
   :widths: 50 50
   :header-rows: 1

   * - Block
     - Target Component
   * - Shield
     - Shield
   * - Fuel
     - Fuel
   * - Plenum
     - Clad
   * - Dummy
     - N/A

The axial thermal expansion algorithm is applied in four steps:

#. Expand the axial dimensions of each solid Component within each block independently.
#. Align blocks axially such that axially-linked components have consistent alignments (e.g.,
   overlapping radial dimensions).
#. Assign the Block lower and upper elevations to account for the thermal expansion of blocks
   below each Block.

   * Create new mesh lines (i.e., Block bounds) that track the target component.

#. Adjust the "dummy" Block located at the top of the assembly to maintain a consistent
   core-wide assembly height before and after axial thermal expansion is applied.

.. _axialLink:

Component-to-Component Axial Linking
------------------------------------
For components to be in mechanical contact, and therefore axially linked, they need to meet the following criteria:

#. The same Component class. E.g., both are :py:class:`basicShapes.Circle`.
#. Both solid materials.

If those are met, then geometric overlap may be checked if the following are met:

#. The components are not :py:class:`components.UnshapedComponent`
#. The components have the same multiplicity
#. Or, they share the same grid indices, as specified by a Block :py:class:`<grid> grids.locations.MultiIndexLocation`.

Finally, geometric overlap is established if the biggest inner bounding diameter of the components is less than the
smallest outer bounding diameter of the components.

Limitations
^^^^^^^^^^^

A current limitation of the axial linking logic is that multiple Components may not be linked to a single Component.
E.g., consider the following:

#. A solid cylinder with an outer diameter of 1.0 cm.
#. Above, a solid cylinder wrapped with an annular cylinder (separate ARMI components) each with the following dimensions:

  * Solid cylinder with an outer diameter of 0.5 cm.
  * Annulus with inner diameter of 0.5 cm and outer diameter of 0.75 cm.

For the above example, in reality, the annulus wrapped pin (two separate ARMI components) would be affected by any
changes in height from the solid cylinder. However, this set up is not allowed by the current implementation and will
raise a ``RuntimeError``.

A second limitation of the component linking implementation involves the Block grid based approach. When Block grids are
used to specify a pin lattice, the Block-grid should be used throughout the Assembly definition; i.e., a mixture of
the Block-grid and multiplicity assignment should not be used (and will likely produce unexpected results and may even
fail). For example, in the following partial blueprint definition, in reality, each shield pin should be in mechanical
contact with the fuel pins. However, since there is a mixture of mulitiplicity and Block-grid approaches, they are
assumed to be not-linked. In order to ensure properly linking, ``block_fuel_axial_shield`` needs to be redefined with
the Block-grid based approach.

.. code-block:: yaml

  axial shield: &block_fuel_axial_shield
    shield:
      shape: Circle
      material: HT9
      Tinput: 25.0
      Thot: 600.0
      id: 0.0
      mult: 169.0
      od: 0.86602

  fuel multiPin: &block_fuel_multiPin
    grid name: twoPin
    fuel 1: &component_fuelmultiPin
      shape: Circle
      material: UZr
      Tinput: 25.0
      Thot: 600.0
      id: 0.0
      od: 0.86602
      latticeIDs: [1]
    fuel 2:
      <<: *component_fuelmultiPin
      latticeIDs: [2]

The following incorporates the fix for ``block_fuel_axial_shield`` and illustrates another potentially undesirable
situation where unexpected results or runtime failure may occur. Here a plenum block is added above the fuel and while
it does utilize a Block-grid, ``clad`` will not be axially linked to either the ``fuel 1`` or ``fuel 2`` components
below it. This is because the ``clad`` and ``fuel*`` components have different grids via their ``grid.spatialLocator``
values. As in the previous example, similar unexpected behavior would also occur if a multiplicity-based definition
were used for ``clad``.

.. code-block:: yaml

  axial shield multiPin: &block_fuel_multiPin_axial_shield
    grid name: twoPin
    shield 1: &component_shield_shield1
      shape: Circle
      material: HT9
      Tinput: 25.0
      Thot: 600.0
      id: 0.0
      od: 0.8
      latticeIDs: [1]
    shield 2:
      <<: *component_shield_shield1
      latticeIDs: [2]

  fuel multiPin: &block_fuel_multiPin
    grid name: twoPin
    fuel 1: &component_fuelmultiPin
      shape: Circle
      material: UZr
      Tinput: 25.0
      Thot: 600.0
      id: 0.0
      od: 0.8
      latticeIDs: [1]
    fuel 2:
      <<: *component_fuelmultiPin
      latticeIDs: [2]

  plenum 2pin: &block_plenum_multiPin
    grid name: twoPin
    clad:
      shape: Circle
      material: Void
      Tinput: 25.0
      Thot: 600.0
      id: 0.9
      od: 1.0
      latticeIDs: [1,2]

To resolve this potential issue, ``block_plenum_multiPin`` should be replaced with the following definition. See the
``multi pin fuel`` assembly definition within ``armi/tests/detailedAxialExpansion/refSmallReactorBase.yaml`` for a
complete example.

.. code-block:: yaml

    plenum 2pin: &block_plenum_multiPin
    grid name: twoPin
    clad 1: &component_plenummultiPin_clad1
        shape: Circle
        material: Void
        Tinput: 25.0
        Thot: 600.0
        id: 0.9
        od: 1.0
        latticeIDs: [1]
    clad 2:
      <<: *component_plenummultiPin_clad1
        latticeIDs: [2]


.. _axialExpTargetComp:

Target Component Logic
----------------------
When two or more solid components exist within a Block, the overall height change of the Block is
driven by an "axial expansion target component" (e.g., fuel). This Component may either be inferred
from the flags prescribed in the blueprints or manually set using the ``axial expansion target
component`` block blueprint attribute. The following logic is used to infer the target component:

#. Search Component flags for neutronically important components. These are defined in
   :py:data:`expansionData.TARGET_FLAGS_IN_PREFERRED_ORDER`.
#. Compare the Block and Component flags. If a Block and Component contain the same flags, that
   Component is selected as the axial expansion target Component.
#. If a Block has :py:data:`flags.flags.PLENUM` or :py:data:`flags.flags.ACLP`, the
   :py:data:`flags.flags.CLAD` Component is hard-coded to be the axial expansion target component.
   If one does not exist, an error is raised.
#. "Dummy Blocks" are intended to only contain fluid (generally coolant fluid), and do not contain
   solid components, and therefore do not have an axial expansion target component.


Mass Conservation
-----------------
Due to the fact that all components within a Block are the same height, the conservation of
mass post-axial expansion is not trivial. The ``axial expansion target component`` plays a critical role in the
conservation of mass. For pinned-blocks, this is typically chosen to be the most neutronically important Component;
e.g., in a fuel Block this is typically the fuel Component. Generally speaking, components which are not the axial
expansion target will exhibit non-conservation on the Block-level as mass is redistributed across the axially-
neighboring blocks; this is discussed in more detail in :numref:`mass_redistribution`. However, the mass of all
solid components are designed to be conserved at the assembly-level if the following are met for a given assembly
design.

#. Axial continuity of like-objects. E.g., pins, clad, etc.
#. Components that may expand at different rates axially terminate in unique blocks

   * E.g., the clad extends above the termination of the fuel and the radial duct encasing an
     assembly extends past the termination of the clad.

#. The top-most Block must be a "dummy Block" containing fluid (typically coolant).

See `armi.tests.detailedAxialExpansion
<https://github.com/terrapower/armi/tree/main/armi/tests/detailedAxialExpansion>`_ for an example
blueprint which satisfy the above requirements.

.. _mass_redistribution:

Block-Level Mass Redistribution
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Figure :ref:`mass_redistribution_illustration` illustrates the mass redistribution process for axial expansion in ARMI given
a uniform axial expansion of 10% for fuel components.

.. figure:: /.static/mass_redistribution_illustration.png
  :name: mass_redistribution_illustration

  Illustration of mass redistribution for axial expansion in ARMI.

The redistribution process can be written mathematically. In Figure :ref:`mass_redistribution_illustration`, consider the
exchange of mass between the clad in Block 0 and Block 1,

.. math::
	:name: cMass0

	\hat{c}_{0,m} = c_{0,m} + 0.1c_{1,m}

.. math::
  :name: cMass1

	\hat{c}_{1,m} = 0.9c_{1,m},

where :math:`c_{0/1,m}` represents the clad mass in Block 0/1 prior to redistribution and :math:`\hat{c}_{0/1,m}`
represents the clad mass in Block 0/1 after redistribution, respectively. Given :math:`\hat{c}_{0,m}` and
:math:`\hat{c}_{1,m}`, the post-mass redistribution number densities, :math:`\hat{N}_{i,0/1}`, where the subscript
:math:`i,0/1` represents isotope :math:`i` for Block 0/1, need to be computed.

Computing :math:`\hat{N}_{i,1}` satisfying :math:`\hat{c}_{1,m}` can be found by scaling the pre-redistribution number
densities by the expansion factor. However, in ARMI, the number densities are not changed and the mass is decreased
through the reduction in the height of the parent Block.

.. note::

  Recall, component mass in ARMI is calculated as the product of the mass density of the component, the area of the
  component, and the height of the block. The mass of components can be tuned through either of these three parameters.

Computing :math:`\hat{N}_{i,0}` is non-trivial as, in general, :math:`c_0` and :math:`c_1` are at different
temperatures. Consider,

.. math::
  :name: newCMass

  \hat{c}_{0,m} &= c_{0,m} + 0.1c_{1,m},\\
  &= \sum_{i=0}^N N_{i,0} A_0(T_0) h_0 + 0.1 \sum_{i=0}^N N_{i,1} A_1(T_1) h_1,\\
  \sum_{i=0}^N \hat{N}_{i,0} A_0(\hat{T}_0) \hat{h}_0 &= \sum_{i=0}^N \left( N_{i,0} A_0(T_0) h_0 + 0.1 N_{i,1} A_1(T_1) h_1 \right),

where,

* :math:`A_{0/1}(T_{0/1})` is the area of component 0/1 at temperature 0/1,
* :math:`h_{0/1}` is the height of component 0/1,
* :math:`\hat{\square}` represents post-redistribution values.

For a given non-target component, we can calculate an expected difference in z-elevation between it and the
``axial expansion target component``,

.. math::

  \delta = b_{\text{ztop}} - c^*_{\text{ztop}}.

.. note::

  #. Recall, axial block bounds are determined by the ``axial expansion target component`` so the top z-elevation ``ztop``
     for the block is the same as the top of the ``axial expansion target component``.
  #. In the axial expansion module, components are given z-elevation attributes. This information is not serialized to
     the database.

This value can then be used to calculate the height of the Component post-expansion,

.. math::

  \hat{h}_0 = h_0 + \delta.

With this height known, there are two unknowns in Equation :eq:`newCMass`, :math:`\hat{T}_0` and :math:`\hat{N}_{i,0}`.

The post-redistribution number densities, :math:`\hat{N}_{i,0}`, are solved by using the expected post-redistribution
mass of each isotope and component volume. The mass of isotope, :math:`i`, for block 0/1 is calculated as follows,

.. math::

  m_{i,0/1} = N_{i,0/1} V_{0/1} \alpha_i \chi,

where :math:`\alpha_i` is the atomic weight for isotope, :math:`i`, and :math:`\chi` is a constant scaling from moles per
cc to atoms per barn per cm. Given the expected mass for isotope, :math:`i`, the post redistribution number density is
calculated as follows,

.. math::

  \hat{N_{i,0}} = \frac{\left( m_{i,0} + m_{i,1} \right) * \chi}{ \left(A_1(T_1) H_1 + A_2(T_2)\delta\right) \eta_i}.

The post redistribution temperature, :math:`\hat{T}_0`, can be computed by minimizing the residual of difference between
the area of the Component and its expected area,

.. math::
  :name: newTemp

  A_0(\hat{T}_0) \left( H_1 + \delta \right) &= A_1(T_1) H_1 + A_2(T_2)\delta,\\
  A_0(\hat{T}_0) &= \frac{A_1(T_1) H_1 + A_2(T_2)\delta}{H_1 + \delta}.

Equation :eq:`newTemp` is solved using Brent's method within ``scipy`` where the bounds of the solve are the temperatures of
the two components exchanging mass, :math:`T_0` and :math:`T_1`.




.. This :math:`\delta` value enables the calculation of an expected volume for :math:`\hat{c}_0`,

.. .. math::

..   \hat{V}_0 = A_0(T_0) h_0 + A_1(T_1) \delta.






..  Written out Equation \ref{eq::cMass0-complex} becomes,

.. \begin{align}
.. 	c_{0,m} &= c_{0,m} + 0.3c_{1,m},\\[5pt]
.. 	&= \sum_{i=0}^N \frac{n^i_{c,0}}{\gamma_{c,0}} A_{c,0} b_{0,h} + 0.3 \sum_{i=0}^N \frac{n^i_{c,1}}{\gamma_{c,1}} A_{c,1} b_{1,h}.
.. \end{align}


.. Given Equation \ref{eq::cMass0-complex}, we can compute the expected total mass for $c_0$,
.. \begin{equation}
.. 	\hat{c}_{0,m} = c_{0,m} + 0.3c_{1,m}.
.. \end{equation}
.. Given $\hat{c}_{0,m}$, we can compute the per isotope number density required to recover $\hat{c}_{0,m}$,
.. \begin{equation}
.. 	\hat{N}^i = \frac{\hat{C}^i_{0,m}}{\hat{V}\sfrac{A^i}{N_A}}, \quad \forall i\in N
.. \end{equation}
.. where
.. \begin{itemize}
.. 	\item $\hat{N}^i$ is the number density for isotope, $i$
.. 	\item $\hat{V}$ is the volume of the new block post redistribution
.. 	\item $A^i$ is the atomic mass of isotope, $i$
.. 	\item $N_A$ is Avodadro's number
.. 	\item $N$ is the total number isotopes for a given material
.. \end{itemize}