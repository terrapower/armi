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

   return generateParamTable(
       reactors.Reactor, reactorParameters.defineReactorParameters()
   )
