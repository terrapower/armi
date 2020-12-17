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

from typing import Generator, Tuple
from armi.settings import caseSettings
from armi.reactor import systemLayoutInput


class Database:
    """Abstract class defining the common interface for all Database implementations.

    Notes
    -----
    This is a pretty anemic set of interfaces, since the different implementations can
    vary wildly. For now these are the bare minimum interfaces that should be needed to
    convert one Database format to another, and serve as a common ancestor."""

    def loadCS(self) -> caseSettings.Settings:
        raise NotImplementedError()

    # Cannot annotate type, because cannot import blueprints, because blueprints cannot
    # be imported until after plugins are registered, and this module gets imported by
    # plugins as they are being registered.
    def loadBlueprints(self):
        raise NotImplementedError()

    def loadGeometry(self) -> systemLayoutInput.SystemLayoutInput:
        raise NotImplementedError()

    def genTimeSteps(self) -> Generator[Tuple[int, int], None, None]:
        """Get a sequence of tuples (cycle, node) that are contained in the database."""
        raise NotImplementedError()

    def genAuxiliaryData(self, ts: Tuple[int, int]) -> Generator[str, None, None]:
        """
        Get a sequence of auxiliary dataset/group names for the passed time step.

        Returns
        -------
        Generator[str]
            A generator that produces **absolute** paths to the auxiliary data.
            Absolute names make it easier for a database version-agnostic converter to
            find the actual data.
        """
        raise NotImplementedError()

    def getAuxiliaryDataPath(self, ts: Tuple[int, int], name: str) -> str:
        """
        Get a string describing a path to an auxiliary data location.

        Parameters
        ----------
        ts
            The time step that the auxiliary data belongs to

        name
            The name of the auxiliary data

        Returns
        -------
        str
            An absolute location for storing auxiliary data with the given name for the
            given time step
        """
        raise NotImplementedError()

    def writeInputsToDB(self, cs, csString=None, geomString=None, bpString=None):
        raise NotImplementedError()

    def readInputsFromDB(self):
        raise NotImplementedError()

    def writeToDB(self, reactor, statePointName=None):
        raise NotImplementedError()

    def close(self):
        raise NotImplementedError()
