******************************************
Radial and Axial Expansion and Contraction
******************************************

ARMI natively supports linear expansion in both the radial and axial dimensions. These expansion
types function independently of one another and each have their own set of underlying assumptions
and use-cases. Radial expansion happens by default but axial expansion only occurss if the setting
``inputHeightsConsideredHot`` is set to ``False``.

.. _thermalExpansion:

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
system, the density of the component is adjusted as a function of temperature based on the following
equation, assuming isotropic thermal expansion.

.. math::
    \rho(T_h) = \frac{\rho(T_0)}{\left(1 + \frac{\Delta L}{L_0}\right)^3} = \frac{\rho(T_0)}{\left(1 + \alpha_m (T_h) (T_h - T_0)\right)^3}

where, :math:`\rho(T_h)` is the component density in :math:`\frac{kg}{m^3}` at the given temperature
:math:`T_h`, :math:`\rho(T_0)` is the component density in :math:`\frac{kg}{m^3}` at the reference
temperature :math:`T_0`, and :math:`\alpha(T_h)` is the mean coefficient of thermal expansion at the
specified temperature :math:`T_h` relative to the material's reference temperature.

An update to mass densities is applied for all solid components given the assumption of isotropic
thermal expansion.  Here we assume the masses of non-solid components (e.g., fluids or gases) are
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
     - 2 x 10-6 1/°C

The figure below illustrates the thermal expansion phenomena in both the radial and axial
directions.

.. figure:: /.static/axial_expansion_simple.png
   :name: therm_exp_illustration
   :scale: 50%

    Illustration of radial (isotropic) and axial thermal expansion for a cylinder in ARMI.

Thermal expansion calculations are performed for each component in the ARMI reactor data model as
component temperatures change. Since components are constrained within blocks, the height of
components are determined by the height of their parent block. The equations below for
``hot_radius`` through ``hot_density`` illustrate how the radius, height, volume, density, and mass
are updated for a component during thermal expansion, respectively.

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

    h(T_h) = 5.0 \left(1 + \left((2\times 10^{-6}(1000 − 20)\right)\right) = 5.01 cm

.. math::
   :name: hot_volume
   
    V(T_h) = \pi (0.251)^2 5.01 = 0.988 cm^3

.. math::
   :name: hot_density

    \rho(T_h) = \frac{1.0}{\left(1 + 2\times 10^{-6}(1000 − 20)\right)} = 0.994 \frac{g}{cc}

.. math::
   :name: hot_mass

    m(T_h) = 0.994 \times 0.988 = 0.982 g

Radial thermal expansion occurs for each component in a given block. Mechanical contact between
components is not accounted for, meaning that the radial expansion of one Component is independent
from the radial expansion of the others. Solid components may be linked to gas/fluid components
(i.e., sodium bond, helium) and the gas/fluid area is allowed to expand and contract with changes in
Component temperatures. It is worth noting that void components are allowed to have negative areas
in cases where the expansion of two solid components overlap each other.

When two or more components exist within the Block, the overall height change of the Block is driven
by an axial expansion "target Component" (e.g., fuel). Alternatively, the axial thermal expansion of
components within a Block do influence the positions of components in neighboring blocks for a given
Assembly. So, while axial thermal expansion evaluations of each Block are treated independently, the
axial mesh points are updated to account for the physical material displacements across the entire
assembly length.

The following two tables provide illustrations of the axial thermal expansion process for an example
core assembly. In this example there are four main block types defined: Shield, Fuel, Plenum, and
Dummy.

.. figure:: /.static/axial_expansion_components.png
   :scale: 60%

    Illustration of Components for Axial Thermal Expansion Process

.. figure:: /.static/axial_expansion_process.png

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

# Expand the axial dimensions of target component and non-target components within each
  block independently. 
# Align blocks axially such that common components have consistent alignments (e.g.,
  overlapping radial dimensions).
# Assign the block lower and upper elevations to account for the thermal expansion of blocks
  below each block.

   #  Create new mesh lines that track the target component.

# Adjust the "Dummy" block located at the top of the assembly to maintain a consistent
  core-wide assembly height before and after axial thermal expansion is applied.


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
#. "Dummy Blocks" are intended to only contain fluid (generally cooling fluid), do not contain solid
   components, and therefore do not have an axial expansion target component.


Mass Conservation
-----------------
TODO
