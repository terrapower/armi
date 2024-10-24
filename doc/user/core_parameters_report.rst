.. _core-parameters-report:

***************
Core Parameters
***************

This document lists all of the Core Parameters that are provided by the ARMI Framework. See
:py:mod:`armi.reactor.parameters` for use.

.. exec::
   from armi.reactor import reactors
   from armi.reactor import reactorParameters
   from dochelpers import generateParamTable

   return generateParamTable(
       reactors.Core, reactorParameters.defineCoreParameters()
   )
