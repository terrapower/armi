.. _assembly-parameters-report:

*******************
Assembly Parameters
*******************

This document lists all of the :py:mod:`Assembly Parameters <armi.reactor.assemblyParameters>` that are provided by the
ARMI Framework. See :py:mod:`armi.reactor.parameters` for use.

.. exec::
   from armi.reactor import assemblies
   from armi.reactor import assemblyParameters
   from dochelpers import generateParamTable

   return generateParamTable(
       assemblies.Assembly, assemblyParameters.getAssemblyParameterDefinitions()
   )
