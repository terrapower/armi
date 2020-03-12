"""
Executors are useful for having a standard way to run physics calculations.

They may involve external codes (with inputs/execution/output) or in-memory
data pathways.
"""

import os

from armi.utils import directoryChangers
from armi import runLog


class ExecutionOptions:
    """
    A data structure representing all options needed for a physics kernel.

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
        self.applyResultsToReactor = True
        self.paramsToScaleSubset = None

    def fromUserSettings(self, cs):
        """Set options from a particular CaseSettings object."""
        raise NotImplementedError()

    def fromReactor(self, reactor):
        """Set options from a particular reactor object."""
        raise NotImplementedError()

    def resolveDerivedOptions(self):
        """Called by executers right before executing."""

    def describe(self):
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
        # must either write input to CWD for analysis and then copy to runDir
        # or not list it in inputs (for optimization)
        self.writeInput()
        with directoryChangers.ForcedCreationDirectoryChanger(
            self.options.runDir, filesToMove=inputs, filesToRetrieve=outputs
        ) as dc:
            self.options.workingDir = dc.initial
            self._execute()
            output = self._readOutput()
            if self.options.applyResultsToReactor:
                output.apply(self.r)
        self._undoGeometryTransformations()
        return output

    def _collectInputsAndOutputs(self):
        """Get total lists of input and output files."""
        inputs = [self.options.inputFile] if self.options.inputFile else []
        inputs.extend(self.options.extraInputFiles)
        outputs = [self.options.outputFile] if self.options.outputFile else []
        outputs.extend(self.options.extraOutputFiles)
        return inputs, outputs

    def _execute(self):
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
