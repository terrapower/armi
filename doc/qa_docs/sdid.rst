Software Design and Implementation Document (SDID)
==================================================


Purpose and Scope
-----------------

This document is the Software Design and Implementation Document (SDID) for ARMI.

The purpose of this document is to define how the ARMI requirements are implemented. These are
important user stories for anyone wanting to use ARMI or develop their own ARMI-based application.
The implementation of the ARMI requirements is described in detail in an Implementation Traceability
Matrix (ITM).


Procedural Compliance
^^^^^^^^^^^^^^^^^^^^^

This document includes information on four topics: the (1) software environment, (2) measures to
mitigate possible failures, (2) implementation of the computational sequence, and (4) technical
adequacy.

Software Environment
^^^^^^^^^^^^^^^^^^^^

ARMI is built using the Python programming language and runs on Windows and Linux operating systems.

Failure Mitigation
^^^^^^^^^^^^^^^^^^

ARMI provides a suite of unit tests which provide indication of the proper usage of the program.
These tests are described in the software test report and are directly traceable to the requirements
in the software requirements specification document. The purpose of these tests is to provide a way
for downstream users to test and measure the utility of the ARMI framework for their own purposes,
in their own environment. This allows users and developers to perform failure analysis. These tests
allow for a push-button way to measure and mitigate consequences and problems including external and
internal abnormal conditions and events that can affect the software.

Implementation of Computational Sequence
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The computational sequence and relevant portions of the technical adequacy are specific to the
implementation and are described for each implementation in the
:ref:`Implementation Traceability Matrix <armi_impl_matrix>`.

Technical Adequacy
^^^^^^^^^^^^^^^^^^

The internal completeness for each implementation is shown by providing traceability to the
requirements as showing in the :ref:`Implementation Traceability Matrix <armi_impl_matrix>`. The
consistency of the implementation is provided by a best practice used by the development team
including, revision control, ensuring that code content is reviewed by non-code originating team
members, and ensuring training for developers. Clarity is provided by the descriptions of the
implementations in the :ref:`Implementation Traceability Matrix <armi_impl_matrix>`. Figures are
added as needed in the implementation in the
:ref:`Implementation Traceability Matrix <armi_impl_matrix>`.


Design and Implementation
-------------------------

To automate the process of tracking the implementation of all requirements in ARMI, we are using the
`Implementation Traceability Matrix <#implementation-traceability-matrix>`_ below. This will connect
high-quality, in-code documentation with each requirement in a complete way. However, before giving
a complete overview of the requirement implementations, this document will describe the design of
two main features in the ARMI codebase: the plugin system and the reactor data model. These are the
two major features which you need to understand to understand what ARMI is, and why it is useful.
So, at the risk of duplicating documentation, the design of these two features will be discussed in
some detail.


Implementation of Plugin System
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The first important design idea to understand in ARMI is that ARMI is a framework for nuclear
reactor modeling. What this means is that the science or engineering calculations for nuclear
reactor modeling do not happen in ARMI. The point of ARMI is to tie together disparate nuclear
modeling software that already exist. Thus, ARMI must be able to wrap external codes, and
orchestrate running them at each time step we want to model.

The second design idea is that at each time step, there is an ordered list of conceptual reactor
modeling steps to be executed. ARMI calls these steps
:py:class:`Interfaces <armi.interfaces.Interface>` and runs the code in each, in order, at each time
step. While ARMI does have a default list of modeling steps, and a default order, none of the steps
are mandatory, and their order is modifiable. An example interface stack would be:

* preprocessing
* fuel management
* depletion
* fuel performance
* cross sections
* critical control
* flux
* thermal hydraulics
* reactivity coefficients
* transient
* bookkeeping
* postprocessing

So, how do we add Interfaces to the simulation? The third major design idea is that developers can
create an ARMI :py:class:`Plugin <armi.plugins.ArmiPlugin>`, which can add one or more Interfaces to
the simulation.

Lastly, at the highest level of the design, a developer can create an ARMI
:py:class:`Application <armi.apps.App>`. This is a flexible container that allows developers to
register multiple Plugins, which register multiple Interfaces, which fully define all the code that
will be run at each time step of the simulation.

Below is a diagram from an example ARMI Application. Following this design, in the real world you
would expect an ARMI Application to be made by various teams of scientists and engineers that define
one Plugin and a small number of Interfaces. Then a simulation of the reactor would be carried out
over some number of cycles / time nodes, where each of the Interfaces would be run in a specified
order at each time node.

