**********************
Making ARMI-based Apps
**********************

Loading a reactor into the ARMI Framework is just the first step in pushing the envelope
of reactor design and analysis. Activating a powerful collection of plugins and
interfaces to automate your work is the next step to unlocking ARMI's potential.

.. admonition:: Heads up

    A full :doc:`tutorial on making an ARMI-based app is here
    </tutorials/making_your_first_app>`.

To really make ARMI your own, you will need to understand a couple of concepts that
enable developers to adapt and extend ARMI to their liking:

* **Plugins**: An ARMI plugin is a collection of code that registers new functionality
  with the ARMI Framework. This can include new Interfaces, Settings, Parameter
  definitions, custom Components, Materials, Operators, and others. For a more complete
  reference, see the :py:mod:`Plugin API <armi.plugins>` documentation. It is typical
  for a plugin to provide related components to some specific type of physics or a
  specific external physics code or the like. Keeping the scope of a plugin limited
  helps users to understand where all of their settings and interfaces and parameters
  are coming from.

* **ARMI-Based Applications**: A collection of plugins, along with application-specific
  customizations, working together with the ARMI Framework constitutes an "ARMI-Based
  Application". As an example, the TerraPower proprietary tool for modeling and
  analyzing sodium-cooled fast reactors is just such an application. It is from an
  Application that ARMI gets its collection of active plugins, which in turn dictate
  much of the ARMI Framework's behavior.

Both of these concepts are discussed in depth below.

------------
ARMI Plugins
------------

An ARMI Plugin is the primary means by which a developer or qualified analyst can go
about building specific capability on top of the ARMI Framework. Even some of the
functionalities that ship with the Framework are implemented internally using the Plugin
system! The :py:mod:`armi.plugins` module contains all of the plugin "hook" definitions
and their associated documentation. It is recommended to peruse those docs before
getting started to get an idea of what is available.

.. admonition:: Setting expectations

   The Plugin API is relatively new, and is expected to change and evolve. We hope at
   some point to mark parts of the API as stable, but we simply are not there yet. A
   stable Plugin API is a major goal for a v1.0 release.

   It is important to mention that the original Plugin API was designed to enable the
   separation of the Framework from TerraPower's internal code suite. Effort has been made
   to design the Plugin API to be general, and to anticipate future needs.  However, we
   expect that the API has plenty of room for improvement and extension. If you find
   yourself needing additional means of customization, or if any of the semantics of the
   Plugin API are causing you problems, please open an issue and we would be happy to work
   with you to improve it.

Some implementation details
---------------------------
One can just monkey-see-monkey-do their own plugins without fully understanding the
following. However, having a deeper understanding of what is going on may be useful.
Feel free to skip this section.

The plugin system is built on top of a Python library called `pluggy
<https://github.com/pytest-dev/pluggy>`_. Unless you plan on doing development within
the ARMI Framework itself, it is unlikely that you will need to be overly familiar with
it, but understanding how it works may be beneficial.

Looking at the code in :py:class:`armi.plugins.ArmiPlugin`, you might notice that all of
the methods are decorated with ``@HOOKSPEC`` (short for "hook specification"); this is
how the Framework itself defines the interfaces that a plugin implementation can
provide.  This is a feature of ``pluggy``. You might also notice that all of the methods
are **static methods**. This is because we do not actually expect an instance of an
``ArmiPlugin``; rather, we currently only use the class as a namespace to collect
whatever hook implementations a Plugin provides. While ``pluggy`` is happy with any
Python namespace containing hook implementations (e.g. module, class, object, function,
etc.), we chose to make a base ``ArmiPlugin`` class for a couple of reasons:

 - Wrapping the specifications in a class allows you to implement them in a subclass,
   which enables tools like ``pylint`` and ``mypy`` to check your work and complain
   early if you do certain things wrong.

 - While we assume all plugins are stateless (hence all ``@staticmethods``), we may
   introduce stateful/configurable plugins later on. Starting out with a base class will
   make this transition easier.


Making your own Plugin
----------------------

To get started on your own plugin you will want to subclass the
:py:class:`armi.plugins.ArmiPlugin` class, and implement whichever Plugin APIs that you
want your Plugin to provide. Mark each of your implementations with an
``@armi.plugins.HOOKIMPL`` decorator. Take a look at
:py:class:`armi.physics.neutronics.NeutronicsPlugin` for an example. Make sure that in
your implementation, you follow any rules or guidelines that are provided in the
docstring for that Plugin API method. Failure to do so will lead to bugs and crashes in
any ARMI-based Application that might use your plugin.

.. important::
   We do not actually instantiate Plugin classes. Plugins are currently assumed to be
   stateless (notice that all of the ``@staticmethods`` on all of the hook
   specifications). See the above section for why.

It is likely that your Plugin class itself is only the tip of the iceberg that is the
functionality provided by it. All of the various Interfaces, Settings, Parameters,
etc. that your Plugin exposes to the Framework will likely live in other modules, which
are imported and returned through your hook implementations. Again, see the Neutronics
Plugin as an example. All of the other code will need to accompany your Plugin class
somehow in a cohesive package. Packaging Python projects is beyond the scope of this
document, but see `this page <https://docs.python-guide.org/writing/structure/>`_ for
some guidance.

Once you have a plugin together, continue reading to see how to plug it into the ARMI
Framework as part of an Application.

-----------------------
ARMI-Based Applications
-----------------------
On its own, ARMI doesn't *do* much. Plugins provide more functionality, but even they
aren't particularly useful on their own either. The magic really happens when you
collect a handful of Plugins and plug them into the ARMI Framework. Such a collection is
called an **ARMI-Based Application**.

Once you have a collection of Plugins that you want to use, creating an ARMI-based
Application is very easy. Start by creating a subclass of the :py:class:`armi.apps.App`
class, and write its ``__init__()`` function to register whichever plugins you need with
the app's ``_pm`` ``PluginManager`` object. Calling the base :py:class:`armi.apps.App`
will start you out with the default Framework Plugins, but you are free to discard any
of these that you wish. Optionally, you can implement the
:py:meth:`armi.apps.App.splashText` property to render a custom header to be printed
whenever your application is used.

Example: ::

   >>> class MyApp(armi.apps.App):
   ...     def __init__(self):
   ...         # Adopt the base Framework Plugins. After calling __init__(), they are in
   ...         # self._pm.
   ...         armi.apps.App.__init__(self)
   ...
   ...         # Register our own plugins
   ...         from myapp.pluginA import PluginA
   ...         from myapp.pluginB import PluginB
   ...
   ...         self._pm.register(PluginA)
   ...         self._pm.register(PluginB)
   ...
   ...     @property
   ...     def splashText(self):
   ...         return """
   ...     ===============================
   ...     == My First ARMI Application ==
   ...     ===============================
   ... """

Once you have defined your ``App`` class, you need to configure the ARMI Framework to
use it. To do this, call the :py:func:`armi.configure()` function, passing an instance
of your ``App`` class as the only argument. It is usually best to do this in your
application's ``__init__.py`` or ``__main__.py``. Notice that in
:py:mod:`armi.__main__`, ARMI configures `itself` with the base
:py:class:`armi.apps.App` class!

Example: ::

   >>> import armi
   >>> armi.configure(MyApp())
