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
"""Dynamic importing help."""


def getEntireFamilyTree(cls):
    """Returns a list of classes subclassing the input class.

    One large caveat is it can only locate subclasses that had been imported somewhere
    Look to use importEntirePackage before searching for subclasses if not all children
    are being found as expected.
    """
    return cls.__subclasses__() + [
        grandchildren for child in cls.__subclasses__() for grandchildren in getEntireFamilyTree(child)
    ]
