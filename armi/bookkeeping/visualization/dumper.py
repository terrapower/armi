# Copyright 2020 TerraPower, LLC
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
"""Abstract base class for visualization file dumpers."""

from abc import ABC, abstractmethod

from armi.reactor import reactors


class VisFileDumper(ABC):
    @abstractmethod
    def dumpState(self, r: reactors.Reactor):
        """Dump a single reactor state to the vis file."""

    @abstractmethod
    def __enter__(self):
        """Invoke initialize when entering a context manager."""

    @abstractmethod
    def __exit__(self, type, value, traceback):
        """Invoke initialize when entering a context manager."""
