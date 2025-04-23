.. _armi_log:

RunLog Module
-------------

This section provides requirements for the simulation logging module, :py:mod:`armi.runLog`, which manages 
the reporting of messages to the user.

Functional Requirements
+++++++++++++++++++++++

.. req:: The runLog module shall allow for a simulation-wide log with user-specified verbosity.
    :id: R_ARMI_LOG
    :subtype: functional
    :status: accepted
    :basis: Logging simulation information is required for analysts to document and verify simulation results.
    :acceptance_criteria: Messages are written to the log with specified verbosity.

I/O Requirements
++++++++++++++++

.. req:: The runLog module shall allow logging to the screen, to a file, or both.
    :id: R_ARMI_LOG_IO
    :subtype: io
    :status: accepted
    :basis: Logging simulation information is required for analysts to document and verify simulation results.
    :acceptance_criteria: Messages can be written to log files and log streams.

.. req:: The runLog module shall allow log files to be combined from different processes.
    :id: R_ARMI_LOG_MPI
    :subtype: io
    :status: accepted
    :basis: Logging simulation information is required for analysts to document and verify simulation results.
    :acceptance_criteria: Messages in different log files can be concatenated.
