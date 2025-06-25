.. _armi_bookkeeping:

Bookkeeping Package
-------------------

This section provides requirements for the :py:mod:`armi.bookkeeping` package within the framework, which
handles data persistence, including storage and recovery, report generation, data visualization, 
and debugging.

Functional Requirements
+++++++++++++++++++++++

.. req:: The database package shall save a copy of the user settings associated with the run.
    :id: R_ARMI_DB_CS
    :subtype: functional
    :basis: This supports traceability and restart ability.
    :acceptance_criteria: Save and retrieve the user settings from the database.
    :status: accepted

.. req:: The database package shall save a copy of the reactor blueprints associated with the run.
    :id: R_ARMI_DB_BP
    :subtype: functional
    :basis: This supports traceability and restart ability.
    :acceptance_criteria: Save and retrieve the blueprints from the database.
    :status: accepted

.. req:: The database shall store reactor state data at specified points in time.
    :id: R_ARMI_DB_TIME
    :subtype: functional
    :basis: Loading a reactor from a database is needed for follow-on analysis.
    :acceptance_criteria: Save and load a reactor from a database at specified point in time and show parameters are appropriate.
    :status: accepted

.. req:: ARMI shall allow runs at a particular time node to be re-instantiated from a snapshot.
    :id: R_ARMI_SNAPSHOT_RESTART
    :subtype: functional
    :basis: Analysts need to do follow-on analysis on detailed treatments of particular time nodes.
    :acceptance_criteria: After restarting a run, the reactor time node and power has been correctly reset.
    :status: accepted

.. req:: The database shall store system attributes during a simulation.
    :id: R_ARMI_DB_QA
    :subtype: functional
    :basis: Storing system attributes provides QA traceability.
    :acceptance_criteria: Demonstrate that system attributes are stored in a database after it is initialized.
    :status: accepted

.. req:: ARMI shall allow for previously calculated reactor state data to be retrieved within a run.
    :id: R_ARMI_HIST_TRACK
    :subtype: functional
    :basis: Retrieval of calculated run data from a previous time node within a run supports time-based data integration.
    :acceptance_criteria: Demonstrate that a set of parameters stored at differing time nodes can be recovered.
    :status: accepted

    .. ## Note: ARMI strongly suggests you use the Database for this purpose instead.

Software Attributes
+++++++++++++++++++

.. req:: The database produced shall be agnostic to programming language.
    :id: R_ARMI_DB_H5
    :subtype: attribute
    :basis: Analysts should be free to use the data in any programming language they choose.
    :acceptance_criteria: Open an output file in the h5 format.
    :status: accepted

I/O Requirements
++++++++++++++++

.. req:: ARMI shall allow extra data to be saved from a run, at specified time nodes.
    :id: R_ARMI_SNAPSHOT
    :subtype: io
    :basis: Analysts need to do follow-on analysis on detailed treatments of particular time nodes.
    :acceptance_criteria: Snapshot logic can be called for a given set of time nodes.
    :status: accepted
