.. _params-report:

=================
Parameters Report
=================

.. exec::
   from armi.reactor import assemblies
   from armi.reactor import assemblyParameters
   from armi.reactor import blockParameters
   from armi.reactor import blocks
   from armi.reactor import reactorParameters
   from armi.reactor import reactors
   from armi.reactor.components import Component
   from armi.reactor.components.componentParameters import getComponentParameterDefinitions
   from dochelpers import generateParamTable

   s = generateParamTable(reactors.Reactor, reactorParameters.defineReactorParameters())
   numR = s.count("  * - ") - 1

   s = generateParamTable(reactors.Core, reactorParameters.defineCoreParameters())
   numC = s.count("  * - ") - 1

   s = generateParamTable(assemblies.Assembly, assemblyParameters.getAssemblyParameterDefinitions())
   numA = s.count("  * - ") - 1

   s = generateParamTable(blocks.Block, blockParameters.getBlockParameterDefinitions())
   numB = s.count("  * - ") - 1

   s = generateParamTable(Component, getComponentParameterDefinitions())
   numComp = s.count("  * - ") - 1

   numParams = numR + numC + numA + numB + numComp

   txt = f"This document lists all {numParams} Parameters in ARMI:\n\n"
   txt += f"* There are {numR} Reactor Parameters.\n"
   txt += f"* There are {numC} Core Parameters.\n"
   txt += f"* There are {numA} Assembly Parameters.\n"
   txt += f"* There are {numB} Block Parameters.\n"
   txt += f"* There are {numComp} Component Parameters.\n\n"

   return txt

Users of the ARMI Framework are not required to use all of these parameters. And the system is easy to extend to add
new Parameters for your use-cases. These are simply the default Parameters that come with ARMI.


.. _reactor-parameters-report:

******************
Reactor Parameters
******************

This document lists all of the :py:mod:`Reactor Parameters <armi.reactor.reactorParameters>` that are provided by the
ARMI Framework. See :py:mod:`armi.reactor.parameters` for use.

.. exec::
   from armi.reactor import reactors
   from armi.reactor import reactorParameters
   from dochelpers import generateParamTable

   return generateParamTable(reactors.Reactor, reactorParameters.defineReactorParameters())

.. _core-parameters-report:


***************
Core Parameters
***************

This is a list of all of the Core Parameters that are provided by the ARMI Framework. See
:py:mod:`armi.reactor.parameters` for use.

.. exec::
   from armi.reactor import reactors
   from armi.reactor import reactorParameters
   from dochelpers import generateParamTable

   return generateParamTable(reactors.Core, reactorParameters.defineCoreParameters())


.. _assembly-parameters-report:

*******************
Assembly Parameters
*******************

This is a list of all of the Assembly Parameters that are provided by the ARMI Framework. See
:py:mod:`armi.reactor.parameters` for use.

.. exec::
   from armi.reactor import assemblies
   from armi.reactor import assemblyParameters
   from dochelpers import generateParamTable

   return generateParamTable(assemblies.Assembly, assemblyParameters.getAssemblyParameterDefinitions())


.. _block-parameters-report:

****************
Block Parameters
****************

This is a list of all of the Block Parameters that are provided by the ARMI Framework. See
:py:mod:`armi.reactor.parameters` for use.

.. exec::
   from armi.reactor import blocks
   from armi.reactor import blockParameters
   from dochelpers import generateParamTable

   return generateParamTable(blocks.Block, blockParameters.getBlockParameterDefinitions())


.. _component-parameters-report:

********************
Component Parameters
********************

This is a list of all of the Component Parameters that are provided by the ARMI Framework. See
:py:mod:`armi.reactor.parameters` for use.

.. exec::
   from armi.reactor.components import Component
   from armi.reactor.components.componentParameters import getComponentParameterDefinitions
   from dochelpers import generateParamTable

   return generateParamTable(Component, getComponentParameterDefinitions())
