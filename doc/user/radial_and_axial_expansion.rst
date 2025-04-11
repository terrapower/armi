******************************************
Radial and Axial Expansion and Contraction
******************************************

ARMI natively supports linear expansion in both the radial and axial dimensions. These expansion types function independently of one another and each have their own set of underlying assumptions and use-cases. The remainder of this section is described as follows: in Section :ref:`thermalExpansion` the methodology used for thermal expansion within ARMI is described.

.. _thermalExpansion:

Thermal Expansion
=================
ARMI treats thermal expansion as a linear phenomena using the standard linear expansion relationship,

.. math::
    \frac{\Delta L}{L_0} = \alpha(T) \Delta T,
    :label: linearExp

where, :math:`\Delta L` and :math:`\Delta T` are the change in length and temperature from the reference state, respectively, and :math:`\alpha` is the thermal expansion coefficient relative to :math:`T_0`. Expanding and rearranging Equation :eq:`linearExp`, we can obtain an expression for the new length, :math:`L_1`,

.. math::
    L_1 = L_0\left[1 + \alpha(T_1)\left(T_1 - T_0\right) \right].
    :label: newLength

Given Equation :eq:`linearExp`, we can create expressions for the change in length between our "hot" temperature (Equation :eq:`hotExp`)

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

These are used within ARMI to enable thermal expansion and contraction with a temperature not equal to the reference temperature, :math:`T_0`. By taking the difference between Equation :eq:`hotExp` and :eq:`nonRefExp`, we can obtain an expression relating the change in length, :math:`L_h - L_c`, to the reference length, :math:`L_0`,

.. math::
    \begin{aligned}
        \frac{L_h - L_0}{L_0} - \frac{L_c - L_0}{L_0} &= \frac{L_h}{L_0} - 1 - \frac{L_c}{L_0} + 1, \\
        &= \frac{L_h - L_c}{L_0}.
    \end{aligned}
    :label: diffHotNonRef

Using Equations :eq:`diffHotNonRef` and :eq:`nonRefExp`, we can obtain an expression for the change in length, :math:`L_h - L_c`, relative to the non-reference temperature,

.. math::
    \frac{L_h - L_c}{L_c} &= \frac{L_h - L_c}{L_0} \frac{L_0}{L_c}\\
    &= \left( \frac{L_h}{L_0} - \frac{L_c}{L_0} \right) \left( 1 + \alpha(T_c)\left(T_c - T_0\right) \right)^{-1}.
    :label: expNewRelative

Using Equations :eq:`hotExp` and :eq:`nonRefExp`, we can simplify Equation :eq:`expNewRelative` to find,

.. math::
    \frac{L_h - L_c}{L_c} = \frac{\alpha(T_h) \left(T_h - T_0\right) - \alpha(T_c)\left(T_c - T_0\right)}{1 + \alpha(T_c)\left(T_c - T_0\right)}.
    :label: linearExpansionFactor

Equation :eq:`linearExpansionFactor` is the expression used by ARMI in :py:meth:`linearExpansionFactor <armi.materials.material.Material.linearExpansionFactor>`.

.. note::
    :py:meth:`linearExpansionPercent
    <armi.materials.material.Material.linearExpansionPercent>` returns
    :math:`\frac{L - L_0}{L_0}` in %.

Given that thermal expansion (or contraction) of solid components must conserve mass throughout the system, the density of the component is adjusted as a function of temperature based on the following equation, assuming isotropic thermal expansion.

.. math::
    \rho(T_h) \frac{kg}{m^3} = \frac{\rho(T_0) \frac{kg}{m^3}}{1 + \frac{\Delta L}{L_0}} = \frac{\rho(T_0) \frac{kg}{m^3}}{(1 + \alpha_m (T_h) (T_h - T_0))^3}

where, :math:`\rho(T_h)` is the component density at the given temperature :math:`T_h`, :math:`\rho(T_0)` is the component density at the reference temperature :math:`T_0`, and :math:`\alpha(T_h)` is the mean coefficient of thermal expansion at the specified temperature :math:`T_h` relative to the material's reference temperature.