.. figure:: /.static/armi_application_structure.png
    :align: center

    An example ARMI Application.

If this high-level design seems abstract, that is by design. ARMI is not concerned with implementing
scientific codes, or enforcing nuclear modelers do things a certain way. ARMI is a tool that aims to
support a wide audience of nuclear reactor modelers.


Implementation of Reactor Data Model
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In the previous section, we described how an ARMI Application is put together. But that Application
is only useful if it can pass information about the reactor between all the external codes that are
being wrapped by each Interface. Thus, an important part of the ARMI design is that is has a robust
and detailed software data model to represent the current state of the reactor. This data model can
be queried and manipulated by each Interface to get data that is needed to run the external reactor
modeling codes.

The structure of the ARMI reactor data model is designed to be quite flexible, and heavily
modifiable in code. But most of the practical work done with ARMI so far has been on pin-type
reactor cores, so we will focus on such an example.

At the largest scale, the :py:class:`Reactor <armi.reactor.reactors.Reactor>` contains a
:py:class:`Core <armi.reactor.reactors.Core>` and a
:py:class:`Spent Fuel Pool <armi.reactor.assemblyLists.SpentFuelPool>`. The Core is made primarily
of a collection of :py:class:`Assemblies <armi.reactor.assemblies.Assembly>`, which are vertical
collections of :py:class:`Blocks <armi.reactor.blocks.Block>`. Each Block, and every other physical
piece of the Reactor is a :py:class:`Composite <armi.reactor.composites.Composite>`. Composites have
a defined shape, material(s), location in space, and parent. Composites have parents because ARMI
defines all Reactors as a hierarchical model, where outer objects contain inner children, and the
Reactor is the outermost object. The important thing about this model is that it is in code, so
developers of ARMI Interfaces can query and modify the reactor data model in any way they need.

.. figure:: /.static/armi_reactor_objects.png
    :align: center

    Structure of the ARMI reactor data model.


.. _armi_hardware:

Hardware/OS Compatibility
^^^^^^^^^^^^^^^^^^^^^^^^^

ARMI is a Python-based framework, designed to help tie together various nuclear models, all written
in a variety of languages. ARMI officially supports Python versions 3.9 and higher. ARMI is also
designed to work on modern versions of both Windows and Linux.

The memory, CPU, and hardware needs of an ARMI simulation depend on the Reactor. Simulations run
with lumped fission products will require more memory than those run without. Simulations with much
larger, more detailed reactor core blueprints, or containing more components, will take up more
memory than simpler blueprints. ARMI can also be run with only one process, but most users choose to
run ARMI in parallel on a computing cluster of some kind. In practice, users tend to find that
dozens or hundreds of parallel processes are helpful for speeding up ARMI runs, and each process
will ideally have 1 or 2 GB of RAM.


Error/Input Handling
^^^^^^^^^^^^^^^^^^^^

ARMI's internal error-handling library is the :py:mod:`runLog <armi.runLog>`. This tool handles the
warnings and errors for internal ARMI code and all the plugins. The ``runLog`` system will handle
both print-to-screen and log file messages. At the end of the run, all log messages from every
plugin and from all parallel processes are tabulated into centralized log files.

The ``runLog`` system will also tabulate a list of all warnings that occurred doing a simulation.
And it should be noted that most full "errors" will cause the ARMI simulation to fail and stop hard,
ending the run early. This is the ideal solution, so people know the run results are invalid. To
that affect, ARMI makes use of Python's robust `Exception` system.


.. _armi_impl_matrix:

Implementation Traceability Matrix
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The requirements and associated tests which demonstrate acceptance of the codebase with the
requirements are in the Software Requirements Specification Document :ref:`(SRSD) <armi_srsd>`. This
section contains a list of all requirement implementations.

Here are some quick metrics for the requirement implementations in ARMI:

* :need_count:`type=='req' and status=='accepted'` Accepted Requirements in ARMI

  * :need_count:`type=='req' and status=='accepted' and len(implements_back)>0` Accepted Requirements with implementations
  * :need_count:`type=='impl'` implementations linked to Requirements

And here is a full listing of all the requirement implementations in ARMI, that are tied to requirements:

.. needextract::
  :filter: id.startswith('I_ARMI_')
