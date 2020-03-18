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

r"""
The ``Case`` object is responsible for running, and executing a set of user inputs.  Many
entry points redirect into ``Case`` methods, such as ``clone``, ``compare``, and ``run``

The ``Case`` object provides an abstraction around ARMI inputs to allow for manipulation and
collection of cases.

See Also
--------
armi.cases.suite : A collection of Cases
"""
import cProfile
import os
import pathlib
import pstats
import re
import sys
import trace
import time
import textwrap
import ast
from typing import Optional, Sequence

import tabulate
import six
import coverage

import armi
from armi import context
from armi import settings
from armi import operators
from armi import runLog
from armi import interfaces
from armi.reactor import blueprints
from armi.reactor import geometry
from armi.reactor import reactors
from armi.bookkeeping import report
from armi.bookkeeping.report import reportInterface
from armi.bookkeeping.db import compareDatabases
from armi.utils import pathTools
from armi.utils.directoryChangers import DirectoryChanger
from armi.utils.directoryChangers import ForcedCreationDirectoryChanger
from armi.utils import textProcessors
from armi.nucDirectory import nuclideBases

# change from default .coverage to help with Windows dotfile issues.
# Must correspond with data_file entry in `coveragerc`!!
COVERAGE_RESULTS_FILE = "coverage_results.cov"


