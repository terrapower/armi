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
Case and CaseSuite objects for running and analyzing ARMI cases.

A ``Case`` is a collection of inputs that represents one particular run. Cases have special knowledge about dependencies
and can perform useful operations like compare, clone, and run.

A ``CaseSuite`` is a set of (often related) Cases. These are fundamental to parameter sweeps and test suites.

See Also
--------
armi.cli : Entry points that build Cases and/or CaseSuites and send them off to do work
armi.operators : Operations that ARMI will perform on a reactor model.
    Generally these are made by an individual Case.

Examples
--------
Create a Case and run it::

    case = Case(settings.Settings("path-to-settings.yaml"))
    case.run()

    # do something with output database

Create a case suite from existing files, and run the suite::

    cs = settings.Settings()  # default settings
    suite = CaseSuite(settings.Settings())  # default settings
    suite.discover("my-cases*.yaml", recursive=True)
    suite.run()

.. warning:: Suite running may not work yet if the cases have interdependencies.

Create a ``burnStep`` sensitivity study from some base CS::

    baseCase = Case(settings.Settings("base-settings.yaml"))  # default settings
    suite = CaseSuite(baseCase.cs)  # basically just sets armiLocation

    for numSteps in range(3, 11):
        with ForcedCreationDirectoryChanger("{}steps".format(numSteps)):
            case = baseCase.clone(title=baseCase.title + f"-with{numSteps}steps", settings={"burnSteps": numSteps})
            suite.add(case)

    suite.writeInputs()

Then submit the inputs to your HPC cluster.
"""

from armi.cases.case import Case  # noqa: F401
from armi.cases.suite import CaseSuite  # noqa: F401
