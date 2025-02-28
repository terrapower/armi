.. _armi_settings:

Settings Package
----------------

This section provides requirements for the :py:mod:`armi.settings` package, which is responsible for providing a centralized means for users to configure an application. This package can serialize and deserialize user settings from a human-readable text file. When a simulation is being initialized, settings validation is performed to enforce things like type consistency, and to find incompatible settings. To make settings easier to understand and use, once a simulation has been initialized, settings become immutable.

Functional Requirements
+++++++++++++++++++++++

.. req:: The settings package shall allow the configuration of a simulation through user settings.
    :id: R_ARMI_SETTING
    :status: accepted
    :basis: Settings are how the user configures their run.
    :acceptance_criteria: Create and edit a set of settings that can be used to initialize a run.
    :subtype: functional

.. req:: All settings must have default values.
    :id: R_ARMI_SETTINGS_DEFAULTS
    :status: accepted
    :basis: Enforcing a default recommendation for a setting allows for ease-of-use of the system
    :acceptance_criteria: A setting cannot be created without providing a default value.
    :subtype: functional

.. req:: Settings shall support rules to validate and customize each setting's behavior.
    :id: R_ARMI_SETTINGS_RULES
    :status: accepted
    :basis: Validation of user settings adds quality assurance pedigree and reduces user errors.
    :acceptance_criteria: Query a setting and make decisions based on its value.
    :subtype: functional

.. req:: The settings package shall supply the total reactor power at each time step of a simulation.
    :id: R_ARMI_SETTINGS_POWER
    :status: accepted
    :basis: Power history is needed by many downstream plugins and methodologies for normalization.
    :acceptance_criteria: Retrieve the power fractions series from the operator and access the value at a given time step.
    :subtype: functional

.. req:: The settings package shall allow users to define basic metadata for the run.
    :id: R_ARMI_SETTINGS_META
    :status: accepted
    :basis: Storing metadata in the settings file makes it easier for analysts to differentiate many settings files, and describe the simulations they configure.
    :acceptance_criteria: Set and retrieve the basic metadata settings.
    :subtype: functional

I/O Requirements
++++++++++++++++

.. req:: The settings package shall use human-readable, plain-text files as input and output.
    :id: R_ARMI_SETTINGS_IO_TXT
    :status: accepted
    :basis: Settings are how the user configures their run.
    :acceptance_criteria: Show a settings object can be created from a text file with a well-specific format, and written back out to a text file.
    :subtype: io
