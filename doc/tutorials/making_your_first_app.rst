..
    Note that this file makes use of Python files in a ``armi-example-app`` folder
    so that they can be put under testing.

================================
Making your first ARMI-based App
================================

In this tutorial we will build a nuclear analysis application that runs (dummy) neutron
flux and thermal/hydraulics calculations. Applications that do real analysis can be
modeled after this starting point.

We'll assume you have the :doc:`ARMI Framework installed </user/user_install>` already.
You can make sure it is ready by running the following command in a shell prompt::

    (armi) $ python -c "import armi;armi.configure()"

You should see an ARMI splash-screen and an ARMI version print out. If you do, you are ready
to proceed.

.. tip:: If you are having trouble getting it installed, see :ref:`getting-help`. You may
    need to ensure your ``PYTHONPATH`` variable includes the armi installation directory.

.. note:: This tutorial is a companion for the :doc:`/developer/making_armi_based_apps`
    developer documentation.

Starting a new app
==================
ARMI-based applications can take on many forms, depending on your workflow. Examples may include:

* Application and plugins together under one folder
* Application in one folder, plugins in separate ones

We will build an application that contains one plugin that runs
neutronics and thermal hydraulics in one folder. This architecture will be a good starting
point for many projects, and can always be separated if needed.

From the command line, ``cd`` into a new directory where you'd like to store your
application code. Make a folder structure that works as a `normal Python package
<https://packaging.python.org/tutorials/packaging-projects/>`_, and create some empty
files for us to fill in, like this::

    my_armi_project/
        myapp/
            __init__.py
            __main__.py
            app.py
            plugin.py
            fluxSolver.py
            thermalSolver.py
        doc/
        setup.py
        README.md
        LICENSE.md


These files are:

* The outer :file:`my_armi_project` root directory is a container for your app. The name
  does not matter to ARMI; you can rename it to anything.

* The inner :file:`myapp` directory is the actual Python package for your app. Its name is
  the Python package name you will use to import anything inside (e.g. ``myapp.plugin``).

* :file:`myapp/__init__.py` tells Python that this directory is a Python package. Code
  in here runs whenever anything in the package is imported.

* :file:`myapp/__main__.py` registers the application with the ARMI framework
  and provides one or more entry points for users of your app (including you!)
  to start running it. Since code here runs when the package is used as a
  main, it generally performs any app-specific configuration.

* :file:`myapp/app.py` contains the actual app registration code that will be called by
  :file:`__main__.py`. This can be named anything as long as it is consistent with the
  registration code.

* :file:`myapp/plugin.py` contains the code that defines the physics plugins we will create

* :file:`myapp/fluxSolver.py` contains the flux solver

* :file:`myapp/thermalSolver.py` contains the thermal/hydraulics solver

* :file:`setup.py` the `python package installation file
  <https://docs.python.org/3/distutils/setupscript.html>`_ to help users install your
  application.

* :file:`README.md` and :file:`LICENSE.md` are an optional description and license of your
  application that would be prominently featured, e.g. in a GitHub repo, if you were to
  put it there.