class Case:
    """
    An ARMI Case that can be used for suite set up and post-analysis.

    A Case is capable of loading inputs, checking that they are valid, and
    initializing a reactor model. Cases can also compare against
    other cases and be collected into :py:class:`~armi.cases.suite.CaseSuite`s.
    """

    def __init__(self, cs, caseSuite=None, bp=None, geom=None):
        """
        Initialize a Case from user input.

        Parameters
        ----------
        cs : CaseSettings
            CaseSettings for this Case

        caseSuite : CaseSuite, optional
            CaseSuite this particular case belongs. Passing this in allows dependency
            tracking across the other cases (e.g. if one case uses the output of
            another as input, as happens in in-use testing for reactivity coefficient
            snapshot testing or more complex analysis sequences).

        bp : Blueprints, optional
            :py:class:`~armi.reactor.blueprints.Blueprints` object containing the assembly
            definitions and other information. If not supplied, it will be loaded from the
            ``cs`` as needed.

        geom : SystemLayoutInput, optional
            SystemLayoutInput for this case. If not supplied, it will be loaded from the ``cs`` as
            needed.
        """
        self._startTime = time.time()
        self._caseSuite = caseSuite
        self._tasks = []
        self.enabled = True

        # NOTE: in order to prevent slow submission times for loading massively large
        # blueprints (e.g. ZPPR or other computer-generated input files),
        # self.bp and self.geom can be None.
        self.cs = cs
        self._bp = bp
        self._geom = geom

        # this is used in parameter sweeps
        self._independentVariables = {}

    @property
    def independentVariables(self):
        """
        Get dictionary of independent variables and their values.

        This unpacks independent variables from the cs object's independentVariables
        setting the first time it is run. This is used in parameter sweeps.

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
            self._bp = blueprints.loadFromCs(self.cs)
        return self._bp

    @bp.setter
    def bp(self, bp):
        self._bp = bp

    @property
    def geom(self):
        """
        Geometry object for this Case.

        Notes
        -----
        This property allows lazy loading.
        """
        if self._geom is None:
            self._geom = geometry.loadFromCs(self.cs)
        return self._geom

    @geom.setter
    def geom(self, geom):
        self._geom = geom

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
            pm = armi.getPluginManager()
            if pm is not None:
                for pluginDependencies in pm.hook.defineCaseDependencies(
                    case=self, suite=self._caseSuite
                ):
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
        dependencies.discard(self)

        return dependencies

    def getPotentialParentFromSettingValue(self, settingValue, filePattern):
        """
        Get a parent case based on a setting value and a pattern.

        Parameters
        ----------
        settingValue : str
            A particular setting value that might contain a reference to an input that
            is produced by a dependency.
        filePattern : str
            A regular expression for extracting the location and name of the dependency.
            If the ``settingValue`` matches the passed pattern, this function will
            attempt to extract the ``dirName`` and ``title`` groups to find the
            dependency.

        This is a convenient way for a plugin to express a dependency. It uses the
        ``match.groupdict`` functionality to pull the directory and case name out of a
        specific setting value an regular expression.
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
            if os.path.normcase(os.path.abspath(case.directory)) != os.path.normcase(
                os.path.abspath(dirName)
            ):
                return False
            return True

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
        # computes the hash of a Case object. This is required in Python3 when __eq__ has been
        # defined.  take the hash of the tuple of the "primary key"
        return hash((self.title, self.directory))

    def setUpTaskDependence(self):
        """
        Set the task dependence based on the :code:`dependencies`.

        This accounts for whether or not the dependency is enabled.

        Note
        ----
        This is a leftover from before the release of the ARMI framework. The API of the
        proprietary cluster communication library is being used here. This should either
        be moved out into the cluster plugin, or the library should be made available.
        """
        if not self.enabled:
            return
        for dependency in self.dependencies:
            if dependency.enabled:
                # pylint: disable=protected-access; dependency should
                # also be a Case, so it's not really "protected"
                self._tasks[0].add_parent(dependency._tasks[-1])

    def run(self):
        """
        Run an ARMI case.

        This initializes an ``Operator``, a ``Reactor`` and invokes
        :py:meth:`Operator.operate`!

        It also activates supervisory things like code coverage checking, profiling,
        or tracing, if requested by users during debugging.

        Notes
        -----
        Room for improvement: The coverage, profiling, etc. stuff can probably be moved
        out of here to a more elegant place (like a context manager?).
        """
        cov = None
        if self.cs["coverage"]:
            cov = coverage.Coverage(
                config_file=os.path.join(armi.RES, "coveragerc"), debug=["dataio"]
            )
            if context.MPI_SIZE > 1:
                # interestingly, you cannot set the parallel flag in the constructor
                # without auto-specifying the data suffix. This should enable
                # parallel coverage with auto-generated data file suffixes and
                # combinations.
                cov.config.parallel = True
            cov.start()

        profiler = None
        if self.cs["profile"]:
            profiler = cProfile.Profile()
            profiler.enable(subcalls=True, builtins=True)

        self.checkInputs()
        o = self.initializeOperator()

        with o:
            if self.cs["trace"] and armi.MPI_RANK == 0:
                # only trace master node.
                tracer = trace.Trace(ignoredirs=[sys.prefix, sys.exec_prefix], trace=1)
                tracer.runctx("o.operate()", globals(), locals())
            else:
                o.operate()

        if profiler is not None:
            profiler.disable()
            profiler.dump_stats("profiler.{:0>3}.stats".format(armi.MPI_RANK))
            statsStream = six.StringIO()
            summary = pstats.Stats(profiler, stream=statsStream).sort_stats(
                "cumulative"
            )
            summary.print_stats()
            if armi.MPI_SIZE > 0:
                allStats = armi.MPI_COMM.gather(statsStream.getvalue(), root=0)
                if armi.MPI_RANK == 0:
                    for rank, statsString in enumerate(allStats):
                        # using print statements because the logger has been turned off
                        print("=" * 100)
                        print(
                            "{:^100}".format(
                                " Profiler statistics for RANK={} ".format(rank)
                            )
                        )
                        print(statsString)
                        print("=" * 100)
            else:
                print(statsStream.getvalue())

        if cov is not None:
            cov.stop()
            cov.save()

            if armi.MPI_SIZE > 1:
                armi.MPI_COMM.barrier()  # force waiting for everyone to finish

            if armi.MPI_RANK == 0 and armi.MPI_SIZE > 1:
                # combine all the parallel coverage data files into one and make
                # the XML and HTML reports for the whole run.
                combinedCoverage = coverage.Coverage(
                    config_file=os.path.join(armi.RES, "coveragerc"), debug=["dataio"]
                )
                combinedCoverage.config.parallel = True
                # combine does delete the files it merges
                combinedCoverage.combine()
                combinedCoverage.save()
                combinedCoverage.html_report()
                combinedCoverage.xml_report()

    def initializeOperator(self, r=None):
        """Creates and returns an Operator."""
        with DirectoryChanger(self.cs.inputDirectory):
            self._initBurnChain()
            o = operators.factory(self.cs)
            if not r:
                r = reactors.factory(self.cs, self.bp)
            o.initializeInterfaces(r)
            # Set this here to make sure the full duration of initialization is properly captured.
            # Cannot be done in reactors since the above self.bp call implicitly initializes blueprints.
            r.core.timeOfStart = self._startTime
            return o

    def _initBurnChain(self):
        """
        Apply the burn chain setting to the nucDir.

        Notes
        -----
        This is admittedly an odd place for this but the burn chain info must be
        applied sometime after user-input has been loaded (for custom burn chains)
        but not long after (because nucDir is framework-level and expected to be
        up-to-date by lots of modules).
        """
        with open(self.cs["burnChainFileName"]) as burnChainStream:
            nuclideBases.imposeBurnChain(burnChainStream)

    def checkInputs(self):
        """
        Checks ARMI inputs for consistency.

        Returns
        -------
        bool
            True if the inputs are all good, False otherwise
        """
        with DirectoryChanger(self.cs.inputDirectory):
            operatorClass = operators.getOperatorClassFromSettings(self.cs)
            inspector = operatorClass.inspector(self.cs)
            inspectorIssues = [query for query in inspector.queries if query]
            if armi.CURRENT_MODE == armi.Mode.Interactive:
                # if interactive, ask user to deal with settings issues
                inspector.run()
            else:
                # when not interactive, just print out the info in the stdout
                queryData = []
                for i, query in enumerate(inspectorIssues, start=1):
                    queryData.append(
                        (
                            i,
                            textwrap.fill(
                                query.statement, width=50, break_long_words=False
                            ),
                            textwrap.fill(
                                query.question, width=50, break_long_words=False
                            ),
                        )
                    )

                if queryData:
                    runLog.header("=========== Settings Input Queries ===========")
                    runLog.info(
                        tabulate.tabulate(
                            queryData,
                            headers=["Number", "Statement", "Question"],
                            tablefmt="armi",
                        )
                    )

            return not any(inspectorIssues)

    def summarizeDesign(self, generateFullCoreMap=True, showBlockAxialMesh=True):
        """Uses the ReportInterface to create a fancy HTML page describing the design inputs."""
        settings.setMasterCs(self.cs)
        o = self.initializeOperator()
        with DirectoryChanger(self.cs.inputDirectory):
            # There are global variables that are modified when a report is
            # generated, so reset it all
            six.moves.reload_module(report)  # pylint: disable=too-many-function-args
            self.cs.setSettingsReport()
            rpi = o.getInterface("report")

            if rpi is None:
                rpi = reportInterface.ReportInterface(o.r, o.cs)

            rpi.generateDesignReport(generateFullCoreMap, showBlockAxialMesh)
            report.DESIGN.writeHTML()
            runLog.important("Design report summary was successfully generated")

    def buildCommand(self, python="python"):
        """
        Build an execution command for running or submitting a job.

        Parameters
        ----------
        python : str, optional
            The path to the python executable to use for executing the case. By default
            this will be whatever "python" resolves to in the target environment.
            However when running in more exotic environments (e.g. HPC cluster), it is
            usually desireable to provide a specific python executable.
        """
        command = ""
        if self.cs["numProcessors"] > 1:
            command += "mpiexec -n {} ".format(self.cs["numProcessors"])
            if self.cs["mpiTasksPerNode"] > 0:
                command += "-c {} ".format(self.cs["mpiTasksPerNode"])

        command += "{} -u ".format(python)
        if not __debug__:
            command += " -O "
        command += ' -m {} run "{}.yaml"'.format(
            armi.context.APP_NAME, self.cs.caseTitle
        )

        return command

    def clone(self, additionalFiles=None, title=None, modifiedSettings=None):
        """
        Clone existing ARMI inputs to current directory with optional settings modifications.

        Since each case depends on multiple inputs, this is a safer way to move cases
        around without having to wonder if you copied all the files appropriately.

        Parameters
        ----------
        additionalFiles : list (optional)
            additional file paths to copy to cloned case
        title : str (optional)
            title of new case
        modifiedSettings : dict (optional)
            settings to set/modify before creating the cloned case

        Raises
        ------
        RuntimeError
            If the source and destination are the same

        """
        cloneCS = self.cs.duplicate()

        if modifiedSettings is not None:
            cloneCS.update(modifiedSettings)

        clone = Case(cloneCS)
        clone.cs.path = pathTools.armiAbsPath(title or self.title) + ".yaml"

        if pathTools.armiAbsPath(clone.cs.path) == pathTools.armiAbsPath(self.cs.path):
            raise RuntimeError(
                "The source file and destination file are the same: {}\n"
                "Cannot use armi-clone to modify armi settings file.".format(
                    pathTools.armiAbsPath(clone.cs.path)
                )
            )

        runLog.important("writing settings file {}".format(clone.cs.path))
        clone.cs.writeToYamlFile(clone.cs.path)
        runLog.important("finished writing {}".format(clone.cs))

        fromPath = lambda fname: pathTools.armiAbsPath(self.cs.inputDirectory, fname)

        for inputFileSetting in ["loadingFile", "geomFile"]:
            fileName = self.cs[inputFileSetting]
            if fileName:
                pathTools.copyOrWarn(
                    inputFileSetting,
                    fromPath(fileName),
                    os.path.join(clone.cs.inputDirectory, fileName),
                )
            else:
                runLog.warning(
                    "skipping {}, there is no file specified".format(inputFileSetting)
                )

        copyInterfaceInputs(self.cs, clone.cs.inputDirectory)

        with open(self.cs["loadingFile"], "r") as f:
            for includePath, mark in textProcessors.findYamlInclusions(
                f, root=pathlib.Path(self.cs.inputDirectory)
            ):
                if not includePath.exists():
                    raise OSError(
                        "The input file file `{}` referenced at {} does not exist.".format(
                            includePath, mark
                        )
                    )
                pathTools.copyOrWarn(
                    "auxiliary input file `{}` referenced at {}".format(
                        includePath, mark
                    ),
                    fromPath(includePath),
                    clone.cs.inputDirectory,
                )

        for fileName in additionalFiles or []:
            pathTools.copyOrWarn(
                "additional file", fromPath(fileName), clone.cs.inputDirectory
            )

        return clone

    def compare(
        self,
        that,
        exclusion: Optional[Sequence[str]] = None,
        weights=None,
        tolerance=0.01,
        timestepMatchup=None,
        output="",
    ) -> int:
        """
        Compare the output databases from two run cases. Return number of differences.

        This is useful both for in-use testing and engineering analysis.
        """
        runLog.info(
            "Comparing the following databases:\n"
            "REF: {}\n"
            "SRC: {}".format(self.dbName, that.dbName)
        )
        diffResults = compareDatabases(
            self.dbName, that.dbName, tolerance=tolerance, exclusions=exclusion
        )

        code = 1 if diffResults is None else diffResults.nDiffs()

        sameOrDifferent = (
            "different"
            if diffResults is None or diffResults.nDiffs() > 0
            else "the same"
        )
        runLog.important("Cases are {}.".format(sameOrDifferent))

        return code

    def writeInputs(self, sourceDir: Optional[str] = None):
        """
        Write the inputs to disk.

        This allows input objects that have been modified in memory (e.g.
        for a parameter sweep or migration) to be written out as input
        for a forthcoming case.

        Parameters
        ----------
        sourceDir : str, optional
            The path to copy inputs from (if different from the cs.path). Needed
            in SuiteBuilder cases to find the baseline inputs from plugins (e.g. shuffleLogic)

        Notes
        -----
        This will rename the ``loadingFile`` and ``geomFile`` to be ``title-blueprints + '.yaml'`` and
        ``title + '-geom.yaml'`` respectively.

        See Also
        --------
        independentVariables
            parses/reads the independentVariables setting

        clone
            Similar to this but doesn't let you write out new/modified
            geometry or blueprints objects
        """
        with ForcedCreationDirectoryChanger(self.cs.inputDirectory):
            # trick: these seemingly no-ops load the bp and geom via properties if
            # they are not yet initialized.
            self.bp
            self.geom
            self.cs["loadingFile"] = self.title + "-blueprints.yaml"
            if self.geom:
                self.cs["geomFile"] = self.title + "-geom.yaml"
                self.geom.writeGeom(self.cs["geomFile"])
            if self.independentVariables:
                self.cs["independentVariables"] = [
                    "({}, {})".format(repr(varName), repr(val))
                    for varName, val in self.independentVariables.items()
                ]

            with open(self.cs["loadingFile"], "w") as loadingFile:
                blueprints.Blueprints.dump(self.bp, loadingFile)

            # copy input files from other modules (e.g. fuel management, control logic, etc.)
            copyInterfaceInputs(self.cs, ".", sourceDir)

            self.cs.writeToYamlFile(self.title + ".yaml")


def copyInterfaceInputs(cs, destination: str, sourceDir: Optional[str] = None):
    """
    Copy sets of files that are considered "input" from each active interface.

    This enables developers to add new inputs in a plugin-dependent/
    modular way.
    """
    activeInterfaces = interfaces.getActiveInterfaceInfo(cs)
    sourceDir = sourceDir or cs.inputDirectory
    for klass, kwargs in activeInterfaces:
        if not kwargs.get("enabled", True):
            # Don't consider disabled interfaces
            continue
        interfaceFileNames = klass.specifyInputs(cs)
        for label, fileNames in interfaceFileNames.items():
            for f in fileNames:
                if not f:
                    continue
                pathTools.copyOrWarn(
                    label,
                    pathTools.armiAbsPath(sourceDir, f),
                    os.path.join(destination, f),
                )
