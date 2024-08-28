.. _reactor-parameters-report:

******************
Reactor Parameters
******************

This document lists all of the Reactor Parameters that are provided by the ARMI Framework.

.. exec::
   from armi.reactor import reactors
   from armi.reactor import reactorParameters
   from dochelpers import generateParamTable

   return generateParamTable(
       reactors.Reactor, reactorParameters.defineReactorParameters()
   )
