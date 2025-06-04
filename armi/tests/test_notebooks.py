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
Tests to make sure ipynb notebooks still execute.

There is a pytest plugin that can run notebooks but that
assumes each cell is a test. To prevent inadvertent breaking
of the ipynbs, we imply run them here and show during unit
testing that a failure was introduced.
"""

import os
import unittest

import nbformat
from nbconvert.preprocessors import ExecutePreprocessor

from armi.tests import TEST_ROOT

TUTORIALS = os.path.join(TEST_ROOT, "tutorials")
ANL_ACFI_177 = os.path.join(TEST_ROOT, "anl-afci-177")


class NotebookTests(unittest.TestCase):
    def test_runParamSweep(self):
        runNotebook(os.path.join(TUTORIALS, "param_sweep.ipynb"))

    def test_runDataModel(self):
        runNotebook(os.path.join(TUTORIALS, "data_model.ipynb"))
        # Do some cleanup because some code run in the notebook doesn't honor the
        # TempDirectoryChanger
        os.remove(os.path.join(TUTORIALS, "anl-afci-177.h5"))


def runNotebook(filename):
    """Run a jupyter notebook."""
    with open(filename) as f:
        nb = nbformat.read(f, as_version=4)
    ep = ExecutePreprocessor(timeout=600, kernel_name="python3")
    ep.preprocess(nb, {"metadata": {"path": TUTORIALS}})
