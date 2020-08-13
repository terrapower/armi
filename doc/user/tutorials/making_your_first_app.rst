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
    need to ensure your ``PYTHON_PATH`` variable includes the armi installation directory.

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
        setup.py
        README.md
        LICENSE.md


These files are:

* The outer :file:`my_armi_project` root directory is a container for your app. The name
  does not matter to ARMI; you can rename it to anything.

* The inner :file:`myapp` directory is the actual Python package for your app. Its name is
  the Python package name you will use to import anything inside (e.g. ``myapp.plugin``).

* :file:`myapp/__init__.py` tells Python that this directory is a Python package and
  performs any app-specific configurations 

* :file:`myapp/__main__.py` registers the application with the ARMI framework
  and provides one or more entry points for users of your app (including you!)
  to start running it.

* :file:`myapp/app.py` contains the actual app registration code that will be called by
  :file:`__init__.py`. This can be named anything as long as it is consistent with the
  registration code in :file:`myapp/__init__.py`. 

* :file:`myapp/plugin.py` contains the code that defines the physics plugins we will create

* :file:`myapp/fluxSolver.py` contains the flux solver

* :file:`myapp/thermalSolver.py` contains the thermal/hydraulics solver

* :file:`setup.py` the `python package installation file
  <https://docs.python.org/3/distutils/setupscript.html>`_ to help users install your
  application.

* :file:`README.md` and :file:`LICENSE.md` are an optional description and license of your
  application that would be prominently featured, e.g. in a github repo, if you were to
  put it there.

Registering the app with ARMI
=============================
The ARMI Framework contains features to run the "main loop" of typical applications. In
order to get access to these, we must register our new app with the ARMI framework. To do
this, we put the following code in the top-level :file:`__main__.py` module:

.. code-block:: python
    :caption: ``myapp/__main__.py``

    import armi
    from myapp import app
    armi.configure(app.ExampleApp())

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

.. code-block:: python
    :caption: ``myapp/app.py``

    import armi
    from armi.apps import App

    from myapp.plugin import DummyPhysicsPlugin

    class ExampleApp(App):
        def __init__(self):
            # activate all built-in plugins
            App.__init__(self)

            # register our plugin with the plugin manager
            self._pm.register(DummyPhysicsPlugin) 

        @property
        def splashText(self):
            return "** My Example App **"


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
    structure of the ARMI framework :py:mod:`physics plugin subpackage <armi.physics>`.

We will start the plugin by pointing to the two physics kernels we wish to register. We
hook them in and tell ARMI the ``ORDER`` they should be run in based on the built-in
``STACK_ORDER`` attribute (defined and discussed :py:class:`here
<armi.interfaces.STACK_ORDER>`).  We will come back to this plugin definition later on to
add a little more to the plugin.



.. code-block:: python
    :caption: ``myapp/plugin.py``

    from armi import plugins
    from armi import interfaces
    from armi.interfaces import STACK_ORDER as ORDER

    from myapp import fluxSolver
    from myapp import thermalSolver


    class DummyPhysicsPlugin(plugins.ArmiPlugin):
        @staticmethod
        @plugins.HOOKIMPL
        def exposeInterfaces(cs):
            kernels = [
                interfaces.InterfaceInfo(ORDER.FLUX, fluxSolver.FluxInterface, {}),
                interfaces.InterfaceInfo(ORDER.THERMAL_HYDRAULICS, thermalSolver.ThermalInterface, {}),
            ]
            return kernels

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

