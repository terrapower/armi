*******************************************
Radial and Axial Expansion and Contraction
*******************************************

ARMI natively supports linear expansion in both the radial and axial dimensions. These expansion types function independently of one another and each have their own set of underlying assumptions and use-cases. The remainder of this section is described as follows: in Section :ref:`thermalExpansion` the methodology used for thermal expansion within ARMI is described; in Sections :ref:`radialExpansion` and :ref:`axialExpansion`, we describe the design, limitations, and intended functionality of radial and axial expansion, respectively.

.. _thermalExpansion:

Thermal Expansion
-----------------
Consider the ordinary differential equation describing the change in length from :math:`L_0` to :math:`L_1` due to a change in temperature from :math:`T_0` to :math:`T_1`,

.. math::
    \begin{align}
        \frac{dL}{dT} &= \alpha(T) L,\\[10pt]
        \int_{L_0}^{L_1} \frac{1}{L} dL &= \int_{T_0}^{T_1} \alpha(T) dT,
    \end{align}
    :label: expODE

where, :math:`\alpha(T)`, is the temperature dependent coefficient of thermal expansion (CTE). If the CTE is an instantaneous, or tanget, CTE, Equation :eq:`expODE` can be directly evaluated for the change in length. If the CTE is a mean, or secant CTE, Equation :eq:`expCTE` simplifies to, 

.. math::
    \begin{align}
        \ln{\frac{L_1}{L_0}} &= \alpha(T_1) \left( T_1 - T_0 \right),\\[10pt]
        \frac{L_1}{L_0} &= \exp\left[{\alpha(T_1) \left( T_1 - T_0 \right)}\right].
    \end{align}
    :label: secantThermExp

Given Equation :eq:`secantThermExp`, we can derive an expression for the change in length due to a change in temperature not relative to the reference temperature, :math:`T_0`. By using expressions for the change in length between a "hot" temperature

.. math::
    \frac{L_h}{L_0} = \exp\left[{\alpha(T_h) \left( T_h - T_0 \right)}\right],
    :label: hotExp

and "non-reference" temperature, :math:`T_c`,

.. math::
    \frac{L_c}{L_0} = \exp\left[{\alpha(T_c) \left( T_c - T_0 \right)}\right].
    :label: nonRefExp

we can obtain an expression relating the change in length, :math:`L_h - L_c`, to the non-reference temperature, :math:`T_c`,

.. math::
    \frac{L_h - L_c}{L_c} = \left( \frac{L_h}{L_0} - \frac{L_c}{L_0} \right) \left( \frac{L_0}{L_c} \right).
    :label: diffHotNonRef

Using Equations :eq:`hotExp` and :eq:`nonRefExp`, we can simplify Equation :eq:`diffHotNonRef` to obtain the following,

.. math::
    \begin{align}
        &= \frac{\exp\left[{\alpha(T_h)\left( T_h - T_0 \right)}\right] - \exp\left[{\alpha(T_c)\left( T_c - T_0 \right)}\right]}{\exp\left[{\alpha(T_c)\left( T_c - T_0 \right)}\right]},\\[10pt]
	    & = \frac{\exp\left[{\alpha(T_h)\left( T_h - T_0 \right)}\right]}{\exp\left[{\alpha(T_c)\left( T_c - T_0 \right)}\right]} - 1,\\[10pt]
	    & = \exp\left[{\alpha(T_h)\left(T_h - T_0\right) - \alpha(T_c)\left( T_c - T_0 \right)}\right] - 1.
    \end{align}
    :label: expNewRelative

Equation :eq:`expNewRelative` is the expression used by ARMI in :py:meth:`linearExpansionFactor <armi.materials.material.Material.linearExpansionFactor>`.

.. note::
    :py:meth:`linearExpansionPercent <armi.materials.material.Material.linearExpansionPercent>` returns :math:`\frac{L}{L_0}` in %.

.. _radialExpansion:

Radial Expansion
----------------

.. _axialExpansion:

Axial Expansion
---------------
