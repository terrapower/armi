*****************
Symmetry Handling
*****************

This section will describe how partial core symmetry is handled in ARMI.

Introduction
============

A partial core may be specified in the blueprints file using the ``symmetry`` attribute, as shown below.

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
          C F

Specifying a core this way is useful for saving computation time, so long as the core state being modeled is truly symmetric.

Because of this, assemblies and blocks have a ``symmetryFactor`` attribute that is used to track how much of the object
is present in the currently modeled core. For example, the central assembly (labeled "C") in the core lattice definition above would 
have a symmetry factor of 3, representing that only 1/3rd of the assembly is in the core model. The blocks within that
assembly would have the same symmetry factor.

Reactors do not have symmetry factors, Cores have symmetry factors but no core parameters are adjusted due to symmetry currently,
and Components always have a symmetry factor of 1. That is, only parameters for Assembly and Block objects are adjusted for 
symmetry.


Symmetry-Aware Operations
=========================

Because some assemblies may be partially in a partial core (e.g. the central assembly in a 1/3rd hex core) certain 
core and assembly operations must adjust parameters to maintain accurate bookkeeping.

The third core hex converter methods :py:meth:`convert <armi.reactor.converters.geometryConverters.ThirdCoreHexToFullCoreChanger.convert>` and 
:py:meth:`restorePreviousGeometry <armi.reactor.converters.geometryConverters.ThirdCoreHexToFullCoreChanger.restorePreviousGeometry>` are both 
core-level operations that account for symmetry when calculating the values of parameters on assemblies and blocks in the converted core. 

On an assembly level, the assembly method :py:meth:`moveTo <armi.reactor.assemblies.Assembly.moveTo>` adjusts parameters as necessary when
moving an assembly between locations with differing symmetry factors.


Parameters Adjusted With Symmetry
=================================

Only some parameters need to be adjusted with symmetry. A parameter must be on either an Assembly or Block object and 
have the flag ``VOLUME_INTEGRATED`` to be adjusted in the operations listed in the previous section. 
