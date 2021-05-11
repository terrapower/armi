"""
Tests to make sure ipynb notebooks still execute.

There is a pytest plugin that can run notebooks but that
assumes each cell is a test. To prevent inadvertent breaking
of the ipynbs, we imply run them here and show during unit
testing that a failure was introduced.
"""
import unittest
import os

import nbformat
from nbconvert.preprocessors import ExecutePreprocessor

from armi.tests import TEST_ROOT

TUTORIALS = os.path.join(TEST_ROOT, "tutorials")


class NotebookTests(unittest.TestCase):
    def test_runParamSweep(self):
        runNotebook(os.path.join(TUTORIALS, "param_sweep.ipynb"))

    def test_runDataModel(self):
        runNotebook(os.path.join(TUTORIALS, "data_model.ipynb"))


def runNotebook(filename):
    """Run a jupyter notebook."""
    with open(filename) as f:
        nb = nbformat.read(f, as_version=4)
    ep = ExecutePreprocessor(timeout=600, kernel_name="python3")
    ep.preprocess(nb, {"metadata": {"path": TUTORIALS}})
