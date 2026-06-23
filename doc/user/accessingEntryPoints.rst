**********************
Accessing Entry Points
**********************

**Entry points** are the commands that ARMI exposes on the command line; they are
the "verbs" that an ARMI-based application can perform, such as running a case,
generating a report, or launching the grid GUI. Each entry point maps a command
name (what you type after ``armi``) to a block of code and an optional set of
command-line options. The built-in entry points live in :py:mod:`armi.cli`, and
applications built on ARMI can add their own.

For details on how entry points are implemented and how to write your own, see
:doc:`/developer/entrypoints`.

Listing available commands
==========================

To see every entry point registered with your application, pass the
``-l``/``--list-commands`` flag::

    (venv) $ armi -l

To see the options and arguments for a specific command, run it with
``--help``::

    (venv) $ armi <command> --help

Most entry points accept a settings input file as a positional argument. Whether
that argument is required, optional, or disallowed is controlled by the entry
point's ``settingsArgument`` attribute (see :doc:`/developer/entrypoints`).

Reports Entry Point
===================

There are two ways to access the reports entry point in ARMI.

The first way is through a yaml settings file.
Here, the call is as follows::

    (venv) $ armi report anl-afci-177.yaml

It is also possible to call this on an h5 file::

    (venv) $ armi report -h5db refTestBase.h5

.. note:: When working with a h5 file, -h5db must be included

Once these are called, a report is generated and outputted as an html file in reportsOutputFiles.
