"""
EntryPoint base classes.

See :doc:`/developer/entrypoints`.
"""
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

import argparse
from typing import Optional, Union

from armi import context, runLog, settings


class _EntryPointEnforcer(type):
    """
    Simple metaclass used for the EntryPoint abstract base class to enforce class
    attributes.
    """

    def __new__(mcs, name, bases, attrs):
        if "name" not in attrs:
            raise AttributeError("Subclasses of EntryPoint must define a `name` class attribute.")

        # basic input validation. Will throw a KeyError if argument is incorrect
        clsSettings = {"optional": "optional", "required": "required", None: None}[attrs.get("settingsArgument", None)]
        attrs["settingsArgument"] = clsSettings

        return type.__new__(mcs, name, bases, attrs)


class EntryPoint(metaclass=_EntryPointEnforcer):
    """
    Generic command line entry point.

    A valid subclass must provide at least a ``name`` class attribute, and may also specify the
    other class attributes described below.

    .. impl:: Generic CLI base class for developers to use.
        :id: I_ARMI_CLI_GEN
        :implements: R_ARMI_CLI_GEN

        Provides a base class for plugin developers to use in creating application-specific CLIs.
        Valid subclasses must at least provide a ``name`` class attribute.

        Optional class attributes that a subclass may provide include ``description``, a string
        describing the command's actions, ``splash``, a boolean specifying whether to display a
        splash screen upon execution, and ``settingsArgument``. If ``settingsArgument`` is specified
        as ``required``, then a settings files is a required positional argument. If
        ``settingsArgument`` is set to ``optional``, then a settings file is an optional positional
        argument. If None is specified for the ``settingsArgument``, then no settings file argument
        is added.
    """

    #: The <command-name> that is used to call the command from the command line
    name: Optional[str] = None

    description: Optional[str] = None
    """A string summarizing the command's actions. This is summary that is printed when
    you run `python -m armi --list-commands` or `python -m armi <command-name>
    --help`. If not provided, the docstring of the decorated class will be used
    instead. In general, the docstring is probably sufficient but this argument allows
    you to provide a short description of the command while retaining a long and
    detailed docstring."""

    settingsArgument: Union[str, None] = None
    """
    One of {'optional', 'required', None}, or unspecified.
    Specifies whether a settings file argument is to be added to the
    command's argument parser. If settingsArgument == 'required', then a settings
    file is a required positional argument. If settingsArgument == 'optional',
    then it is an optional positional argument. Finally, if settingsArgument is
    None, then no settings file argument is added."""

    splash = True
    """
    Whether running the entry point should produce a splash text upon executing.

    Setting this to ``False`` is useful for utility commands that produce standard
    output that would be needlessly cluttered by the splash text.
    """

    #: One of {armi.Mode.BATCH, armi.Mode.INTERACTIVE, armi.Mode.GUI}, optional.
    #: Specifies the ARMI mode in which the command is run. Default is armi.Mode.BATCH.
    mode: Optional[int] = None

    def __init__(self):
        if self.name is None:
            raise AttributeError("Subclasses of EntryPoint must define a `name` class attribute")

        self.cs = self._initSettings()

        self.parser = argparse.ArgumentParser(
            prog="{} {}".format(context.APP_NAME, self.name),
            description=self.description or self.__doc__,
        )
        if self.settingsArgument is not None:
            if self.settingsArgument not in ["required", "optional"]:
                raise AttributeError(
                    "Subclasses of EntryPoint must specify if the a case settings file is `required` or `optional`"
                )
            if self.settingsArgument == "optional":
                self.parser.add_argument(
                    "settings_file",
                    nargs="?",
                    action=loadSettings(self.cs),
                    help="path to the settings file to load.",
                )
            elif self.settingsArgument == "required":
                self.parser.add_argument(
                    "settings_file",
                    action=loadSettings(self.cs),
                    help="path to the settings file to load.",
                )

        # optional arguments
        self.parser.add_argument(
            "--caseTitle",
            type=str,
            nargs=None,
            action=setCaseTitle(self.cs),
            help="update the case title of the run.",
        )
        self.parser.add_argument(
            "--batch",
            action="store_true",
            default=False,
            help="Run in batch mode even on TTY, silencing all queries.",
        )
        self.createOptionFromSetting("verbosity", "-v")
        self.createOptionFromSetting("branchVerbosity", "-V")

        self.args = argparse.Namespace()
        self.settingsProvidedOnCommandLine = []

    @staticmethod
    def _initSettings():
        """
        Initialize settings for this entry point.

        Settings given on command line will update this data structure.
        Override to provide specific settings in the entry point.
        """
        return settings.Settings()

    def addOptions(self):
        """
        Add additional command line options.

        Values of options added to ``self.parser`` will be available
        on ``self.args``. Values added with ``createOptionFromSetting``
        will override the setting values in the settings input file.

        See Also
        --------
        createOptionFromSetting : A method often called from here to creat CLI options from
            application settings.

        argparse.ArgumentParser.add_argument : Often called from here using
            ``self.parser.add_argument`` to add custom argparse arguments.
        """

    def parse_args(self, args):
        self.parser.parse_args(args, namespace=self.args)
        runLog.setVerbosity(self.cs["verbosity"])

    def parse(self, args):
        """Parse the command line arguments, with the command specific arguments."""
        self.addOptions()
        self.parse_args(args)

    def invoke(self) -> Optional[int]:
        """
        Body of the entry point.

        This is an abstract method, and must must be overridden in sub-classes.

        Returns
        -------
        exitcode : int or None
            Implementations should return an exit code, or ``None``, which is interpreted the
            same as zero (successful completion).
        """
        raise NotImplementedError("Subclasses of EntryPoint must override the .invoke() method")

    def createOptionFromSetting(self, settingName: str, additionalAlias: str = None, suppressHelp: bool = False):
        """
        Create a CLI option from an ARMI setting.

        This will override whatever is in the settings file.

        Parameters
        ----------
        settingName : str
            the setting name

        additionalAlises : str
            additional alias for the command line option, be careful and make sure they are all distinct!

        supressHelp : bool
            option to suppress the help message when using the command line :code:`--help` function. This is
            particularly beneficial when many options are being added as they can clutter the :code:`--help` to be
            almost unusable.
        """
        settingsInstance = self.cs.getSetting(settingName)

        if settings.isBoolSetting(settingsInstance):
            helpMessage = argparse.SUPPRESS if suppressHelp else settingsInstance.description
            self._createToggleFromSetting(settingName, helpMessage, additionalAlias)

        else:
            choices = None
            if suppressHelp:
                helpMessage = argparse.SUPPRESS
            else:
                helpMessage = settingsInstance.description.replace("%", "%%")

            aliases = ["--" + settingName]
            if additionalAlias is not None:
                aliases.append(additionalAlias)

            isListType = settingsInstance.underlyingType is list

            try:
                self.parser.add_argument(
                    *aliases,
                    type=str,  # types are properly converted by _SetSettingAction
                    nargs="*" if isListType else None,
                    action=setSetting(self),
                    default=settingsInstance.default,
                    choices=choices,
                    help=helpMessage,
                )
            # Capture an argument error here to prevent errors when duplicate options are attempting
            # to be added. This may also be captured by exploring the parser's `_actions` list as well
            # but this avoid accessing a private attribute.
            except argparse.ArgumentError:
                pass

    def _createToggleFromSetting(self, settingName, helpMessage, additionalAlias=None):
        aliases = ["--" + settingName]
        if additionalAlias is not None:
            aliases.append(additionalAlias)

        group = self.parser.add_mutually_exclusive_group()

        group.add_argument(*aliases, action=storeBool(True, self), help=helpMessage)

        # not really sure what to do about the help message here. Don't
        # want to suppress it since it won't show up at all, but can't
        # exactly "negate" the text automatically. Ideas?
        if helpMessage is not argparse.SUPPRESS:
            helpMessage = ""

        group.add_argument(
            "--no-" + settingName,
            action=storeBool(False, self),
            dest=settingName,
            help=helpMessage,
        )
        # ^^ overwrites settingName with False


