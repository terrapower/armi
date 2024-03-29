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
"""This is a temporary file created to ease a long API transition.

Originally, the ``Database3`` class existed as a temporary naming stop-gap as ARMI transitioned from
one version of a "Database" class to another. But, for reasons lost to history, the "Database3" name
stuck.

However, it would be a painful effort if ARMI just renamed this class now. That's why this file
exists; to allow for a long, slow API deprecation.
"""
# ruff: noqa: F403
from armi.bookkeeping.db.database import *


# ruff: noqa: F405
class Database3(Database):
    pass
