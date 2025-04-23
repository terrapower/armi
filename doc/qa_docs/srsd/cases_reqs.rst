.. _armi_cases:

Cases Package
-------------

This section provides requirements for the :py:mod:`armi.cases` package within the framework, which
is responsible for running and analyzing ARMI-based cases and case suites for an application. This
includes functionalities to serialize and deserialize case inputs for input modification, tracking
the status of a case, and running simulations.

Functional Requirements
+++++++++++++++++++++++

.. req:: The case package shall provide a generic mechanism that will allow a user to run a simulation.
    :id: R_ARMI_CASE
    :subtype: functional
    :basis: Most workflows rely on this capability.
    :acceptance_criteria: Build a case and initialize a simulation.
    :status: accepted

.. req:: The case package shall provide a tool to run multiple cases at the same time or with dependence on other cases.
    :id: R_ARMI_CASE_SUITE
    :subtype: functional
    :basis: Many workflows rely on this capability.
    :acceptance_criteria: Build a suite of cases with dependence and run them.
    :status: accepted

.. req:: The case package shall provide a generic mechanism to allow users to modify user inputs in a collection of cases.
    :id: R_ARMI_CASE_MOD
    :subtype: functional
    :basis: This capability is needed by analysis workflows such as parameter studies and uncertainty quantification.
    :acceptance_criteria: Load user inputs and build a collection of cases that contain programmatically-perturbed inputs.
    :status: accepted

I/O Requirements
++++++++++++++++

.. req:: The case package shall have the ability to load user inputs and perform input validation checks.
    :id: R_ARMI_CASE_CHECK
    :subtype: io
    :basis: Most workflows rely on this capability.
    :acceptance_criteria: Load user inputs and perform validation checks.
    :status: accepted
