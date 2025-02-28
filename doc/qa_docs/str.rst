Software Test Report (STR)
==========================

Purpose and Scope
-----------------

This document is the software test report (STR) for the ARMI framework.

.. _ref_armi_default_test_criteria:

Default Test Criteria
---------------------

The acceptance tests for ARMI requirements are very uniform. They are all unit tests that were
designed to be quite linear and straight-forward. Unless the test states otherwise, all of the
following test criteria apply to each ARMI requirement test. Any deviation from these standard
conditions will be documented in  :numref:`Section %s <ref_armi_test_trace_matrix>` on a test-by-
test basis.

Testing Approach
^^^^^^^^^^^^^^^^

This section defines some test attributes that all tests here have in common.

Planned Test Cases, Sequence, and Identification of Stages Required
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

The test cases are described in the test traceability matrix in 
:numref:`Section %s <ref_armi_test_trace_matrix>`. All  tests must be run, and the sequence can be
in any order unless otherwise  specified for the test in
:numref:`Section %s <ref_armi_test_trace_matrix>`.

Requirements for Testing Logic Branches
"""""""""""""""""""""""""""""""""""""""

Tests are written such that each test has only one primary logic path. For tests that do not conform
to only one logic path, more information will be defined in  the test traceability section of the
STR  (:numref:`Section %s <ref_armi_test_trace_matrix>`) defining the logic flow in  more detail.

.. _ref_armi_hardware_integration:

Requirements for Hardware Integration
"""""""""""""""""""""""""""""""""""""

The ``ARMI`` software test will be run in modern versions Linux, Windows, and MacOS. Though for
documentation brevity, we will only attach the verbose logging to this document for Linux.

Criteria for Accepting the Software
"""""""""""""""""""""""""""""""""""

The acceptance testing must pass with satisfactory results for all tests associated with
requirements in the :ref:`Software Requirements Specification  Document (SRSD) <armi_srsd>`
for the ``ARMI`` software.

.. _ref_armi_input_data_requirements:

Necessary Inputs to Run Test Cases
""""""""""""""""""""""""""""""""""

If inputs are necessary to run test cases or to return the system and data back to its original
state, the processes will be documented in the test  traceability matrix (TTM) in
:numref:`Section %s <ref_armi_test_trace_matrix>`  (The TTM provides traceability for each test to
the required criteria). Otherwise, there are no special inputs necessary to run test cases or steps
to  restore the system. 

Required Ranges of Input Parameters for the Test Case(s)
""""""""""""""""""""""""""""""""""""""""""""""""""""""""

If a test uses a range of inputs, then it will be documented in the TTM in 
:numref:`Section %s <ref_armi_test_trace_matrix>`. Otherwise, there are no required ranges of inputs
for the test case.

Expected Results for the Test Case(s)
"""""""""""""""""""""""""""""""""""""

If a test expects a specific result, it will be documented in the TTM in 
:numref:`Section %s <ref_armi_test_trace_matrix>`. Otherwise, the expected test result is that no
error is raised, which constitutes a passing test.

Acceptance Criteria for the Test Case(s)
""""""""""""""""""""""""""""""""""""""""

The acceptance criteria for the test cases will be described. In cases where the SRSD requirement
acceptance criteria is acceptable for the test case  acceptance criteria, the SRSD requirement
acceptance criteria can be referenced  by default.

.. _ref_armi_record_criteria:

Test Record Criteria
^^^^^^^^^^^^^^^^^^^^

The default values for the remaining 12 criteria pertaining to the test record are given in this
section below. A test record will be produced after the test  is run which contains pertinent
information about the execution of the test.  This test record will be saved as part of the software
test report (STR).

Software Tested, Including System Software Used and All Versions
""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

The ARMI version will be shown in the test record via standard output logs. 

