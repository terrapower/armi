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

.. req:: The operator package shall provide a means by which to communicate inputs and results between analysis plugins.
    :id: R_ARMI_OPERATOR_COMM
    :subtype: functional
    :basis: This is a foundational design concept in ARMI and is what makes it a framework.
    :acceptance_criteria: A plugin can access run input data and results from other plugins.
    :status: accepted

.. req:: The operator package shall allow tight coupling between analysis plugins.
    :id: R_ARMI_OPERATOR_PHYSICS
    :subtype: functional
    :basis: Tight coupling is a mechanism that allows for simultaneous convergence of analysis results.
    :acceptance_criteria: An operator can call each interface multiple times at a given time node, subject to some convergence criteria.
    :status: accepted

.. req:: The operator package shall provide a means to perform parallel computations.
    :id: R_ARMI_OPERATOR_MPI
    :subtype: functional
    :basis: Parallel computations provide scalable solutions to computational performance.
    :acceptance_criteria: An operator can execute logic dependent on its MPI rank.
    :status: accepted

.. req:: ARMI shall allow users to customize how time is discretized for modeling.
    :id: R_ARMI_FW_HISTORY
    :subtype: functional
    :basis: Analysts will want to model the time evolution of reactors. And discretizing time is a common need to nearly all scientific modeling.
    :acceptance_criteria: Specify number of cycles and burn steps and observe the interfaces are run at those time nodes.
    :status: accepted

.. req:: An application shall consist of a collection of plugins.
    :id: R_ARMI_APP_PLUGINS
    :subtype: functional
    :basis: Plugins are the major mechanism for adding code to a simulations.
    :acceptance_criteria: Construct an ARMI application from a collection of plugins.
    :status: accepted

.. req:: An operator shall be built from user settings.
    :id: R_ARMI_OPERATOR_SETTINGS
    :subtype: functional
    :basis: Configuring an operator allows users to customize a simulation.
    :acceptance_criteria: Construct an operator that depends on user settings.
    :status: accepted

.. req:: The operator package shall expose an ordered list of interfaces that is looped over at each time step.
    :id: R_ARMI_OPERATOR_INTERFACES
    :subtype: functional
    :basis: Reactor modeling is controlled by looping over an ordered list of interfaces at each time node.
    :acceptance_criteria: Show that interfaces are executed in order at each time step.
    :status: accepted

.. req:: The interface package shall allow code execution at important operational points in time.
    :id: R_ARMI_INTERFACE
    :subtype: functional
    :basis: Defining code to be run at specific times allows users to control the reactor simulation and analysis.
    :acceptance_criteria: Show that interfaces allow code to be execute at BOL, EOL, BOC, and EOC.
    :status: accepted

.. req:: The plugin module shall allow the creation of a plugin, which adds code to the application.
    :id: R_ARMI_PLUGIN
    :subtype: functional
    :basis: The primary way developers will add code to the simulation is by writing an ARMI plugin.
    :acceptance_criteria: Load a plugin into an application.
    :status: accepted

.. req:: Plugins shall add interfaces to the operator.
    :id: R_ARMI_PLUGIN_INTERFACES
    :subtype: functional
    :basis: The mechanism by which plugins add code to the simulation is that plugins can register interfaces on the operator.
    :acceptance_criteria: Register multiple interfaces from a given plugin.
    :status: accepted

.. req:: Plugins shall have the ability to add parameters to the reactor data model.
    :id: R_ARMI_PLUGIN_PARAMS
    :subtype: functional
    :basis: An important feature of plugins is that they can add parameters to the reactor model, thus increasing the variety of physical values the simulations can track.
    :acceptance_criteria: Register multiple parameters from a given plugin.
    :status: accepted

.. req:: Plugins shall have the ability to add custom settings to the simulation.
    :id: R_ARMI_PLUGIN_SETTINGS
    :subtype: functional
    :basis: An important feature of plugins is that they can add settings that can be used to configure a simulation.
    :acceptance_criteria: Add multiple settings from a given plugin.
    :status: accepted

.. ## Note: These 12 requirements define ARMI at a high level. They will rarely change.
