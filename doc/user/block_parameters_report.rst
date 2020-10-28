Block Parameters
================
This document lists all of the Block Parameters that are provided by the ARMI
Framework and included plugins.

.. exec::
   from armi.reactor import blocks
   from armi.reactor import blockParameters
   from armi.utils.dochelpers import generateParamTable

   return generateParamTable(
       blocks.Block, blockParameters.getBlockParameterDefinitions()
   )


