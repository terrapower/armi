Software Requirements Specification Document (SRSD)
===================================================


Purpose
-------

This Software Requirements Specification Document (SRSD) is prepared for the Advanced Reactor
Modeling Interface (ARMI) framework. The purpose of thisdocument is to define the functional
requirements, I/O requirements, relevant attributes, and applicable design constraints for ARMI.

This SRSD will be accompanied by a Software Design and Implementation Document (SDID), that
describes how the requirements are implemented within the software and a Software Test Report (STR),
that documents the test plan and reporting of test results.

.. _armi_srsd:

Introduction
------------

The Advanced Reactor Modeling Interface (ARMI®) is an open-source framework for nuclear reactor
design and analysis. Based on Python, ARMI provides a richly-featured toolset for connecting
disparate nuclear reactor modeling tools. ARMI is not meant to directly implement the science or
engineering aspects of nuclear reactor modeling, but to help the wealth of existing models work
together. It does this by providing easy-to-use tools for coordinating reactor simulation and
analysis workflows. A large part of the power of ARMI is that it provides a flexible in-memory data
model of a reactor, which is used to pass information between different external tools.

ARMI:

* Provides a hub-and-spoke mechanism to standardize communication and coupling between physics
  kernels and the specialist analysts who use them,
* Facilitates the creation and execution of detailed models and complex analysis methodologies,
* Provides an ecosystem within which to rapidly and collaboratively build new analysis and physics
  simulation capabilities, and
* Provides useful utilities to assist in reactor development.

Because the ARMI software is just a framework for other, much larger nuclear models, ARMI does not
contain any proprietary or classified information. This allows ARMI to be open-source software. It
also greatly simplifies the software design and maintenance. For instance, ARMI does not have any
performance requirements. ARMI has been used to model nuclear reactors for over a decade, and in
that time the practical reality is that ARMI is quite light weight and >99% of the run time of a
simulation occurs in running other nuclear models.

Here are some quick metrics for ARMI's requirements:

* :need_count:`type=='req'` Requirements in ARMI

  * :need_count:`type=='req' and status=='preliminary'` Preliminary Requirements
  * :need_count:`type=='req' and status=='accepted'` Accepted Requirements
  * :need_count:`type=='req' and len(implements_back)>0` Requirements with implementations
  * :need_count:`type=='req' and len(tests_back)>0` Requirements with tests
  * :need_count:`type=='test'` tests linked to Requirements
  * :need_count:`type=='impl'` implementations linked to Requirements

.. Note each of these docs has their own section header

.. include:: srsd/framework_reqs.rst
.. include:: srsd/bookkeeping_reqs.rst
.. include:: srsd/cases_reqs.rst
.. include:: srsd/cli_reqs.rst
.. include:: srsd/materials_reqs.rst
.. include:: srsd/nucDirectory_reqs.rst
.. include:: srsd/nuclearDataIO_reqs.rst
.. include:: srsd/physics_reqs.rst
.. include:: srsd/reactors_reqs.rst
.. include:: srsd/runLog_reqs.rst
.. include:: srsd/settings_reqs.rst
.. include:: srsd/utils_reqs.rst


Software Attributes
-------------------

ARMI is a Python-based framework, designed to help tie together various nuclear models, written in a
variety of languages. ARMI officially supports Python versions 3.9 and up.

ARMI is heavily tested and used in both Windows and Linux. More specifically, ARMI is always
designed to work in the most modern Windows operating system (Windows 10 and Windows 11 currently).
Similarly, ARMI is designed to work with fairly modern versions of Ubuntu (22.04 and 24.04 at the
time of writing) and Red Hat (RHEL 7 and 8 currently).

Version control for ARMI is achieved using Git and is publicly hosted as open-source software on
GitHub. To ensure ARMI remains portable and open-source, it only uses third-party libraries that are
similarly fully open-source and that make no onerous demands on ARMI's distribution or legal status.

ARMI makes use of a huge suite of unit tests to cover the codebase. The tests are run via Continuous
Integration (CI) both internally and publicly. Every unit test must pass on every commit to the ARMI
main branch. Also, as part of our rigorous quality system, ARMI enforces tight controls on code
style using Black as our code formatter and Ruff as our linter.
