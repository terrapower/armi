.. _core-parameters-report:

***************
Core Parameters
***************

This document lists all of the Core Parameters that are provided by the ARMI Framework.

.. exec::
   from armi.reactor import reactors
   from armi.reactor import reactorParameters
   from armi.utils.dochelpers import generateParamTable

   return generateParamTable(
       reactors.Core, reactorParameters.defineCoreParameters()
   )