Compute Platform and Hardware Used
""""""""""""""""""""""""""""""""""

The test record will reference the environment upon which the test is run. See
:numref:`Section %s <ref_armi_hardware_integration>` for acceptable test environments.

Test Equipment and Calibrations
"""""""""""""""""""""""""""""""

Not applicable for the ``ARMI`` software.

.. _ref_armi_run_env:

Runtime Environment Including System Software, and Language-Specific Environments
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

The runtime environment including the operating system, hardware, and software configuration will be
specified in the test report. If necessary, more detail will be provided for individual tests which
utilize custom runtime environments or have dependencies such as custom compiler options.

Date of Test
""""""""""""

The date of the test execution is recorded in the output of the test.

Tester or Data Recorder
"""""""""""""""""""""""

Acceptance tests will be run via automation.

Simulation Models Used
""""""""""""""""""""""

If simulation models beyond what is described elsewhere in the documentation (SRSD, SDID, or STR)
are used the simulation models will be  documented in the test record. Otherwise, this test record
criterion is not  applicable to the test.

Test Problems Identified During Test Planning
"""""""""""""""""""""""""""""""""""""""""""""

If specific problems such as textbooks or benchmarks are utilized for the test, then the test record
will reference those problems. Otherwise, test problems  are not applicable to the test record.

All Input Data and Output Results and Applicability
"""""""""""""""""""""""""""""""""""""""""""""""""""

The input data will be recorded per :numref:`Section %s <ref_armi_input_data_requirements>`. Output
data will be provided as a pass or fail of the test as part of the test  record.

Action Taken in connection with Any Deviations Noted
""""""""""""""""""""""""""""""""""""""""""""""""""""

No actions will have been assumed to be taken based on the test other than pass or fail for the
test. If there are exceptions, to this statement, they will be noted in the TTM in
:numref:`Section %s <ref_armi_test_trace_matrix>`. 

Person Evaluating Test Result
"""""""""""""""""""""""""""""

The reviewer of the document will evaluate the test results. Any failing unit test should result in
a release failure.

Acceptability
"""""""""""""

The test record states whether the tests pass or fail.


.. _ref_armi_test_trace_matrix:

Test Traceability Matrix
------------------------

The requirements and associated tests which demonstrate acceptance of the codebase with the
requirements are in the :ref:`SRSD <armi_srsd>`. This section contains a list of all tests and will
provide information for  any non-default  criteria (see
:numref:`Section %s <ref_armi_default_test_criteria>` for default criteria).

Here are some quick metrics for the requirement tests in ARMI:

* :need_count:`type=='req' and status=='accepted'` Accepted Requirements in ARMI

  * :need_count:`type=='req' and status=='accepted' and len(tests_back)>0` Accepted Requirements with tests
  * :need_count:`type=='test' and id.startswith('T_ARMI')` tests linked to Requirements

And here is a full listing of all the tests in ARMI, that are tied to requirements:

.. needextract::
  :types: test
  :filter: id.startswith('T_ARMI_')


Test Results Report
-------------------

This section provides the results of the test case runs for this release of ARMI software.

.. _ref_armi_test_env:

Testing Environment
^^^^^^^^^^^^^^^^^^^

This section describes the relevant environment under which the tests were run as required by
:numref:`Section %s <ref_armi_run_env>`. Note that individual test  records have the option to
define additional environment information.

System Information
""""""""""""""""""

The logged operating system and processor information proves what environment the software was
tested on:

.. literalinclude:: ../../system_info.log

Python Version and Packages
+++++++++++++++++++++++++++

.. literalinclude:: ../../python_details.log

.. _ref_armi_software_date:

Software Tested and Date
""""""""""""""""""""""""

The software tested and date of testing are below: 

.. literalinclude:: ../../python_details.log
   :lines: 1-2

Record of Test Cases
^^^^^^^^^^^^^^^^^^^^

This section includes the resulting test record for each test which together with 
:numref:`Section %s <ref_armi_test_env>` satisfies the criteria necessary for the creation of the
test record defined in :numref:`Section %s <ref_armi_record_criteria>`.

.. test-results:: ../test_results.xml


Appendix A Pytest Verbose Output 
--------------------------------

Below is the verbose output of the pytest run for armi.

.. literalinclude:: ../../pytest_verbose.log
