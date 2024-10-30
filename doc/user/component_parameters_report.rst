.. _component-parameters-report:

********************
Component Parameters
********************

This document lists all of the :py:mod:`Component Parameters <armi.reactor.components.componentParameters>` that are
provided by the ARMI Framework. See :py:mod:`armi.reactor.parameters` for use.

.. exec::
   from armi.reactor.components import Component
   from armi.reactor.components.componentParameters import getComponentParameterDefinitions
   from dochelpers import generateParamTable

   return generateParamTable(Component, getComponentParameterDefinitions())
