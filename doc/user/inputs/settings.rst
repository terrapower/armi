***********************
The Settings Input File
***********************

The **settings** input file defines a series of key/value pairs the define various information about the system you are
modeling as well as which modules to run and various modeling/approximation settings. For example, it includes:

* The case title
* The reactor power
* The number of cycles to run
* Which physics solvers to activate
* Whether or not to perform a critical control search
* Whether or not to do tight coupling iterations
* What neutronics approximations specific to the chosen physics solver to apply
* Environment settings (paths to external codes)
* How many CPUs to use on a computer cluster

This file is a YAML file that you can edit manually with a text editor or with the ARMI GUI.

Here is an excerpt from a settings file:

.. literalinclude:: ../../../armi/tests/armiRun.yaml
    :language: yaml
    :lines: 3-15

A full listing of settings available in the framework may be found in the :doc:`Table of all global settings </user/inputs/settings_report>`.

Many settings are provided by the ARMI Framework, and others are defined by various plugins.

.. _armi-gui:

The ARMI GUI
============
The ARMI GUI may be used to manipulate many common settings (though the GUI can't change all of the settings).  The GUI
also enables the graphical manipulation of a reactor core map, and convenient automation of commands required to submit to a
cluster.  The GUI is a front-end to
these files. You can choose to use the GUI or not, ARMI doesn't know or care --- it just reads these files and runs them.

Note that one settings input file is required for each ARMI case, though many ARMI cases can refer to the same
Blueprints, Core Map, and Fuel Management inputs.

.. tip:: The ARMI GUI is not yet included in the open-source ARMI framework

The assembly clicker
--------------------
The assembly clicker (in the ``grids`` editor) allows users to define the 2-D layout of the assemblies defined in the
:doc:`/user/inputs/blueprints`. This can be done in hexagon or cartesian. The results of this arrangement get written to
grids in blueprints. Click on the assembly palette on the right and click on the locations where you want to put the
assembly. By default, the input assumes a 1/3 core model, but you can create a full core model through the menu.

If you want one assembly type to fill all positions in a ring, right click it once it is placed and choose ``Make ring
like this hex``. Once you submit the job or save the settings file (File -> Save), you will be prompted for a new name
of the geometry file before the settings file is saved. The geometry setting in the main tab will also be updated.

The ARMI Environment Tab
------------------------
The environment tab contains important settings about which version of ARMI you will run
and with which version of Python, etc. Most important is the ``ARMI location`` setting. This
points to the codebase that will run. If you want to run the released version of ARMI,
ensure that it is set in this setting. If you want to run a developer version, then be sure
to update this setting.

Other settings on this tab may need to be updated depending on your computational environment.
Talk to your system admins to determine which settings are best.

Some special settings
=====================
A few settings warrant additional discussion.

.. _detail-assems:

Detail assemblies
-----------------
Many plugins perform more detailed analysis on certain regions of the reactor. Since the analyses
often take longer, ARMI has a feature, called *detail assemblies* to help. Different plugins
may treat detail assemblies differently, so it's important to read the plugin documentation
as well. For example, a depletion plugin may perform pin-level depletion and rotation analysis
only on the detail assemblies. Or perhaps CFD thermal/hydraulics will be run on detail assemblies,
while subchannel T/H is run on the others.

Detail assemblies are specified by the user in a variety of ways,
through the GUI or the settings system.

.. warning:: The Detail Assemblies mechanism has begun to be too broad of a brush
    for serious multiphysics calculations with each plugin treating them differently.
    It is likely that this feature will be extended to be more flexible and less
    surprising in the future.

Detail Assembly Locations BOL
    The ``detailAssemLocationsBOL`` setting is a list of assembly location strings
    (e.g. ``004-003`` for ring 4, position 3). Assemblies that are in these locations at the
    beginning-of-life will be activated as detail assemblies.

Detail assembly numbers
    The ``detailAssemNums`` setting is a list of ``assemNum``\ s that can be inferred from a previous
    case and specified, regardless of when the assemblies enter the core. This is useful for
    activating detailed treatment of assemblies that enter the core at a later cycle.

Detail all assemblies
    The ``detailAllAssems`` setting makes all assemblies in the problem detail assemblies

.. _kinetics-settings:

Kinetics settings
-----------------
In reactor physics analyses it is standard practice to represent reactivity
in either absolute units (i.e., dk/kk' or pcm) or in dollars or cents. To
support this functionality, the framework supplies the ``beta`` and
``decayConstants`` settings to apply the delayed neutron fraction and
precursor decay constants to the Core parameters during initialization.

These settings come with a few caveats:

    1. The ``beta`` setting supports two different meanings depending on
       the type that is provided. If a single value is given, then this setting
       is interpreted as the effective delayed neutron fraction for the
       system. If a list of values is provided, then this setting is interpreted
       as the group-wise (precursor family) delayed neutron fractions (useful for
       reactor kinetics simulations).

    2. The ``decayConstants`` setting is used to define the precursor
       decay constants for each group. When set, it must be
       provided with a corresponding ``beta`` setting that has the
       same number of groups. For example, if six-group delayed neutron
       fractions are provided, the decay constants must also be provided
       in the same six-group structure.

    3. If ``beta`` is interpreted as the effective delayed neutron fraction for
       the system, then the ``decayConstants`` setting will not be utilized.

    4. If both the group-wise ``beta`` and ``decayConstants`` are provided
       and their number of groups are consistent, then the effective delayed
       neutron fraction for the system is calculated as the summation of the
       group-wise delayed neutron fractions.

.. _cycle-history:

Cycle history
-------------
For all cases, ``nCycles`` and ``power`` must be specified by the user.
In the case that only a single state is to be examined (i.e. no burnup), the user need only additionally specify ``nCycles = 1``.

In the case of burnup, the reactor cycle history may be specified using either the simple or detailed
option.
The simple cycle history consists of the following case settings:
    
    * ``power``
    * ``nCycles`` (default = 1)
    * ``burnSteps`` (default = 4)
    * ``availabilityFactor(s)`` (default = 1.0)
    * ``cycleLength(s)`` (default = 365.2425)

In addition, one may optionally use the ``powerFractions`` setting to change the reactor
power between each cycle.
With these settings, a user can define a history in which each cycle may vary
in power, length, and uptime.
The history is restricted, however, to each cycle having a constant power, to
each cycle having the same number of burnup nodes, and to those burnup nodes being
evenly spaced within each cycle.
An example simple cycle history might look like

.. code-block:: yaml

       power: 1000000
       nCycles: 3
       burnSteps: 2
       cycleLengths: [100, R2]
       powerFractions: [1.0, 0.5, 1.0]
       availabilityFactors: [0.9, 0.3, 0.93]

Note the use of the special shorthand list notation, where repeated values in a list can be specified using an "R" followed by the number of times the value is to be repeated.

The above scheme would represent 3 cycles of operation:
    
    1. 100% power for 90 days, split into two segments of 45 days each, followed by 10 days shutdown (i.e. 90% capacity)

    2. 50% power for 30 days, split into two segments of 15 days each, followed by 70 days shutdown (i.e. 15% capacity)

    3. 100% power for 93 days, split into two segments of 46.5 days each, followed by 7 days shutdown (i.e. 93% capacity)

In each cycle, criticality calculations will be performed at 3 nodes evenly-spaced through the uptime portion of the cycle (i.e. ``availabilityFactor``*``powerFraction``), without option for changing node spacing or frequency.
This input format can be useful for quick scoping and certain types of real analyses, but clearly has its limitations.

To overcome these limitations, the detailed cycle history, consisting of the ``cycles`` setting may be specified instead.
For each cycle, an entry to the ``cycles`` list is made with the following optional fields: 
    
    * ``name``
    * ``power fractions``
    * ``cumulative days``, ``step days``, or ``burn steps`` + ``cycle length``
    * ``availability factor``

An example detailed cycle history employing all of these fields could look like

.. code-block:: yaml

       power: 1000000
       nCycles: 4
       cycles:
         - name: A
           step days: [1, 1, 98]
           power fractions: [0.1, 0.2, 1]
           availability factor: 0.1
         - name: B
           cumulative days: [2, 72, 78, 86]
           power fractions: [0.2, 1.0, 0.95, 0.93]
         - name: C
           step days: [5, R5]
           power fractions: [1, R5]
         - cycle length: 100
           burn steps: 2
           availability factor: 0.9

Note that repeated values in a list may be again be entered using the shorthand notation for ``step days``, ``power fractions``, and ``availability factors`` (though not ``cumulative days`` because entries must be monotonically increasing).

Such a scheme would define the following cycles:

    1. A 2 day power ramp followed by full power operations for 98 days, with three nodes clustered during the ramp and another at the end of the cycle, followed by 900 days of shutdown

    2. A 2 day power ramp followed by a prolonged period at full power and then a slight power reduction for the last 14 days in the cycle

    3. Constant full-power operation for 30 days split into six even increments

    4. Constant full-power operation for 90 days, split into two equal-length 45 day segments, followed by 10 days of downtime

As can be seen, the detailed cycle history option provides much greated flexibility for simulating realistic operations, particularly power ramps or scenarios that call for unevenly spaced burnup nodes, such as xenon buildup in the early period of thermal reactor operations.

.. note:: Although the detailed cycle history option allows for powers to change within each cycle, it should be noted that the power over each step is still considered to be constant.

.. note:: The detailed cycle history may not be used for equilibrium calculations at this time.

.. note:: The ``name`` field of the detailed cycle history is not yet used for anything, but this information will still be accessible on the operator during runtime.

.. note:: Cycles without names will be given the name ``None``

.. _restart-cases:

Restart cases
-------------

Oftentimes the user is interested in re-examining just a specific set of time nodes from an existing run.
In these cases, it is sometimes not necessary to rerun an entire reactor history, and one may instead use one of the following options:
    
    1. Snapshot, where the reactor state is loaded from a database and just a single time node is run.

    2. Restart, where the cycle history is loaded from a database and the calculation continues through the remaining specified time history.

For either of these options, it is possible to alter the specific settings applied to the run by simply adjusting the case settings for the run.
For instance, a run that originally had only neutronics may incorporate thermal hydraulics during a snapshot run by adding in the relevant TH settings.

.. note:: For either of these options, it is advisable to first create a new case settings file with a name different than the one from which you will be restarting off of, so as to not overwrite those results.

To run a snapshot, the following settings must be added to your case settings:

    * Set ``runType`` to ``Snapshots``
    * Add a list of cycle/node pairs corresponding to the desired snapshots to ``dumpSnapshot`` formatted as ``'CCCNNN'``
    * Set ``reloadDBName`` to the existing database file that you would like to load the reactor state from

An example of a snapshot run input:

.. code-block:: yaml
       
       runType: Snapshots
       reloadDBName: my-old-results.h5
       dumpSnapshot: ['000000', '001002'] # would produce 2 snapshots, at BOL and at node 2 of cycle 1

To run a restart, the following settings must be added to your case settings:

    * Set ``runType`` to ``Standard``
    * Set ``loadStyle`` to ``fromDB``
    * Set ``startCycle`` and ``startNode`` to the cycle/node that you would like to continue the calculation from (inclusive). 
    ``startNode`` may use negative indexing.
    * Set ``reloadDBName`` to the existing database file from which you would like to load the reactor history up to the restart point
    * If you would like to change the specified reactor history (see :ref:`restart-cases`), keep the history up to the restarting cycle/node
    unchanged, and just alter the history after that point. This means that the cycle history specified in your restart run should include
    all cycles/nodes up to the end of the simulation. For complicated restarts, it
    may be necessary to use the detailed ``cycles`` setting, even if the original case only used the simple history option.

A few examples of restart cases:
    
    - Restarting a calculation at a specific cycle/node and continuing for the remainder of the originally-specified cycle history:
        .. code-block:: yaml
               
               # old settings
               nCycles: 2
               burnSteps: 2
               cycleLengths: [100, 100]
               runType: Standard
               loadStyle: fromInput
               loadingFile: my-blueprints.yaml

        .. code-block:: yaml
            
               # restart settings
               nCycles: 2
               burnSteps: 2
               cycleLengths: [100, 100]
               runType: Standard
               loadStyle: fromDB
               startCycle: 1
               startNode: 0
               reloadDBName: my-original-results.h5

    - Add an additional cycle to the end of a case:
        .. code-block:: yaml
            
               # old settings
               nCycles: 1
               burnSteps: 2
               cycleLengths: [100]
               runType: Standard
               loadStyle: fromInput
               loadingFile: my-blueprints.yaml

        .. code-block:: yaml
            
               # restart settings
               nCycles: 2
               burnSteps: 2
               cycleLengths: [100, 100]
               runType: Standard
               loadStyle: fromDB
               startCycle: 0
               startNode: -1
               reloadDBName: my-original-results.h5

    - Restart but cut the reactor history short:
        .. code-block:: yaml
            
               # old settings
               nCycles: 3
               burnSteps: 2
               cycleLengths: [100, 100, 100]
               runType: Standard
               loadStyle: fromInput
               loadingFile: my-blueprints.yaml

        .. code-block:: yaml
            
               # restart settings
               nCycles: 2
               burnSteps: 2
               cycleLengths: [100, 100]
               runType: Standard
               loadStyle: fromDB
               startCycle: 1
               startNode: 0
               reloadDBName: my-original-results.h5

    - Restart with a different number of steps in the third cycle using the detailed ``cycles`` setting:
        .. code-block:: yaml
            
               # old settings
               nCycles: 3
               burnSteps: 2
               cycleLengths: [100, 100, 100]
               runType: Standard
               loadStyle: fromInput
               loadingFile: my-blueprints.yaml

        .. code-block:: yaml
            
               # restart settings
               nCycles: 3
               cycles:
                 - cycle length: 100
                   burn steps: 2
                 - cycle length: 100
                   burn steps: 2
                 - cycle length: 100
                   burn steps: 4
               runType: Standard
               loadStyle: fromDB
               startCycle: 2
               startNode: 0
               reloadDBName: my-original-results.h5

.. note:: The ``skipCycles`` setting is related to skipping the lattice physics calculation specifically, it is not required to do a restart run.

.. note:: The *-SHUFFLES.txt file is required to do explicit repeated fuel management.

.. note:: The restart.dat file is required to repeat the exact fuel management methods during a branch search. These can potentially modify the reactor state in ways that cannot be captures with the SHUFFLES.txt file.

.. note:: The ISO* binary cross section libraries are required to run cases that skip the lattice physics calculation (e.g. MC**2)

.. note:: The multigroup flux is not yet stored on the output databases. If you need to do a restart with these values (e.g. for depletion), then you need to reload from neutronics outputs.

.. note:: Restarting a calculation with an different version of ARMI than what was used to produce the restarting database may result in undefined behavior.