def storeBool(boolDefault, ep):
    class _StoreBoolAction(argparse.Action):
        def __init__(self, option_strings, dest, help=None):
            super(_StoreBoolAction, self).__init__(
                option_strings=option_strings,
                dest=dest,
                nargs=0,
                const=boolDefault,
                default=False,
                required=False,
                help=help,
            )

        def __call__(self, parser, namespace, values, option_string=None):
            ep.cs[self.dest] = self.const
            ep.settingsProvidedOnCommandLine.append(self.dest)
            ep.cs.failOnLoad()

    return _StoreBoolAction


def setSetting(ep):
    class _SetSettingAction(argparse.Action):
        """This class loads the command line supplied setting values into the
        :py:data:`armi.settings.cs`.
        """

        def __call__(self, parser, namespace, values, option_string=None):
            # correctly converts type
            ep.cs[self.dest] = values
            ep.settingsProvidedOnCommandLine.append(self.dest)
            ep.cs.failOnLoad()

    return _SetSettingAction


# Q: Why does this require special treatment? Why not treat it like the other
#    case settings and use setSetting action?
# A: Because caseTitle is no longer an actual cs setting. It's a instance attr.
def setCaseTitle(cs):
    class _SetCaseTitleAction(argparse.Action):
        """This class sets the case title to the supplied value of the
        :py:data:`armi.settings.cs`.
        """

        def __call__(self, parser, namespace, value, option_string=None):
            cs.caseTitle = value

    return _SetCaseTitleAction


# Careful, this is used by physicalProgramming
def loadSettings(cs):
    class LoadSettingsAction(argparse.Action):
        """This class loads the command line supplied settings file into the
        :py:data:`armi.settings.cs`.
        """

        def __call__(self, parser, namespace, values, option_string=None):
            # since this is a positional argument, it can be called with values is
            # None (i.e. default)
            if values is not None:
                cs.loadFromInputFile(values)

    return LoadSettingsAction
