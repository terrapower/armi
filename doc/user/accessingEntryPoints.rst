**********************
Accessing Entry Points 
**********************

**Entry Points** are like the verbs that your App can *do*. The built-in entry
points in the :py:mod:`cli module<armi.cli>` offer basic functionality, like
running a case (:py:class:`armi.cli.run.RunEntryPoint`) or opening up the GUI (
:py:class:`armi.cli.gridGui.GridGuiEntryPoint`), but the real joy of an
application comes when you add your own project-specific entry points that do
the actions that you commonly need done.

ARMI comes with some built-in Entry Points that
can shown by running::

    (venv) $ armi --list-commands

Note that not all built-in Entry Points may be used out of the box, and some may
need to be implemented for your specific application, like the
:py:class:`armi.cli.reportsEntryPoint.ReportsEntryPoint`)

:ref:`The developer doc page on Entry Points <dev-entry-points>` gives a brief
overview on how to build an entry point for your ARMI application.

