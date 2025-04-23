****************
Physics Coupling
****************

Loose Coupling
==============
ARMI supports loose and tight coupling. Loose coupling is interpreted as one-way coupling between physics for a single time node. For example, a power distribution in cycle 0 node 0 is used to calculate a temperature distribution in cycle 0 node 0. This temperature is then used in cycle 0 node 1 to compute new cross sections and a new power distribution. This process repeats itself for the lifetime of the simulation. 

.. graphviz:: /.static/looseCouplingIllustration.dot

Loose coupling is enabled by default in ARMI simulations.

Tight Coupling
==============
Tight coupling is interpreted as two-way communication between physics within a given time node. Revisiting our previous example, enabling tight coupling results in the temperature distribution being used to generate updated cross sections (new temperatures induce changes such as Doppler broadening feedback) and ultimately an updated power distribution. This process is repeated iteratively until a numerical convergence criteria is met.

.. graphviz:: /.static/tightCouplingIllustration.dot

The following settings are involved with enabling tight coupling in ARMI:

1. ``tightCoupling``: When ``True``, tight coupling is enabled.
2. ``tightCouplingSettings``: Used to specify which parameters and convergence criteria will be used to measure the convergence of a given interface.

.. code-block:: yaml

       tightCoupling: true
       tightCouplingSettings:
         globalFlux:
           parameter: power
           convergence: 1.0e-4
         thermalHydraulics:
           parameter: THaverageCladTemperature
           convergence: 1.0e-2


The ``tightCouplingSettings`` settings interact with the interfaces available in ARMI (or an ARMI app). The interface headers (i.e., "globalFlux" and "thermalHydraulics") must match the value prescribed for :py:attr:`Interface.function <armi.interfaces.interface.function>`. The option, ``parameter``, can be a registered parameter. The ``convergence`` option is expected to be any float value. In the current implementation, different interfaces may have different developer intended restrictions. For example, the global flux interface currently only allows the eigenvalue (i.e. :math:`k_{\text{eff}}`) or block-wise power to be valid ``parameter`` values.

.. warning::
    The inherent limitations of the above interface-based tight coupling settings have been documented and a new and improved user-interface is currently being developed.

In the global flux interface, the following norms are used to compute the convergence of :math:`k_{\text{eff}}` and block-wise power.

Eigenvalue
----------
The convergence of the eigenvalue is measured through an L2-norm.

.. math::
    \epsilon = \| k_\text{eff} \|_2 = \left( \left( k_\text{eff,old} - k_\text{eff,new} \right)^2 \right) ^ \frac{1}{2}

Block-wise Power
----------------
The block-wise power can be used as a convergence mechanism to avoid the integral effects of :math:`k_{\text{eff}}` (i.e., over and under predictions cancelling each other out) and in turn, can have a different convergence rate. To measure the convergence of the power distribution with the prescribed tolerances (e.g., 1e-4), the power is scaled in the following manner (otherwise the calculation struggles to converge). 

For an assembly, :math:`a`, we compute the total power of the assembly,

.. math::
    a_{\text{power},i} = \sum_{j}b_{\text{power},(i,j)},

where :math:`i` is the :math:`i^{\text{th}}` assembly and :math:`j` is the :math:`j^{\text{th}}` block within assembly, :math:`i`. With the assembly power, we scale the block power and obtain an array of scaled block powers for a given assembly, :math:`\mathbf{b}_{i}`,

.. math::
    \mathbf{b}_{i} = \left\lbrace \frac{b_{\text{power},(i,j)}}{a_{\text{power},i}} \right\rbrace, \quad \forall j \in a_i.

We can now calculate a convergence parameter for each assembly,

.. math::
    \epsilon_i &= \| \textbf{b}_{i,\text{old}} - \textbf{b}_{i,\text{new}} \|_2 \\
               &=\sqrt{\sum_{i}\left( \textbf{b}_{i,\text{old}} - \textbf{b}_{i,\text{new}} \right)^2}.

These assembly-wise convergence parameters are then stored in an array of convergence values,

.. math::
    \xi = \left\lbrace \epsilon_i \right\rbrace,\quad \forall i \in \text{Core}.

The total convergence of the power distribution is finally measured through the infinity norm (i.e, the max) of :math:`\xi`,

.. math::
    \epsilon = \| \xi \|_{\inf} = \max \xi.


The Global Flux Interface
-------------------------
The :py:class:`Global Flux Interface <armi.physics.neutronics.globalFlux.globalFluxInterface.GlobalFluxInterface>`
class will attempt to set its own ``TightCoupler`` based on ``keff``. To see the specifics, see:
:py:meth:`_setTightCouplingDefaults <armi.physics.neutronics.globalFlux.globalFluxInterface.GlobalFluxInterface._setTightCouplingDefaults>`.
If you want to change the tight coupling performance of the ``GlobalFluxInterface``, it would be
easiest to just subclass the interface and over-write the `_setTightCouplingDefaults` method.
