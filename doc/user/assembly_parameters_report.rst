Assembly Parameters
===================
This document lists all of the Assembly Parameters that are provided by the ARMI
Framework and included plugins.

.. exec::
   from armi.reactor import assemblies
   from armi.reactor import assemblyParameters
   from armi.reactor import parameters

   return parameters.generateTable(
       assemblies.Assembly, assemblyParameters.getAssemblyParameterDefinitions()
   )