.. code-block:: python
    :caption: ``myapp/fluxSolver.py``

    import os

    import numpy as np

    from armi import runLog
    from armi import interfaces
    from armi.physics import neutronics


    class FluxInterface(interfaces.Interface):
        name = "dummyFlux"

        def interactEveryNode(self, cycle=None, timeNode=None):
            runLog.info("Computing neutron flux and power.")
            setFakePower(self.r.core)


    def setFakePower(core):
        midplane = core[0].getHeight()/2.0
        center = np.array([0,0,midplane])
        peakPower = 1e6
        mgFluxBase = np.arange(5)
        for a in core:
            for b in a:
                vol = b.getVolume()
                coords = b.spatialLocator.getGlobalCoordinates()
                r = np.linalg.norm(abs(coords-center))
                fuelFlag = 10 if b.isFuel() else 1.0
                b.p.power = peakPower / r**2 * fuelFlag
                b.p.pdens = b.p.power/vol
                b.p.mgFlux = mgFluxBase*b.p.pdens


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

    q''' = \dot{m} C_p \Delta T

.. code-block:: python
    :caption: ``myapp/thermalSolver.py``

    from armi import interfaces
    from armi.reactor.flags import Flags
    from armi import runLog

    # hard coded inlet/outlet temperatures
    # NOTE: can make these user settings
    inletInC = 360.0
    outletInC = 520.0

    class ThermalInterface(interfaces.Interface):
        name = "dummyTH"

        def interactEveryNode(self, cycle=None, timeNode=None):
            runLog.info("Computing idealized flow rate")
            for assembly in self.r.core:
                runThermalHydraulics(assembly)

    def runThermalHydraulics(assembly):
        massFlow = computeIdealizedFlow(assembly)
        computeAxialCoolantTemperature(assembly, massFlow)

    def computeIdealizedFlow(a):

        # compute required mass flow rate in assembly to reach target outlet temperature
        # mass flow rate will be constant in each axial region, regardless of coolant
        # area (velocity may change)
        coolants = a.getComponents(Flags.COOLANT)
        coolantMass = sum([c.getMass() for c in coolants])

        # use ARMI material library to get heat capacity for whatever the user has
        # defined the coolant as
        tempAvg = (outletInC + inletInC)/2.0
        coolantProps = coolants[0].getProperties()
        heatCapacity = coolantProps.heatCapacity(Tc=tempAvg)

        deltaT = outletInC - inletInC
        massFlowRate = a.calcTotalParam('power')/(deltaT * heatCapacity)
        return massFlowRate

    def computeAxialCoolantTemperature(a, massFlow):
        """Compute block-level coolant inlet/outlet/avg temp and velocity."""
        # solve q''' = mdot * Cp * dT for dT this time
        inlet = inletInC
        for b in a:
            b.p.THcoolantInletT = inlet
            coolant = b.getComponent(Flags.COOLANT)
            coolantProps = coolant.getProperties()
            heatCapacity = coolantProps.heatCapacity(Tc = inlet)
            deltaT = b.p.power/(massFlow * heatCapacity)
            outlet = inlet + deltaT
            b.p.THcoolantOutletT = outlet
            b.p.THcoolantAverageT = (outlet + inlet)/2.0
            # fun fact: could iterate on this to get
            # heat capacity properties updated better
            # get flow velocity too
            # V [m/s] = mdot [kg/s] / density [kg/m^3] / area [m^2] 
            b.p.THaveCoolantVel = (
                massFlow /
                coolantProps.density(Tc=b.p.THcoolantAverageT) /
                coolant.getArea() * 100**2
            )
            inlet=outlet

Adding entry points
===================
In order to call our application directly, we need to add the :file:`__main__.py` file to
the package. We could add all manner of :py:mod:`entry points <armi.cli.entryPoint>` here
for different operations we want our application to perform. If you want to add your own
entry points, you have to register them with the
:py:meth:`armi.plugins.ArmiPlugin.defineEntryPoints` hook. For now, we can just inherit
from the default ARMI entry points (including ``run``) by adding the following code:

.. code-block:: python
    :caption: ``myapp/__main__.py``

    import sys
    from armi.cli import ArmiCLI

    def main():
        code = ArmiCLI().run()
        sys.exit(code)

    if __name__ == "__main__":
        main()


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

Make a run directory with some input files in it. You can use the same SFR input files
we've used in previous tutorials for starters (but quickly transition to your own inputs
for your own interests!)

Here are the files you can download into the run directory.

* :download:`Blueprints <../../../armi/tests/tutorials/anl-afci-177-blueprints.yaml>`
* :download:`Settings <../../../armi/tests/tutorials/anl-afci-177.yaml>`
* :download:`Core map <../../../armi/tests/tutorials/anl-afci-177-coreMap.yaml>`
* :download:`Fuel management <../../../armi/tests/tutorials/anl-afci-177-fuelManagement.py>`


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

.. code-block:: python
    :caption: ``myapp/materials.py``

    from armi import materials
    from armi.utils.units import getTc

    class Sodium(materials.Sodium):
        def heatCapacity(self, Tk=None, Tc=None):
            """Sodium heat capacity in J/kg-K"""
            Tc = getTc(Tc,Tk)
            # not even temperature dependent for now
            return 1.252

But wait! Now there are **two** materials with the name *Sodium* in ARMI. Which will be
chosen? ARMI uses a namespace order controlled by
:py:func:`armi.materials.setMaterialNamespaceOrder` which can be set either
programmatically (in an app) or at runtime (via the ``materialNamespaceOrder`` user
setting). In our case, we want to set it at the app level, so we will add the following to
the :file:`myapp/__init__.py` file:

.. code-block:: python
    :caption: Addition to ``myapp/__init__.py``

    from armi import materials
    materials.setMaterialNamespaceOrder(
        ["myapp.materials", "armi.materials"]
    )

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

.. admonition:: Is there a general DB viewer?

    TerraPower uses an internal HDF5 viewer called *XTVIEW* to view the state in the HDF5
    database. At some point this tool will either be made available, or we or someone else
    will create a plugin for a more generic visualization tools like VisIT or Paraview.
    For now you are stuck exploring the HDF5 output via the ARMI API. 

A generic description of the outputs is provided in :doc:`/user/outputs/index`. 

You can add your own outputs from your plugins.
