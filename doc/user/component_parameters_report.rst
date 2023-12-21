********************
Component Parameters
********************

This document lists all of the Component Parameters that are provided by the ARMI Framework.

.. exec::
   from armi.reactor.components import Component
   from armi.reactor.components.componentParameters import getComponentParameterDefinitions
   from armi.utils.dochelpers import generateParamTable

   return generateParamTable(Component, getComponentParameterDefinitions())
