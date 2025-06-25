# Copyright 2024 TerraPower, LLC
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
"""This is a placeholder file that only exists to provide backwards compatibility.

Notes
-----
The actual ``settingsValidation.py`` module has been move to ``armi/settings/``. For now, this file will
provide backwards compatibility.

Warning
-------
DeprecationWarning: This file will disappear in early 2025.
"""
# ruff: noqa: F401

from armi.settings.settingsValidation import (
    Inspector,
    Query,
    createQueryRevertBadPathToDefault,
)
