.. _block-parameters-report:

****************
Block Parameters
****************

This document lists all of the :py:mod:`Block Parameters <armi.reactor.blockParameters>` that are provided by the ARMI
Framework. See :py:mod:`armi.reactor.parameters` for use.

.. exec::
   from armi.reactor import blocks
   from armi.reactor import blockParameters
   from dochelpers import generateParamTable

   return generateParamTable(
       blocks.Block, blockParameters.getBlockParameterDefinitions()
   )


