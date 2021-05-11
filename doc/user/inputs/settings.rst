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

A full listing of settings may be found in the :doc:`Table of all global settings </user/inputs/settings_report>`.

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

The assembly dragger
--------------------
The assembly dragger (in the ``Geometry`` tab) allows users to define the 2-D layout of the assemblies defined in the
:doc:`/user/inputs/blueprints`. It is currently limited to hexagons. The results of this arrangement get written to
:doc:`/user/inputs/facemap_file`. Drag hexagons from the options on the right and place them into the core positions you
want them to be in. By default, the input assumes a 1/3 core model, but you can create a full core model through the
menu.

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
