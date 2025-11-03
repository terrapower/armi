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
The ``Case`` object is responsible for running, and executing a set of user inputs. Many entry
points redirect into ``Case`` methods, such as ``clone``, ``compare``, and ``run``.

The ``Case`` object provides an abstraction around ARMI inputs to allow for manipulation and
collection of cases.

See Also
--------
armi.cases.suite : A collection of Cases
"""

import ast
import cProfile
import glob
import io
import os
import pathlib
import pstats
import re
import sys
import textwrap
import time
import trace
from typing import Dict, Optional, Sequence, Set, Union

import coverage

from armi import context, getPluginManager, interfaces, operators, runLog, settings
from armi.bookkeeping.db import compareDatabases
from armi.physics.neutronics.settings import CONF_LOADING_FILE
from armi.reactor import blueprints, reactors
from armi.utils import pathTools, tabulate, textProcessors
from armi.utils.customExceptions import NonexistentSetting
from armi.utils.directoryChangers import (
    DirectoryChanger,
    ForcedCreationDirectoryChanger,
)

# Change from default .coverage to help with Windows dotfile issues.
# Must correspond with data_file entry in `pyproject.toml`!
COVERAGE_RESULTS_FILE = "coverage_results.cov"


class Case:
    """
    An ARMI Case that can be used for suite set up and post-analysis.

    A Case is capable of loading inputs, checking that they are valid, and initializing a reactor
    model. Cases can also compare against other cases and be collected into multiple
    :py:class:`armi.cases.suite.CaseSuite`.
    """

    def __init__(self, cs, caseSuite=None, bp=None):
        """
        Initialize a Case from user input.

        Parameters
        ----------
        cs : Settings
            Settings for this Case
        caseSuite : CaseSuite, optional
            CaseSuite this particular case belongs. Passing this in allows dependency tracking
            across the other cases (e.g. if one case uses the output of another as input, as happens
            in in-use testing for reactivity coefficient snapshot testing or more complex analysis
            sequences).
        bp : Blueprints, optional
            :py:class:`armi.reactor.blueprints.Blueprints` object containing the assembly
            definitions and other information. If not supplied, it will be loaded from the ``cs`` as
            needed.
        """
        self._startTime = time.time()
        self._caseSuite = caseSuite
        self._tasks = []
        self._dependencies: Set[Case] = set()
        self.enabled = True

        # set the signal if the user passes in a blueprint object, instead of a file
        if bp is not None:
            cs.filelessBP = True

        # NOTE: in order to prevent slow submission times for loading massively large blueprints
        # (e.g. certain computer-generated input files), self.bp can be None.
        self.cs = cs
        self._bp = bp

        # this is used in parameter sweeps
        self._independentVariables = {}

    @property
    def independentVariables(self):
        """
        Get dictionary of independent variables and their values.

        This unpacks independent variables from the cs object's independentVariables setting the
        first time it is run. This is used in parameter sweeps.

        See Also
        --------
        writeInputs : writes the ``independentVariabls`` setting
        """
        if not self._independentVariables:
            for indepStr in self.cs["independentVariables"]:
                indepName, value = ast.literal_eval(indepStr)
                self._independentVariables[indepName] = value
        return self._independentVariables

    def __repr__(self):
        return "<Case cs: {}>".format(self.cs.path)

    @property
    def bp(self):
        """
        Blueprint object for this case.

        Notes
        -----
        This property allows lazy loading.
        """
        if self._bp is None:
            self._bp = blueprints.loadFromCs(self.cs, roundTrip=True)
        return self._bp

    @bp.setter
    def bp(self, bp):
        self._bp = bp

    @property
    def dependencies(self):
        """
        Get a list of parent Case objects.

        Notes
        -----
        This is performed on demand so that if someone changes the underlying Settings, the case
        will reflect the correct dependencies. As a result, if this is being done iteratively,
        you may want to cache it somehow (in a dict?).

        Ideally, this should not be the responsibility of the Case, but rather the suite!
        """
        dependencies = set()
        if self._caseSuite is not None:
            pm = getPluginManager()
            if pm is not None:
                for pluginDependencies in pm.hook.defineCaseDependencies(case=self, suite=self._caseSuite):
                    dependencies.update(pluginDependencies)

            # the ([^\/]) capture basically gets the file name portion and excludes any
            # directory separator
            dependencies.update(
                self.getPotentialParentFromSettingValue(
                    self.cs["explicitRepeatShuffles"],
                    r"^(?P<dirName>.*[\/\\])?(?P<title>[^\/\\]+)-SHUFFLES\.txt$",
                )
            )
        # ensure that a case doesn't appear to be its own dependency
        dependencies.update(self._dependencies)
        dependencies.discard(self)

        return dependencies

    def addExplicitDependency(self, case):
        """
        Register an explicit dependency.

        When evaluating the ``dependency`` property, dynamic dependencies are probed
        using the current case settings and plugin hooks. Sometimes, it is necessary to
        impose dependencies that are not expressed through settings and hooks. This
        method stores another case as an explicit dependency, which will be included
        with the other, implicitly discovered, dependencies.
        """
        if case in self._dependencies:
            runLog.warning("The case {} is already explicitly specified as a dependency of {}".format(case, self))
        self._dependencies.add(case)

    def getPotentialParentFromSettingValue(self, settingValue, filePattern):
        """
        Get a parent case based on a setting value and a pattern.

        This is a convenient way for a plugin to express a dependency. It uses the
        ``match.groupdict`` functionality to pull the directory and case name out of a
        specific setting value an regular expression.

        Parameters
        ----------
        settingValue : str
            A particular setting value that might contain a reference to an input that
            is produced by a dependency.
        filePattern : str
            A regular expression for extracting the location and name of the dependency.
            If the ``settingValue`` matches the passed pattern, this function will
            attempt to extract the ``dirName`` and ``title`` groups to find the dependency.
        """
        m = re.match(filePattern, settingValue, re.IGNORECASE)
        deps = self._getPotentialDependencies(**m.groupdict()) if m else set()
        if len(deps) > 1:
            raise KeyError("Found more than one case matching {}".format(settingValue))
        return deps

    def _getPotentialDependencies(self, dirName, title):
        """Get a parent case based on a directory and case title."""
        if dirName is None:
            dirName = self.directory
        elif not os.path.isabs(dirName):
            dirName = os.path.join(self.directory, dirName)

        def caseMatches(case):
            if os.path.normcase(case.title) != os.path.normcase(title):
                return False

            return os.path.normcase(os.path.abspath(case.directory)) == os.path.normcase(os.path.abspath(dirName))

        return {case for case in self._caseSuite if caseMatches(case)}

    @property
    def title(self):
        """The case title."""
        return self.cs.caseTitle

    @title.setter
    def title(self, name):
        self.cs.caseTitle = name

    @property
    def dbName(self):
        """The case output database name."""
        return os.path.splitext(self.cs.path)[0] + ".h5"

    @property
    def directory(self):
        """The working directory of the case."""
        return self.cs.inputDirectory

    def __eq__(self, that):
        """
        Compares two cases to determine if they are equivalent by looking at the ``title`` and
        ``directory``.

        Notes
        -----
        No other attributes except those stated above are used for the comparison; the above stated
        attributes can be considered the "primary key" for a Case object and identify it as being
        unique. Both of these comparisons are simple string comparisons, so a reference and an
        absolute path to the same case would be considered different.
        """
        return self.title == that.title and self.directory == that.directory

    def __hash__(self):
        """Computes the hash of a Case object.

        This is required when __eq__ is been defined. Take the hash of the tuple of the "primary key".
        """
        return hash((self.title, self.directory))

    def setUpTaskDependence(self):
        """
        Set the task dependence based on the :code:`dependencies`.

        This accounts for whether or not the dependency is enabled.
        """
        if not self.enabled:
            return

        for dependency in self.dependencies:
            if dependency.enabled:
                self._tasks[0].add_parent(dependency._tasks[-1])

    def run(self):
        """
        Run an ARMI case.

        .. impl:: The case class allows for a generic ARMI simulation.
            :id: I_ARMI_CASE
            :implements: R_ARMI_CASE

            This method is responsible for "running" the ARMI simulation instigated by the inputted
            settings. This initializes an :py:class:`~armi.operators.operator.Operator`, a
            :py:class:`~armi.reactor.reactors.Reactor` and invokes
            :py:meth:`Operator.operate <armi.operators.operator.Operator.operate>`. It also
            activates supervisory things like code coverage checking, profiling, or tracing, if
            requested by users during debugging.

        Notes
        -----
        Room for improvement: The coverage, profiling, etc. stuff can probably be moved out of here
        to a more elegant place (like a context manager?).
        """
        # Start the log here so that the verbosities for the head and workers can be configured
        # based on the user settings for the rest of the run.
        runLog.LOG.startLog(self.cs.caseTitle)
        if context.MPI_RANK == 0:
            runLog.setVerbosity(self.cs["verbosity"])
        else:
            runLog.setVerbosity(self.cs["branchVerbosity"])

        # if in the settings, start the coverage and profiling
        cov = self._startCoverage()
        profiler = self._startProfiling()

        self.checkInputs()
        o = self.initializeOperator()

        with o:
            if self.cs["trace"] and context.MPI_RANK == 0:
                # only trace primary node.
                tracer = trace.Trace(ignoredirs=[sys.prefix, sys.exec_prefix], trace=1)
                tracer.runctx("o.operate()", globals(), locals())
            else:
                o.operate()

        # if in the settings, report the coverage and profiling
        Case._endCoverage(self.cs["coverageConfigFile"], cov)
        Case._endProfiling(profiler)

    def _startCoverage(self):
        """Helper to the Case.run: spin up the code coverage tooling, if the Settings file says to.

        Returns
        -------
        coverage.Coverage
            Coverage object for pytest or unittest
        """
        cov = None
        if self.cs["coverage"]:
            cov = coverage.Coverage(
                config_file=Case._getCoverageRcFile(userCovFile=self.cs["coverageConfigFile"], makeCopy=True),
                debug=["dataio"],
            )
            if context.MPI_SIZE > 1:
                # interestingly, you cannot set the parallel flag in the constructor without
                # auto-specifying the data suffix. This should enable parallel coverage with
                # auto-generated data file suffixes and combinations.
                cov.config.parallel = True
            cov.start()

        return cov

    @staticmethod
    def _endCoverage(userCovFile, cov=None):
        """Helper to the Case.run(): stop and report code coverage, if the Settings file says to.

        Parameters
        ----------
        userCovFile : str
            File path to user-supplied coverage configuration file (default setting is empty string)
        cov: coverage.Coverage (optional)
            Hopefully, a valid and non-empty set of coverage data.
        """
        if cov is None:
            return

        cov.stop()
        cov.save()

        if context.MPI_SIZE > 1:
            context.MPI_COMM.barrier()  # force waiting for everyone to finish

        if context.MPI_RANK == 0 and context.MPI_SIZE > 1:
            # combine all the parallel coverage data files into one and make the XML and HTML
            # reports for the whole run.
            combinedCoverage = coverage.Coverage(config_file=Case._getCoverageRcFile(userCovFile), debug=["dataio"])
            combinedCoverage.config.parallel = True
            # combine does delete the files it merges
            combinedCoverage.combine()
            combinedCoverage.save()
            combinedCoverage.html_report()
            combinedCoverage.xml_report()

    @staticmethod
    def _getCoverageRcFile(userCovFile, makeCopy=False):
        """Helper to provide the coverage configuration file according to the OS. A user-supplied
        file will take precedence, and is not checked for a dot-filename.

        Notes
        -----
        ARMI replaced the ".coveragerc" file has been replaced by "pyproject.toml".

        Parameters
        ----------
        userCovFile : str
            File path to user-supplied coverage configuration file (default setting is empty string)
        makeCopy : bool (optional)
            Whether or not to copy the coverage config file to an alternate file path

        Returns
        -------
        covFile : str
            path of pyprojec.toml file
        """
        # User-defined file takes precedence.
        if userCovFile:
            return os.path.abspath(userCovFile)

        covRcDir = os.path.abspath(context.PROJECT_ROOT)
        return os.path.join(covRcDir, "pyproject.toml")

    def _startProfiling(self):
        """Helper to the Case.run(): start the Python profiling, if the Settings file says to.

        Returns
        -------
        cProfile.Profile
            Standard Python profiling object
        """
        profiler = None
        if self.cs["profile"]:
            profiler = cProfile.Profile()
            profiler.enable(subcalls=True, builtins=True)

        return profiler

    @staticmethod
    def _endProfiling(profiler=None):
        """Helper to the Case.run(): stop and report python profiling, if the Settings file says to.

        Parameters
        ----------
        profiler: cProfile.Profile (optional)
            Hopefully, a valid and non-empty set of profiling data.
        """
        if profiler is None:
            return

        profiler.disable()
        profiler.dump_stats("profiler.{:0>3}.stats".format(context.MPI_RANK))
        statsStream = io.StringIO()
        summary = pstats.Stats(profiler, stream=statsStream).sort_stats("cumulative")
        summary.print_stats()
        if context.MPI_SIZE > 0 and context.MPI_COMM is not None:
            allStats = context.MPI_COMM.gather(statsStream.getvalue(), root=0)
            if context.MPI_RANK == 0:
                for rank, statsString in enumerate(allStats):
                    # using print statements because the logger has been turned off
                    print("=" * 100)
                    print("{:^100}".format(" Profiler statistics for RANK={} ".format(rank)))
                    print(statsString)
                    print("=" * 100)
        else:
            print(statsStream.getvalue())

    def _initBurnChain(self, r):
        """
        Apply the burn chain setting to the nucDir.

        Parameters
        ----------
        r: Reactor
            The reactor object for this case.

        Notes
        -----
        This is admittedly an odd place for this but the burn chain info must be applied sometime after user-input has
        been loaded (for custom burn chains) but not long after (because users need it).
        """
        if not self.cs["initializeBurnChain"]:
            runLog.info("Skipping burn-chain initialization since `initializeBurnChain` setting is disabled.")
            return

        if not os.path.exists(self.cs["burnChainFileName"]):
            raise ValueError(
                f"The burn-chain file {self.cs['burnChainFileName']} does not exist. The data cannot be loaded. Fix "
                "this path or disable burn-chain initialization using the `initializeBurnChain` setting."
            )

        with open(self.cs["burnChainFileName"]) as burnChainStream:
            r.nuclideBases.imposeBurnChain(burnChainStream)

    def initializeOperator(self, r=None):
        """Creates and returns an Operator."""
        with DirectoryChanger(self.cs.inputDirectory, dumpOnException=False):
            o = operators.factory(self.cs)
            if r is None:
                r = reactors.factory(self.cs, self.bp)

            self._initBurnChain(r)
            o.initializeInterfaces(r)
            # Set this here to make sure the full duration of initialization is properly captured.
            # Cannot be done in reactors since the above self.bp call implicitly initializes blueprints.
            r.core.timeOfStart = self._startTime
            return o

    def checkInputs(self):
        """
        Checks ARMI inputs for consistency.

        .. impl:: Perform validity checks on case inputs.
            :id: I_ARMI_CASE_CHECK
            :implements: R_ARMI_CASE_CHECK

            This method checks the validity of the current settings. It relies on an
            :py:class:`~armi.settings.settingsValidation.Inspector` object from the
            :py:class:`~armi.operators.operator.Operator` to generate a list of
            :py:class:`~armi.settings.settingsValidation.Query` objects that represent potential
            issues in the settings. After gathering the queries, this method prints a table of query
            "statements" and "questions" to the console. If running in an interactive mode, the user
            then has the opportunity to address the questions posed by the queries by either
            addressing the potential issue or ignoring it.

        Returns
        -------
        bool
            True if the inputs are all good, False otherwise
        """
        runLog.header("=========== Settings Validation Checks ===========")
        with DirectoryChanger(self.cs.inputDirectory, dumpOnException=False):
            operatorClass = operators.getOperatorClassFromSettings(self.cs)
            inspector = operatorClass.inspector(self.cs)
            inspectorIssues = [query for query in inspector.queries if query]

            # Write out the settings validation issues that will be prompted for resolution if in an
            # interactive session or forced to be resolved otherwise.
            queryData = []
            for i, query in enumerate(inspectorIssues, start=1):
                queryData.append(
                    (
                        i,
                        textwrap.fill(query.statement, width=50, break_long_words=False),
                        textwrap.fill(query.question, width=50, break_long_words=False),
                    )
                )

            if queryData and context.MPI_RANK == 0:
                runLog.info(
                    tabulate.tabulate(
                        queryData,
                        headers=["Number", "Statement", "Question"],
                        tableFmt="armi",
                    )
                )
            if context.CURRENT_MODE == context.Mode.INTERACTIVE:
                # if interactive, ask user to deal with settings issues
                inspector.run()

            return not any(inspectorIssues)

    def clone(
        self,
        additionalFiles=None,
        title=None,
        modifiedSettings=None,
        writeStyle="short",
    ):
        """
        Clone existing ARMI inputs to current directory with optional settings modifications.

        Since each case depends on multiple inputs, this is a safer way to move cases around without
        having to wonder if you copied all the files appropriately.

        Parameters
        ----------
        additionalFiles : list (optional)
            additional file paths to copy to cloned case
        title : str (optional)
            title of new case
        modifiedSettings : dict (optional)
            settings to set/modify before creating the cloned case
        writeStyle : str (optional)
            Writing style for which settings get written back to the settings files
            (short, medium, or full).

        Raises
        ------
        RuntimeError
            If the source and destination are the same
        """
        cloneCS = self.cs.duplicate()

        if modifiedSettings is not None:
            cloneCS = cloneCS.modified(newSettings=modifiedSettings)

        clone = Case(cloneCS)
        clone.cs.path = pathTools.armiAbsPath(title or self.title) + ".yaml"

        if pathTools.armiAbsPath(clone.cs.path) == pathTools.armiAbsPath(self.cs.path):
            raise RuntimeError(
                "The source file and destination file are the same: {}\nCannot use armi-clone to "
                "modify armi settings file.".format(pathTools.armiAbsPath(clone.cs.path))
            )

        newSettings = copyInterfaceInputs(self.cs, clone.cs.inputDirectory)
        newCs = clone.cs.modified(newSettings=newSettings)
        clone.cs = newCs

        runLog.important(f"writing settings file {clone.cs.path}")
        clone.cs.writeToYamlFile(clone.cs.path, style=writeStyle, fromFile=self.cs.path)
        runLog.important(f"finished writing {clone.cs}")

        fromPath = lambda f: pathTools.armiAbsPath(self.cs.inputDirectory, f)

        fileName = self.cs[CONF_LOADING_FILE]
        if fileName:
            pathTools.copyOrWarn(
                CONF_LOADING_FILE,
                fromPath(fileName),
                os.path.join(clone.cs.inputDirectory, fileName),
            )
        else:
            runLog.warning(f"skipping {CONF_LOADING_FILE}, there is no file specified")

        with open(self.cs[CONF_LOADING_FILE], "r") as f:
            # The root for handling YAML includes is relative to the YAML file, not the
            # settings file
            root = pathlib.Path(self.cs.inputDirectory) / pathlib.Path(self.cs[CONF_LOADING_FILE]).parent
            cloneRoot = pathlib.Path(clone.cs.inputDirectory) / pathlib.Path(clone.cs[CONF_LOADING_FILE]).parent
            for includePath, mark in textProcessors.findYamlInclusions(f, root=root):
                if not includePath.is_absolute():
                    includeSrc = root / includePath
                    includeDest = cloneRoot / includePath
                else:
                    # don't bother copying absolute files
                    continue
                if not includeSrc.exists():
                    raise OSError("The input file file `{}` referenced at {} does not exist.".format(includeSrc, mark))
                pathTools.copyOrWarn(
                    "auxiliary input file `{}` referenced at {}".format(includeSrc, mark),
                    includeSrc,
                    includeDest,
                )

        for fileName in additionalFiles or []:
            pathTools.copyOrWarn("additional file", fromPath(fileName), clone.cs.inputDirectory)

        return clone

    def compare(
        self,
        that,
        exclusion: Optional[Sequence[str]] = None,
        tolerance=0.01,
        timestepCompare=None,
    ) -> int:
        """
        Compare the output databases from two run cases. Return number of differences.

        This is useful both for in-use testing and engineering analysis.
        """
        runLog.info("Comparing the following databases:\nREF: {}\nSRC: {}".format(self.dbName, that.dbName))
        diffResults = compareDatabases(
            self.dbName,
            that.dbName,
            tolerance=tolerance,
            exclusions=exclusion,
            timestepCompare=timestepCompare,
        )

        code = 1 if diffResults is None else diffResults.nDiffs()

        sameOrDifferent = "different" if diffResults is None or diffResults.nDiffs() > 0 else "the same"
        runLog.important("Cases are {}.".format(sameOrDifferent))

        return code

    def writeInputs(self, sourceDir: Optional[str] = None, writeStyle: Optional[str] = "short"):
        """
        Write the inputs to disk.

        This allows input objects that have been modified in memory (e.g. for a parameter sweep or
        migration) to be written out as input for a forthcoming case.

        Parameters
        ----------
        sourceDir : str (optional)
            The path to copy inputs from (if different from the cs.path). Needed
            in SuiteBuilder cases to find the baseline inputs from plugins (e.g. shuffleLogic)
        writeStyle : str (optional)
            Writing style for which settings get written back to the settings files
            (short, medium, or full).

        Notes
        -----
        This will rename the ``loadingFile`` to ``title-blueprints + '.yaml'``.

        See Also
        --------
        independentVariables
            parses/reads the independentVariables setting

        clone
            Similar to this but doesn't let you write out new/modified blueprints objects
        """
        with ForcedCreationDirectoryChanger(self.cs.inputDirectory, dumpOnException=False):
            # These seemingly no-ops load the bp via properties if they are not yet initialized.
            self.bp

            newSettings = {}
            newSettings[CONF_LOADING_FILE] = self.title + "-blueprints.yaml"
            if self.independentVariables:
                newSettings["independentVariables"] = [
                    f"({repr(varName)}, {repr(val)})" for varName, val in self.independentVariables.items()
                ]

            with open(newSettings[CONF_LOADING_FILE], "w") as loadingFile:
                blueprints.Blueprints.dump(self.bp, loadingFile)

            # copy input files from other modules/plugins
            interfaceSettings = copyInterfaceInputs(self.cs, ".", sourceDir)
            for settingName, value in interfaceSettings.items():
                newSettings[settingName] = value

            self.cs = self.cs.modified(newSettings=newSettings)
            if sourceDir:
                fromPath = os.path.join(sourceDir, self.title + ".yaml")
            else:
                fromPath = self.cs.path
            self.cs.writeToYamlFile(f"{self.title}.yaml", style=writeStyle, fromFile=fromPath)


def _copyInputsHelper(fileDescription: str, sourcePath: str, destPath: str, origFile: str) -> str:
    """
    Helper function for copyInterfaceInputs: Creates an absolute file path, and copies the file to
    that location. If that file path does not exist, returns the file path from the original
    settings file.

    Parameters
    ----------
    fileDescription : str
        A file description for the copyOrWarn method
    sourcePath : str
        The absolute file path of the file to copy
    destPath : str
        The target directory to copy input files to
    origFile : str
        File path as defined in the original settings file

    Returns
    -------
    destFilePath (or origFile) : str
    """
    sourceName = pathlib.Path(sourcePath).name
    destFilePath = os.path.join(destPath, sourceName)
    try:
        pathTools.copyOrWarn(fileDescription, sourcePath, destFilePath)
        if pathlib.Path(destFilePath).exists():
            # the basename gets written back to the settings file to protect against potential
            # future dir structure changes
            return os.path.basename(destFilePath)
        else:
            # keep original filepath in the settings file if file copy was unsuccessful
            return origFile
    except Exception:
        return origFile


def copyInterfaceInputs(cs, destination: str, sourceDir: Optional[str] = None) -> Dict[str, Union[str, list]]:
    """
    Ping active interfaces to determine which files are considered "input". This enables developers
    to add new inputs in a plugin-dependent/ modular way.

    This function should now be able to handle the updating of:

      - a single file (relative or absolute)
      - a list of files (relative or absolute)
      - a file entry that has a wildcard processing into multiple files. Glob is used to offer
        support for wildcards.
      - a directory and its contents

    If the file paths are absolute, do nothing. The case will be able to find the file.

    In case suites or parameter sweeps, these files often have a sourceDir associated with them that
    is different from the cs.inputDirectory. So, if relative or wildcard, update the file paths to
    be absolute in the case settings and copy the file to the destination directory.

    Parameters
    ----------
    cs : Settings
        The source case settings to find input files
    destination : str
        The target directory to copy input files to
    sourceDir : str, optional
        The directory from which to copy files. Defaults to cs.inputDirectory

    Returns
    -------
    dict
        A new settings object that contains settings for the keys and values that are either an
        absolute file path, a list of absolute file paths, or the original file path if absolute
        paths could not be resolved.

    Notes
    -----
    Regarding the handling of relative file paths: In the future this could be simplified by adding
    a concept for a suite root directory, below which it is safe to copy files without needing to
    update settings that point with a relative path to files that are below it.
    """
    activeInterfaces = interfaces.getActiveInterfaceInfo(cs)
    sourceDir = sourceDir or cs.inputDirectory
    sourceDirPath = pathlib.Path(sourceDir)

    assert pathlib.Path(destination).is_dir()

    newSettings = {}

    for klass, _ in activeInterfaces:
        interfaceFileNames = klass.specifyInputs(cs)
        for key, files in interfaceFileNames.items():
            if not isinstance(key, settings.Setting):
                try:
                    key = cs.getSetting(key)
                    label = key.name
                    isSetting = True
                except NonexistentSetting(key):
                    runLog.debug(f"{key} is not a valid setting; continuing on anyway.")
                    label = key
                    isSetting = False
            else:
                isSetting = True
                label = key.name

            newFiles = []
            for f in files:
                WILDCARD = False
                EMPTY = False
                ABSOLUTE = False
                if "*" in f:
                    WILDCARD = True
                if not f:
                    # beware: pathlib.path("") returns "." which can be bad news, so we handle empty
                    # strings as their own category
                    EMPTY = True
                path = pathlib.Path(f)
                if not EMPTY and path.is_absolute():
                    ABSOLUTE = True

                # Attempt to construct an absolute file path
                srcFullPath = os.path.join(sourceDirPath, f)
                destFilePath = None
                if WILDCARD:
                    globFilePaths = [pathlib.Path(os.path.join(sourceDirPath, g)) for g in glob.glob(srcFullPath)]
                    if len(globFilePaths) == 0:
                        destFilePath = f
                        newFiles.append(str(destFilePath))
                    else:
                        for gFile in globFilePaths:
                            destFilePath = _copyInputsHelper(label, gFile, destination, f)
                            newFiles.append(str(destFilePath))
                elif EMPTY:
                    pass
                elif ABSOLUTE:
                    if path.exists():
                        # Path is absolute, no settings modification or filecopy needed
                        newFiles.append(path)
                else:
                    # treat as a relative path
                    destFilePath = _copyInputsHelper(label, srcFullPath, destination, f)
                    newFiles.append(str(destFilePath))

                if destFilePath == f:
                    runLog.debug(
                        f"No input files for `{label}` could be resolved with the following path: "
                        f"`{srcFullPath}`. Will not update `{label}`."
                    )

            # Some settings are a single filename. Others are lists of files. Make
            # sure we are returning what the setting expects
            if isSetting and len(newFiles):
                if len(files) == 1 and not WILDCARD and key.name in cs and not isinstance(cs[key.name], list):
                    newSettings[label] = newFiles[0]
                else:
                    newSettings[label] = newFiles

    return newSettings