* :file:`doc/` is an optional folder where your application documentation source may go.
  If you choose to use Sphinx you can run ``sphinx-quickstart` in that folder to begin
  documentation.

Registering the app with ARMI
=============================
The ARMI Framework contains features to run the "main loop" of typical applications. In
order to get access to these, we must register our new app with the ARMI framework. To do
this, we put the following code in the top-level :file:`__main__.py` module:

.. literalinclude:: armi-example-app/myapp/__main__.py
    :language: python
    :caption: ``myapp/__main__.py``
    :start-after: tutorial-configure-start
    :end-before: tutorial-configure-end

Similar code will be needed in scripts or other code where you would like your app to be used.

.. tip:: You may find it appropriate to use the plugin registration mechanism in some cases
    rather than the app registration. More info on plugins vs. apps coming soon.

Defining the app class
======================
We define our app in the :file:`myapp/app.py` module. For this example, the app class is
relatively small: it will just register our one custom plugin. We will actually create
the plugin shortly.

.. admonition:: Apps vs. plugins vs. interfaces

    ARMI-based methodologies are broken down into three layers of abstraction. Apps are
    collections of plugins intended to perform analysis on a certain type of reactor.
    Plugins are independent and mixable collections of relatively arbitrary code that
    might bring in special materials, contain certain engineering methodologies, and/or
    Interfaces with one or more physics kernels. See :doc:`/developer/guide` for more
    info on architecture.

.. literalinclude:: armi-example-app/myapp/app.py
    :language: python
    :caption: ``myapp/app.py``


Defining the physics plugin
===========================
Now we will create the plugin that will coordinate our dummy physics modules.

.. admonition:: What are plugins again?

    Plugins are the basic modular building block of ARMI-based apps. In some cases, one
    plugin will be associated with one physics kernel (like COBRA or MCNP). This is a
    reasonable practice when you expect to be mixing and matching various combinations of
    plugins between related teams. It is also possible to have a plugin that performs a
    whole cacophony of analyses using multiple codes, which some smaller research teams
    may find preferable. The flexibility is very broad.

    See :py:mod:`armi.plugins` more for info.

Plugin code can exist in any directory structure in an app. In this app we
put it in the :file:`myapp/plugin.py` file.

.. note:: For "serious" plugins, we recommend mirroring the ``armi/physics/[subphysics]``
    structure of the ARMI Framework :py:mod:`physics plugin subpackage <armi.physics>`.

We will start the plugin by pointing to the two physics kernels we wish to register. We
hook them in and tell ARMI the ``ORDER`` they should be run in based on the built-in
``STACK_ORDER`` attribute (defined and discussed :py:class:`here
<armi.interfaces.STACK_ORDER>`).  We will come back to this plugin definition later on to
add a little more to the plugin.


.. literalinclude:: armi-example-app/myapp/plugin.py
    :caption: ``myapp/plugin.py``
    :language: python


Creating the physics kernels
============================
So far we have basically been weaving an administrative thread to tell ARMI about the code
we want to run. Now we finally get to write the guts of the code that actually does
something. In your real app, this code will run your own industrial or research code, or
perform your own methodology.  Here we just have it make up dummy values representing flux
and temperatures.

Making the (dummy) flux kernel
------------------------------
In a previous tutorial, we made a function that sets a dummy flux to all parts of the core
based on a radial distance from the origin. Here we will re-use that code but package it
more formally so that ARMI can actually run it for us from a user perspective.

The interface is responsible largely for scheduling activities to run at various time
points. For a flux calculation, we want it to compute at every single time node, so we use
the :py:meth:`armi.interfaces.Interface.interactEveryNode` hook.

These interaction hooks can call arbitrarily complex code. The code could, for example:

* Run an external executable locally
* Submit an external code to a cloud HPC and wait for it to complete
* Run an internal physics tool

Here it just does a tiny bit of math locally.

.. literalinclude:: armi-example-app/myapp/fluxSolver.py
    :caption: ``myapp/fluxSolver.py``
    :language: python



Making the thermal/hydraulics kernel
------------------------------------------
Since we told the ARMI plugin to schedule the flux solver before thermal/hydraulics solver
via the ``ORDER`` attribute, we can depend on there being up-to-date block-level ``power``
state data loaded onto the ARMI reactor by the time this thermal/hydraulics solver gets
called by the ARMI main loop.

We'll make a somewhat meaningful (but still totally academic) flow solver here that uses
energy conservation to determine an idealized coolant flow rate. To do this it will
compute the total power produced by each assembly to get the required mass flow rate and
then apply that mass flow rate from the bottom of the assembly to the top, computing a
block-level temperature (and flow velocity) distribution as we go.

.. math::

    \dot{Q} = \dot{m} C_p \Delta T

.. literalinclude:: armi-example-app/myapp/thermalSolver.py
    :caption: ``myapp/thermalSolver.py``
    :language: python



Adding entry points
===================
In order to call our application directly, we need to add the :file:`__main__.py` file to
the package. We could add all manner of :py:mod:`entry points <armi.cli.entryPoint>` here
for different operations we want our application to perform. If you want to add
:doc:`your own entry points </developer/entrypoints>`, you have to register them with the
:py:meth:`armi.plugins.ArmiPlugin.defineEntryPoints` hook. For now, we can just inherit
from the default ARMI entry points (including ``run``) by adding the following code
to what we already have in :file:`myapp/__main__.py`:

.. literalinclude:: armi-example-app/myapp/__main__.py
    :language: python
    :caption: ``myapp/__main__.py``
    :start-after: tutorial-entry-point-start
    :end-before: tutorial-entry-point-end

.. tip:: Entry points are phenomenal places to put useful analysis scripts
    that are limited in scope to the scope of the application.

Running the app and debugging
=============================
We are now ready to execute our application. Even though it still contains an issue, we
will run it now to get a feel for the iterative debugging process (sometimes lovingly
called ARMI whack-a-mole).

We must make sure our ``PYTHONPATH`` contains both the armi framework itself as well as
the directory that contains our app. For testing, an example value for this might be::

    $ export PYTHONPATH=/path/to/armi:/path/to/my_armi_project

.. admonition:: Windows tip

    If you're using Windows, the slashes will be the other way, you use ``set`` instead of
    ``export``, and you use ``;`` to separate entries (or just use the GUI).

.. admonition:: Submodule tip

    In development, we have found it convenient to use git submodules to contain the armi
    framework and pointers to other plugins you may need. If you do this, you can set
    the ``sys.path`` directly in the ``__main__`` file and not have to worry about
    ``PYTHONPATH`` nearly as much.


Make a run directory with some input files in it. You can use the same SFR input files
we've used in previous tutorials for starters (but quickly transition to your own inputs
for your own interests!).

Here are the files you can download into the run directory.

* :download:`Blueprints <../../armi/tests/tutorials/anl-afci-177-blueprints.yaml>`
* :download:`Settings <../../armi/tests/tutorials/anl-afci-177.yaml>`
* :download:`Core map <../../armi/tests/tutorials/anl-afci-177-coreMap.yaml>`
* :download:`Fuel management <../../armi/tests/tutorials/anl-afci-177-fuelManagement.py>`


Then, run your app!::

    (armi) $ python -m myapp run anl-afci-177.yaml

The code will run for a while and you will see your physics plugins in the interface
stack, but will run into an error::

    NotImplementedError: Material Sodium does not implement heatCapacity

The included academic Sodium material in the ARMI material library doesn't have any heat
capacity! Here we can either add heat capacity to the material and submit a pull request
to include it in the ARMI Framework (preferred for generic things), or make our own
material and register it through the plugin.

.. admonition:: Yet another way

    You could alternatively make a separate plugin that only has your team's special
    material properties.

Adding a new material
---------------------
Let's just add a subclass of sodium in our plugin that has a heat capacity defined. Make
your new material in a new module called :file:`myapp/materials.py`:

.. literalinclude:: armi-example-app/myapp/materials.py
    :caption: ``myapp/materials.py``
    :language: python

But wait! Now there are **two** materials with the name *Sodium* in ARMI. Which will be
chosen? ARMI uses a namespace order controlled by
:py:func:`armi.materials.setMaterialNamespaceOrder` which can be set either
programmatically (in an app) or at runtime (via the ``materialNamespaceOrder`` user
setting). In our case, we want to set it at the app level, so we will yet again add
more to the :file:`myapp/__main__.py` file:

.. literalinclude:: armi-example-app/myapp/__main__.py
    :language: python
    :caption: ``myapp/__main__.py``
    :start-after: tutorial-material-start
    :end-before: tutorial-material-end


.. admonition:: Why ``__main__.py``?

    We put this line in ``__main__.py`` rather than ``__init__.py`` so it only activates
    when we're explicitly running our app. If we put it in ``__init__`` it would
    change the order even in situations where code from anywhere within our app
    was imported, possibly conflicting with another app's needs.


Now ARMI should find our new updated Sodium material and get past that error.  Run it once
again::

    (armi) $ python -m myapp run anl-afci-177.yaml

.. tip:: You may want to pipe the output to a log file for convenient viewing with
    a command like ``python -m myapp run anl-afci-177.yaml > run.stdout``

Checking the output
===================
Several output files should have been created in the run directory from that past command.
Most important is the ``anl-afci-177.h5`` HDF5 binary database file. You can use this file
to bring the ARMI state back to any state point from the run for analysis.

To vizualize the output in a 3D graphics program like `ParaView <https://www.paraview.org/Wiki/ParaView>`_
or `VisIT <https://wci.llnl.gov/simulation/computer-codes/visit>`_,
you can run the ARMI ``vis-file`` entry point, like this::

    (armi) $ python -m myapp vis-file -f vtk anl-afci-177.h5

This creates several ``VTK`` files covering different time steps and levels of abstraction
(assembly vs. block params). If you load up the block file and plot one of the output
params (such as ``THcoolantAverageT`` you can see the outlet temperature going nicely
from 360 |deg|\ C  to 510 |deg|\ C (as expected given our simple TH solver).


.. figure:: /.static/anl-acfi-177-coolant-temperature.jpg
    :alt: The coolant temperature as seen in ParaView viewing the VTK file.
    :align: center

    The coolant temperature as seen in ParaView viewing the VTK file.


.. admonition:: Fancy XDMF format

    The ``-f xdmf`` produces `XDMF files <http://xdmf.org/index.php/XDMF_Model_and_Format>`_
    that are lighter-weight than VTK, just pointing the visualization
    program to the data in the primary ARMI HDF5 file. However it is slightly more
    finicky and has slightly less support in some tools (looking at VisIT).

A generic description of the outputs is provided in :doc:`/user/outputs/index`.

You can add your own outputs from your plugins.

.. |deg| unicode:: U+00B0
