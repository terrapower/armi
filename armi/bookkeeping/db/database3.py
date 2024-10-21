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
"""
Temporary placeholder, to support backwards compatibility of the API.

We are moving from the name "Database3" to just "Database". As this is an API breaking change, this
file exists to streamline and ease the transition.
"""
# ruff: noqa: F403, F405
from armi.bookkeeping.db.database import *


class Database3(Database):
    """Temporary placeholder to ease the API-breaking transition from Database3 to Database."""

    pass
