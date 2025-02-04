.. _armi_framework:

Framework-Related Concepts
--------------------------

This section provides the highest-level requirements for the ARMI framework. These requirements are
specific to the idea that ARMI is a framework, that allows for the connection of disparate scientific and
nuclear engineer models. The four major pieces of the codebase covered by these requirements are:

    - :py:mod:`armi.apps` - An ARMI simulation is controlled by an ARMI :py:class:`Application <armi.apps.App>`.
    - :py:mod:`armi.plugins` - Each :py:class:`Application <armi.apps.App>` registers a list of :py:class:`Plugins <armi.plugins.ArmiPlugin>`.
    - :py:mod:`armi.interfaces` - Each :py:class:`Plugin <armi.plugins.ArmiPlugin>` registers a list of :py:class:`Interface <armi.interfaces.Interface>`.
    - :py:mod:`armi.operators` - The :py:class:`Operator <armi.operators.Operator>` contains a list of :py:class:`Interfaces <armi.interfaces.Interface>`, which are run in order at each time node.

Functional Requirements
+++++++++++++++++++++++

.. ## Note: These 12 requirements define ARMI at a high level. They will rarely change.

.. req:: placeholder
    :id: R_ARMI_OPERATOR_COMM
    :subtype: functional
    :basis: placeholder
    :acceptance_criteria: placeholder
    :status: accepted

.. req:: placeholder
    :id: R_ARMI_OPERATOR_PHYSICS
    :subtype: functional
    :basis: placeholder
    :acceptance_criteria: placeholder
    :status: accepted

.. req:: placeholder
    :id: R_ARMI_OPERATOR_MPI
    :subtype: functional
    :basis: placeholder
    :acceptance_criteria: placeholder
    :status: accepted

.. req:: placeholder
    :id: R_ARMI_FW_HISTORY
    :subtype: functional
    :basis: placeholder
    :acceptance_criteria: placeholder
    :status: accepted

.. req:: placeholder
    :id: R_ARMI_APP_PLUGINS
    :subtype: functional
    :basis: placeholder
    :acceptance_criteria: placeholder
    :status: accepted

.. req:: placeholder
    :id: R_ARMI_OPERATOR_SETTINGS
    :subtype: functional
    :basis: placeholder
    :acceptance_criteria: placeholder
    :status: accepted

.. req:: placeholder
    :id: R_ARMI_OPERATOR_INTERFACES
    :subtype: functional
    :basis: placeholder
    :acceptance_criteria: placeholder
    :status: accepted

.. req:: placeholder
    :id: R_ARMI_INTERFACE
    :subtype: functional
    :basis: placeholder
    :acceptance_criteria: placeholder
    :status: accepted

.. req:: placeholder
    :id: R_ARMI_PLUGIN
    :subtype: functional
    :basis: placeholder
    :acceptance_criteria: placeholder
    :status: accepted

.. req:: placeholder
    :id: R_ARMI_PLUGIN_INTERFACES
    :subtype: functional
    :basis: placeholder
    :acceptance_criteria: placeholder
    :status: accepted

.. req:: placeholder
    :id: R_ARMI_PLUGIN_PARAMS
    :subtype: functional
    :basis: placeholder
    :acceptance_criteria: placeholder
    :status: accepted

.. req:: placeholder
    :id: R_ARMI_PLUGIN_SETTINGS
    :subtype: functional
    :basis: placeholder
    :acceptance_criteria: placeholder
    :status: accepted

.. ## Note: These 12 requirements define ARMI at a high level. They will rarely change.
