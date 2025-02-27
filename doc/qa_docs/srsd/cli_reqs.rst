.. _armi_cli:

Command Line Interface Package
------------------------------

This section provides requirements for the :py:mod:`armi.cli` package. This package is
responsible for providing user entry points to an ARMI-based application as a Command Line Interface (CLI). This package allows for developers to create their own automated work flows including: case submission, user setting validation, data migrations, and more.

Functional Requirements
+++++++++++++++++++++++

.. req:: The cli package shall provide a generic CLI for developers to build their own CLI.
    :id: R_ARMI_CLI_GEN
    :basis: Provides extensibility of the system behavior for an application to implement analysis workflows.
    :subtype: functional
    :status: accepted
    :acceptance_criteria: Create an entry point, pass it arguments, and invoke it.

I/O Requirements
++++++++++++++++

.. req:: The cli package shall provide a basic CLI which allows users to start an ARMI simulation.
    :id: R_ARMI_CLI_CS
    :basis: This is relied upon for most users to submit jobs to a cluster.
    :subtype: io
    :status: accepted
    :acceptance_criteria: Invoke an ARMI CLI.
