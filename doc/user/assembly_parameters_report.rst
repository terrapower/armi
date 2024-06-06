.. _assembly-parameters-report:

*******************
Assembly Parameters
*******************

This document lists all of the Assembly Parameters that are provided by the ARMI Framework.

.. exec::
   from armi.reactor import assemblies
   from armi.reactor import assemblyParameters
   from dochelpers import generateParamTable

   return generateParamTable(
       assemblies.Assembly, assemblyParameters.getAssemblyParameterDefinitions()
   )
