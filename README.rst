
|Build Status| |Code Coverage| |Commit Activity| |Good First Issues|

####
ARMI
####

The Advanced Reactor Modeling Interface (ARMI\ :sup:`®`) is an open-source tool that streamlines your nuclear reactor
design/analysis needs by providing a software reactor model and a rich ecosystem of tools to interogate that model. It
is made by and for professional reactor analysis teams and is maintained by `TerraPower LLC <http://terrapower.com/>`_,
a nuclear technology development company.

ARMI provides:

- standardized communication between physics kernels
- a flexible reactor data model
- dependable input and output data formats
- an ecosystem for multi-disciplinary simulation and analysis of a nuclear reactor

Demos of ARMI can be seen in the `ARMI example gallery <https://terrapower.github.io/armi/gallery/index.html>`_.

Using ARMI, plus a collection of ARMI-aware physics plugins, and engineering team can perform a full analysis of a
reactor with various input parameters. On larger compute clusters, thousands of perturbed cases are frequently run in
parallel. Such studies are useful for both design decisions and senstivity analyses.

ARMI aims to enhance the quality and rigor of computational nuclear reactor design and analysis. Additional high-level
information about this system can be found in [#touranarmi]_.


.. list-table:: Quick links
   :widths: 30 70

   * - Source code
     - https://github.com/terrapower/armi
   * - Documentation
     - https://terrapower.github.io/armi
   * - First time contributor's guide
     - https://terrapower.github.io/armi/developer/first_time_contributors.html
   * - Bug tracker
     - https://github.com/terrapower/armi/issues
   * - Plugin directory
     - https://github.com/terrapower/armi-plugin-directory
   * - Contact
     - armi-devs@terrapower.com


Overview
********

High-Level Architecture
=======================
Figure 1 below is meant to represent the high-level goal of ARMI. At the center of the diagram is the ARMI Reactor Data
Model, this is a central place in memory where the physical state of the reactor can be viewed and changed. The outer
ring of figure shows "external physics kernels", which have been written for different nuclear engineering disciplines
around the world for decades now. The glue that connects these external software packages to ARMI are "ARMI Plugins"
which you write, based on ARMI examples, to read and write data from the ARMI reactor data model. A collection of these
plugins can be collected into an ARMI "Application" which orchestrates simulating or analyzing your reactor.

.. figure:: https://terrapower.github.io/armi/_static/armiSchematicView.png
   :figclass: align-center

   **Figure 1.** A high-level view of the ARMI architecture as a framework.

Please note that ARMI does not come with a full selection of physics kernels. You will need to be acquire or develope
these yourself, for your specific needs. ARMI is just the framework for your modeling. Also, the examples shown in
Figure 1 were chosen arbitrarily; ARMI is not limited to these physics kernels, nor should it limit you in what physics
you want to model.


Getting Started
***************

Quick Start
===========
Before starting, you need to install `Python <https://www.python.org/downloads/>`.

Get the ARMI code, install the dependencies, and fire up the launcher with the following commands. You probably want to
do this in a virtual environment as described in the
`Installation documentation <https://terrapower.github.io/armi/installation.html>`_.

First, upgrade your version of pip::

    $ pip install -U pip>=22.1

Now clone and install ARMI::

    $ git clone https://github.com/terrapower/armi
    $ cd armi
    $ pip install -e .
    $ armi --help

The ARMI tests are meant to be run using `pytest <https://docs.pytest.org/en/8.0.x/>`_ locally::

    $ pip install -e ".[test]"
    $ pytest -n 4 armi

From here, we recommend going through a few of our
`gallery examples <https://terrapower.github.io/armi/gallery/index.html>`_ and
`tutorials <https://terrapower.github.io/armi/tutorials/index.html>`_ to start touring the features and capabilities and
then move on to the `User Manual <https://terrapower.github.io/armi/user/index.html>`_.

System Requirements
===================
Being largely written in the Python programming language, the ARMI system works on most platforms.  It can perform
meaningful analysis on a single laptop, but the full value of design optimization and large problems is realized with
parallel runs over large clusters (using MPI via  ``mpi4py``).


Misc
****

.. _getting-help:

Getting Help
============
You can get help with ARMI by either making issues on our `github page <https://github.com/terrapower/armi/issues>`_ or
by e-mailing armi-devs@terrapower.com.

Disclaimers
===========
Due to TerraPower goals and priorities, many ARMI modules were developed with the sodium-cooled fast reactors as a
target, and are not yet optimized for other plants. This is a known issue and we are working on it. On the other hand,
the framework is sufficiently general that teams have modeled other reactor types with ARMI, including thermal reactors.

ARMI is being developed and used within a rapidly-changing R&D environment. It has evolved a great deal, and naturally
carries some legacy. We are constantly on the look out for technical debt, and pay it off regularly. If you find some,
please make a ticket. Users should understand that ARMI is not a polished consumer product, but a flexible engineering
tool.

License
=======
TerraPower and ARMI are registered trademarks of TerraPower, LLC. Other trademarks and registered trademarks used in
this Manual are the property of the respective trademark holders.

The ARMI system is licensed as follows:

.. code-block:: none

  Copyright 2009 TerraPower, LLC

  Licensed under the Apache License, Version 2.0 (the "License");
  you may not use this file except in compliance with the License.
  You may obtain a copy of the License at

      http://www.apache.org/licenses/LICENSE-2.0

  Unless required by applicable law or agreed to in writing, software
  distributed under the License is distributed on an "AS IS" BASIS,
  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
  See the License for the specific language governing permissions and
  limitations under the License.


.. [#touranarmi] Touran, Nicholas W., et al. "Computational tools for the integrated design of advanced nuclear reactors."
   Engineering 3.4 (2017): 518-526. https://doi.org/10.1016/J.ENG.2017.04.016

.. |Build Status| image:: https://github.com/terrapower/armi/actions/workflows/unittests.yaml/badge.svg?branch=main
    :target: https://github.com/terrapower/armi/actions/workflows/unittests.yaml

.. |Code Coverage| image:: https://codecov.io/gh/terrapower/armi/branch/main/graph/badge.svg
    :target: https://app.codecov.io/gh/terrapower/armi/tree/main

.. |Commit Activity| image:: https://img.shields.io/github/commit-activity/m/terrapower/armi
    :target: https://github.com/terrapower/armi/pulse

.. |Good First Issues| image:: https://img.shields.io/github/issues/terrapower/armi/good%20first%20issue
    :target: https://github.com/terrapower/armi/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22
