# Copyright 2019 TerraPower, LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
This package provides various operations users can ask ARMI to do with their inputs.

An Entry Point might run a simulation, migrate inputs, build a suite of related inputs
and submit them in a parameter sweep, validate inputs, open the GUI, run a test suite,
or other similar things. There are built-in entry points, and additional ones may
be specified by custom plugins.

The full :doc:`docs for entry points are here </developer/entrypoints>`.

See Also
--------
armi.cases : Individual collections of tasks that may run one or more entry points.
    These allow one entry point to create a sequence of events that may call one
    or more additional entry points. For example, the ``submitSuite`` entry point builds
    a case suite with many related cases that will all call the ``run`` entry point from
    a HPC cluster.

armi.operators :  Operations that ARMI will perform on a reactor model.
    These may be created by ``Case`` objects created by certain entry points (e.g. ``run``).

armi : Fundamental entry point that calls this package.

"""

# importing each module causes the any EntryPoints defined in the module that
# are decorated with @armi.command to be added to the collection of registered
# classes

import argparse
import re
import sys
import textwrap
from typing import Optional

from armi import context
from armi import meta
from armi import plugins
from armi import runLog


class EntryPointsPlugin(plugins.ArmiPlugin):
    @staticmethod
    @plugins.HOOKIMPL
    def defineEntryPoints():
        from armi.cli import (
            checkInputs,
            clone,
            compareCases,
            migrateInputs,
            modify,
            run,
            gridGui,
            # testing
            cleanTemps,
            runSuite,
            reportsEntryPoint,
        )

        entryPoints = []
        entryPoints.append(checkInputs.CheckInputEntryPoint)
        entryPoints.append(checkInputs.ExpandBlueprints)
        entryPoints.append(clone.CloneArmiRunCommandBatch)
        entryPoints.append(clone.CloneArmiRunCommandInteractive)
        entryPoints.append(clone.CloneSuiteCommand)
        entryPoints.append(compareCases.CompareCases)
        entryPoints.append(compareCases.CompareSuites)
        entryPoints.append(migrateInputs.MigrateInputs)
        entryPoints.append(modify.ModifyCaseSettingsCommand)
        entryPoints.append(run.RunEntryPoint)
        entryPoints.append(runSuite.RunSuiteCommand)
        entryPoints.append(gridGui.GridGuiEntryPoint)

        # testing
        entryPoints.append(cleanTemps.CleanTemps)
        entryPoints.append(reportsEntryPoint.ReportsEntryPoint)

        return entryPoints


class ArmiParser(argparse.ArgumentParser):
    """
    Subclass of default ArgumentParser to better handle application splash text.
    """

    def print_help(self, file=None):
        splash()
        argparse.ArgumentParser.print_help(self, file)


class ArmiCLI:
    """
    ARMI CLI -- The main entry point into ARMI. There are various commands
    available, to get help for the individual commands, run again with
    `<command> --help`. Generically, the CLI implements functions that already
    exists within ARMI
    """

    def __init__(self):
        from armi import getPluginManager  # pylint: disable=import-outside-toplevel

        self._entryPoints = dict()
        for pluginEntryPoints in getPluginManager().hook.defineEntryPoints():
            for entryPoint in pluginEntryPoints:
                if entryPoint.name in self._entryPoints:
                    raise KeyError(
                        "Duplicate entry points defined for `{}`: {} and {}".format(
                            entryPoint.name,
                            self._entryPoints[entryPoint.name],
                            entryPoint,
                        )
                    )
                self._entryPoints[entryPoint.name] = entryPoint

        parser = ArmiParser(
            prog=context.APP_NAME,
            description=self.__doc__,
            usage="%(prog)s [-h] [-l | command [args]]",
        )

        group = parser.add_mutually_exclusive_group()

        group.add_argument(
            "-v", "--version", action="store_true", help="display the version"
        )

        group.add_argument(
            "-l", "--list-commands", action="store_true", help="list commands"
        )
        group.add_argument("command", nargs="?", default="help", help=argparse.SUPPRESS)
        parser.add_argument("args", nargs=argparse.REMAINDER, help=argparse.SUPPRESS)

        self.parser = parser

    def showVersion(self):
        """Print the App name and version on the command line"""
        from armi import getApp  # pylint: disable=import-outside-toplevel

        prog = context.APP_NAME
        app = getApp()
        if app is None or prog == "armi":
            print("{0} {1}".format(prog, meta.__version__))
        else:
            print("{0} {1}".format(prog, app.version))

    def listCommands(self):
        """List commands with a short description."""
        splash()

        indent = 22
        initial_indent = "  "
        subsequent_indent = initial_indent + " " * indent
        wrapper = textwrap.TextWrapper(
            initial_indent=initial_indent, subsequent_indent=subsequent_indent, width=79
        )

        sub = re.compile(r"\s+").sub

        # given a string, condense white space into a single space
        condense = lambda s: sub(" ", s.strip())

        commands = self._entryPoints.values()

        formatter = "{name:<{width}}{desc}".format
        print("\ncommands:")
        for cmd in sorted(commands, key=lambda cmd: cmd.name):
            """Each command can optionally define a class attribute `description`
            as documentation. If description is not defined (default=None since
            it should inherit from EntryPoint), then the docstring is used.
            If the docstring is also None, then fall back to an empty string."""
            desc = condense(cmd.description or cmd.__doc__ or "")
            print(wrapper.fill(formatter(width=indent, name=cmd.name, desc=desc)))

    def run(self) -> Optional[int]:
        args = self.parser.parse_args()

        if args.list_commands:
            self.listCommands()
            return 0
        elif args.version:
            self.showVersion()
            return 0
        elif args.command == "help":
            self.parser.print_help()
            return 0

        return self.executeCommand(args.command, args.args)

    def executeCommand(self, command, args) -> Optional[int]:
        r"""execute `command` with arguments `args`, return optional exit code."""
        command = command.lower()
        if command not in self._entryPoints:
            print(
                'Unrecognized command "{}". Valid commands are listed below.'.format(
                    command
                )
            )
            self.listCommands()

            return 1

        commandClass = self._entryPoints[command]
        cmd = commandClass()
        if cmd.splash:
            splash()

        # parse the arguments... command can have their own
        cmd.parse(args)

        if cmd.args.batch:
            context.Mode.setMode(context.Mode.BATCH)
        elif cmd.mode is not None:
            context.Mode.setMode(cmd.mode)

        # do whatever there is to be done!
        return cmd.invoke()


def splash():
    """Emit a the active App's splash text to the runLog for the master node."""
    from armi import getApp  # pylint: disable=import-outside-toplevel

    app = getApp()
    assert app is not None
    if context.MPI_RANK == 0:
        runLog.raw(app.splashText)
