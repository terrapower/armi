******************************************
Radial and Axial Expansion and Contraction
******************************************

ARMI natively supports linear expansion in both the radial and axial dimensions. These expansion types function independently of one another and each have their own set of underlying assumptions and use-cases. The remainder of this section is described as follows: in Section :ref:`thermalExpansion` the methodology used for thermal expansion within ARMI is described; in Sections :ref:`radialExpansion` and :ref:`axialExpansion`, we describe the design, limitations, and intended functionality of radial and axial expansion, respectively.

.. _thermalExpansion:

Thermal Expansion
-----------------
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
    \begin{align}
        \frac{L_h - L_0}{L_0} &= \alpha(T_h)\left(T_h - T_0\right),\\
        \frac{L_h}{L_0} &= 1 + \alpha(T_h)\left(T_h - T_0\right).
    \end{align}
    :label: hotExp

and "non-reference" temperature, :math:`T_c` (Equation :eq:`nonRefExp`),

.. math::
    \begin{align}
        \frac{L_c - L_0}{L_0} &= \alpha(T_c)\left(T_c - T_0\right),\\
        \frac{L_c}{L_0} &= 1 + \alpha(T_c)\left(T_c - T_0\right).
    \end{align}
    :label: nonRefExp

These are used within ARMI to enable thermal expansion and contraction with a temperature not equal to the reference temperature, :math:`T_0`. By taking the difference between Equation :eq:`hotExp` and :eq:`nonRefExp`, we can obtain an expression relating the change in length, :math:`L_h - L_c`, to the reference length, :math:`L_0`,

.. math::
    \begin{align}
        \frac{L_h - L_0}{L_0} - \frac{L_c - L_0}{L_0} &= \frac{L_h}{L_0} - 1 - \frac{L_c}{L_0} + 1, \\
        &= \frac{L_h - L_c}{L_0}.
    \end{align}
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
    :py:meth:`linearExpansionPercent <armi.materials.material.Material.linearExpansionPercent>` returns :math:`\frac{L - L_0}{L_0}` in %.

.. _radialExpansion:

Radial Expansion
----------------

.. _axialExpansion:

Axial Expansion
---------------
