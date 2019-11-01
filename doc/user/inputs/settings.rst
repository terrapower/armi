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

The ARMI GUI
============
The ARMI GUI may be used to manipulate many common settings (though the GUI can't change all of the settings).  The GUI
also enables the graphical manipulation of a reactor core map, and convenient automation of commands required to submit to a
cluster.  The GUI is simply a front-end to
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