An update to mass densities is applied for all solid components given the assumption of isotropic thermal expansion, whereas the masses of non-solid components (e.g., fluids/gases) are allowed to change within the reactor core model based on the solid component volume changes. This allows for the flowing coolant area and mass to change for system temperature conditions.

Implementation Discussion and Example of Radial and Axial Thermal Expansion
===========================================================================

This section provides an example thermal expansion calculation for a simple cylindrical component in the following figure:

.. figure:: /.static/axial_expansion_simple.png

    Illustration of Simple Cylinder Radial and Axial Thermal Expansion

from a reference temperature of 20°C to 1000°C with example material properties and dimensions as shown in this table:

.. list-table:: Example Component Properties for Thermal Expansion
   :widths: 50 50
   :header-rows: 1

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

This process is performed iteratively for each component as temperatures are modified. One important note about the thermal expansion implementation is that components are constrained within blocks, so the height of the component is determined by the height of its parent block. What follows is a simple example illustrating the behavior of thermal expansion for a block containing a single component.

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
     - 0.982 :math:`cm^3`
     -  0.988 :math:`cm^3`
   * - Density
     - 1.0 g/cc
     - 0.994 g/cc
   * - Mass
     - 0.982 g
     - 0.982 g

.. math::
    \vec{r} = 0.25 cm \cdot (1 + (2 x 10^-6 \frac{1}{°C})(1000°C − 20°C)) = 0.251 cm

.. math::
    \vec{r} = 5.0 cm \cdot (1 + (2 x 10^-6 \frac{1}{°C})(1000°C − 20°C)) = 5.01 cm

.. math::
    \vec{V} = \pi \cdot (0.251 cm)^2 \cdot 5.01 cm = 0.988 cm^3

.. math::
    \vec{\rho} = \frac{1.0 \frac{g}{cc}}{(1 + (2 x 10^-6 \frac{1}{°C})(1000°C − 20°C))} = 0.994 \frac{g}{cc}

.. math::
    \vec{m} = 0.994 \frac{g}{cc} \cdot 0.988 cm^3 = 0.982 g

When two or more components exist within the block, the overall height change of the block is driven by a target component (e.g., fuel), where the target is selected to ensure some parameter of interest (e.g., linear heat generation rate) is evaluate correctly. In this case, the height of the block containing the multiple components is only expanded to meet the axial expansion of the target component and the remaining solid components have their densities further adjusted to preserve mass within the assembly.

Radial thermal expansion occurs for each component in the block and mechanical contact of components is not accounted for, meaning that the radial expansion of one component is independent from the radial expansion of the others. Solid components are linked to gas/fluid components (i.e., sodium bond, helium) and the gas/fluid area is allowed to expand and contract with changes in component temperatures. Alternatively, the axial thermal expansion of a block within an assembly does influence other block positions. Blocks are dynamically linked in the axial direction. So, while axial thermal expansion evaluations of each block are treated independently, the axial mesh points are updated to account for the physical material displacements across the entire assembly length

The following two tables provide illustrations of the axial thermal expansion process for an example core assembly. In this example there are four main block types defined: Shield, Fuel, Plenum, and Dummy.

.. figure:: /.static/axial_expansion_components.png

    Illustration of Components for Axial Thermal Expansion Process

.. figure:: /.static/axial_expansion_process.png

    Simplified Illustration of Axial Thermal Expansion Process for a Core Assembly

The target components for each block type are provided in the following table:

.. list-table:: : Example Assignment of Target Components within Blocks
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

The axial thermal expansion algorithm is applied in four (4) main steps:

* Step 1: Expand the axial dimensions of target components and non-target components within each block independently.
* Step 2: Align blocks axially such that common components have consistent alignments (e.g., overlapping radial dimensions).
* Step 3: Assign the block lower and upper elevations to account for the thermal expansion of blocks below each block.
  * Step 3a: Create new mesh lines that track the target component.
* Step 4: Adjust the “Dummy” block located at the top of the core assembly to maintain a consistent core assembly height before and after axial thermal expansion is applied.
