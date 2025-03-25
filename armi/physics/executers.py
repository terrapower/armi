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
Executors are useful for having a standard way to run physics calculations.

They may involve external codes (with inputs/execution/output) or in-memory
data pathways.
"""
import hashlib
import os

from armi import runLog
from armi.context import MPI_RANK, getFastPath
from armi.utils import directoryChangers, pathTools


class ExecutionOptions:
    """
    A data structure representing all options needed for a physics kernel.

    .. impl:: Options for executing external calculations.
        :id: I_ARMI_EX0
        :implements: R_ARMI_EX

        Implements a basic container to hold and report options to be used in
        the execution of an external code (see :need:`I_ARMI_EX1`).
        Options are stored as instance attributes and can be dumped as a string
        using :py:meth:`~armi.physics.executers.ExecutionOptions.describe`, which
        will include the name and value of all public attributes of the instance.

        Also facilitates the ability to execute parallel instances of a code by
        providing the ability to resolve a ``runDir`` that is aware of the
        executing MPI rank. This is done via :py:meth:`~armi.physics.executers.ExecutionOptions.setRunDirFromCaseTitle`,
        where the user passes in a ``caseTitle`` string, which is hashed and combined
        with the MPI rank to provide a unique directory name to be used by each parallel
        instance.

    Attributes
    ----------
    inputFile : str
        Name of main input file. Often passed to stdin of external code.
    outputFile : str
        Name of main output file. Often the stdout of external code.
    extraInputFiles : list of tuples
        (sourceName, destName) pairs of file names that will be brought from the
        working dir into the runDir. Allows renames while in transit.
    extraOutputFiles : list of tuples
        (sourceName, destName) pairs of file names that will be extracted from the
        runDir to the working dir
    executablePath : str
        Path to external executable to run (if external code is used)
    runDir : str
        Path on running system where the run will take place. This is often used
        to ensure external codes that use hard-drive disk space run on a local disk
        rather than a shared network drive
    workingDir : str
        Path on system where results will be placed after the run. This is often
        a shared network location. Auto-applied during execution by default.
    label : str
        A name for the run that may be used as a prefix for input/output files generated.
    interface : str
        A name for the interface calling the Executer that may be used to organize the
        input/output files generated within sub-folders under the working directory.
    savePhysicsFiles : bool
        Dump the physics kernel I/O files from the execution to a dedicated directory that
        will not be overwritten so they will be available after the run.
    copyOutput : bool
        Copy the output from running the executable back to the working directory.
    applyResultsToReactor : bool
        Update the in-memory reactor model with results upon completion. Set to False
        when information from a run is needed for auxiliary purposes rather than progressing
        the reactor model.
    """

    def __init__(self, label=None):
        self.inputFile = None
        self.outputFile = None
        self.extraInputFiles = []
        self.extraOutputFiles = []
        self.executablePath = None
        self.runDir = None
        self.workingDir = None
        self.label = label
        self.interfaceName = None
        self.applyResultsToReactor = True
        self.paramsToScaleSubset = None
        self.savePhysicsFiles = False
        self.copyOutput = True

    def __repr__(self):
        return f"<{self.__class__.__name__}: {self.label}>"

    def fromUserSettings(self, cs):
        """Set options from a particular Settings object."""
        raise NotImplementedError()

    def fromReactor(self, reactor):
        """Set options from a particular reactor object."""
        raise NotImplementedError()

    def resolveDerivedOptions(self):
        """Called by executers right before executing."""

    def setRunDirFromCaseTitle(self, caseTitle: str) -> None:
        """
        Set run directory derived from case title and label.

        This is optional (you can set runDir to whatever you want). If you
        use this, you will get a relatively consistent naming convention
        for your fast-path folders.
        """
        # This creates a hash of the case title plus the label
        # to shorten the running directory and to avoid path length
        # limitations on the OS.
        caseString = f"{caseTitle}-{str(self.label)}".encode("utf-8")
        caseTitleHash = str(hashlib.sha1(caseString).hexdigest())[:8]
        self.runDir = os.path.join(getFastPath(), f"{caseTitleHash}-{MPI_RANK}")

    def describe(self) -> str:
        """Make a string summary of all options."""
        lines = ["Options summary:", "----------------"]
        for key, val in sorted(self.__dict__.items()):
            if not key.startswith("_"):
                lines.append(f"  {key:40s}{str(val)[:80]:80s}")
        return "\n".join(lines)


class Executer:
    """
    Short-lived object that coordinates a calculation step and updates a reactor.

    Notes
    -----
    This is deliberately **not** a :py:class:`~mpiActions.MpiAction`. Thus, Executers can run as
    potentially multiple steps in a parent (parallelizable ) MpiAction or in other flexible
    ways. This is intended to maximize reusability.
    """

    def __init__(self, options, reactor):
        self.options = options
        self.r = reactor
        self.dcType = directoryChangers.TemporaryDirectoryChanger

    def run(self):
        """
        Run the executer steps.

        This should use the current state of the reactor as input,
        perform some kind of calculation, and update the reactor
        with the output.
        """
        raise NotImplementedError()


class DefaultExecuter(Executer):
    """
    An Executer that uses a common run sequence.

    This sequence has been found to be relatively common in many
    externally-executed physics codes. It is here for convenience
    but is not required. The sequence look like:

    * Choose modeling options (either from the global run settings input or dictated programmatically)
    * Apply geometry transformations to the ARMI Reactor as needed
    * Build run-specific working directory
    * Write input file(s)
    * Put specific input files and libs in run directory
    * Run the analysis (external execution, or not)
    * Process output while still in run directory
    * Check error conditions
    * Move desired output files back to main working directory
    * Clean up run directory
    * Un-apply geometry transformations as needed
    * Update ARMI data model as desired

    .. impl:: Default tool for executing external calculations.
        :id: I_ARMI_EX1
        :implements: R_ARMI_EX

        Facilitates the execution of external calculations by accepting ``options`` (an
        :py:class:`~armi.physics.executers.ExecutionOptions` object) and providing
        methods that build run directories and execute a code based on the values in
        ``options``.

        The :py:meth:`~armi.physics.executers.DefaultExecuter.run` method will first
        resolve any derived options in the ``options`` object and check if the specified
        ``executablePath`` option is valid, raising an error if not. If it is,
        preparation work for executing the code is performed, such as performing any geometry
        transformations specified in subclasses or building the directories needed
        to save input and output files. Once the temporary working directory is created,
        the executer moves into it and runs the external code, applying any results
        from the run as specified in subclasses.

        Finally, any geometry perturbations that were performed are undone.
    """

    def run(self):
        """
        Run the executer steps.

        .. warning::
                If a calculation requires anything different from what this method does,
                do not update this method with new complexity! Instead, simply make your own
                run sequence and/or class. This pattern is useful only in that it is fairly simple.
                By all means, do use ``DirectoryChanger`` and ``ExecuterOptions``
                and other utilities.
        """
        self.options.resolveDerivedOptions()
        runLog.debug(self.options.describe())
        if self.options.executablePath and not os.path.exists(
            self.options.executablePath
        ):
            raise IOError(
                f"Required executable `{self.options.executablePath}` not found for {self}"
            )
        self._performGeometryTransformations()
        inputs, outputs = self._collectInputsAndOutputs()
        state = f"c{self.r.p.cycle}n{self.r.p.timeNode}"
        dirName = self.options.interfaceName or self.options.label
        if self.options.savePhysicsFiles:
            outputDir = os.path.join(pathTools.armiAbsPath(os.getcwd()), state, dirName)
        else:
            outputDir = pathTools.armiAbsPath(os.getcwd())
        # must either write input to CWD for analysis and then copy to runDir
        # or not list it in inputs (for optimization)
        self.writeInput()
        with self.dcType(
            self.options.runDir,
            filesToMove=inputs,
            filesToRetrieve=outputs,
            outputPath=outputDir,
        ) as dc:
            self.options.workingDir = dc.initial
            self._updateRunDir(dc.destination)
            self._execute()
            output = self._readOutput()
            if self.options.applyResultsToReactor:
                output.apply(self.r)
        self._undoGeometryTransformations()
        return output

    def _updateRunDir(self, directory):
        """
        If a ``TemporaryDirectoryChanger`` is used, the ``runDir`` needs to be updated.

        If a ForcedCreationDirectoryChanger is used instead, nothing needs to be done.

        Parameters
        ----------
        directory : str
            New path for runDir
        """
        if self.dcType == directoryChangers.TemporaryDirectoryChanger:
            self.options.runDir = directory

    def _collectInputsAndOutputs(self):
        """
        Get total lists of input and output files.

        If self.options.copyOutput is false, don't copy the main `outputFile` back from
        the working directory.

        In some ARMI runs, the executer can be run hundreds or thousands of times and
        generate many output files that aren't strictly necessary to keep around. One
        can save space by choosing not to copy the outputs back in these special cases.
        ``extraOutputFiles`` are typically controlled by the subclass, so the copyOutput
        option only affects the main ``outputFile``.

        """
        inputs = [self.options.inputFile] if self.options.inputFile else []
        inputs.extend(self.options.extraInputFiles)
        if self.options.outputFile and self.options.copyOutput:
            outputs = [self.options.outputFile]
        else:
            outputs = []
        outputs.extend(self.options.extraOutputFiles)
        return inputs, outputs

    def _execute(self) -> bool:
        runLog.extra(
            f"Executing {self.options.executablePath}\n"
            f"\tInput: {self.options.inputFile}\n"
            f"\tOutput: {self.options.outputFile}\n"
            f"\tWorking dir: {self.options.runDir}"
        )
        return True

    def writeInput(self):
        pass

    def _readOutput(self):
        raise NotImplementedError()

    def _applyOutputToDataModel(self, output):
        pass

    def _performGeometryTransformations(self):
        pass

    def _undoGeometryTransformations(self):
        pass
