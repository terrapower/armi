# Copyright 2026 TerraPower, LLC
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

"""All data in the material YAMLs need to have a reference for the information source."""

UNDEFINED_REF_DATA = "NONE"


class Reference:
    """
    A container for the source of the material's data. The Reference class is used to manage the material data's source
    information and have methods to extract the data for generating the reference section of documentation.
    """

    def __init__(self):
        self._ref = ""
        """Entire reference in a single string"""

        self._type = ""
        """Type of document (open literature|export controlled|test|your company name)"""

    def __repr__(self):
        if not self._ref:
            return UNDEFINED_REF_DATA
        elif not self._type:
            return self._ref
        else:
            return f"{self._ref} ({self._type})"

    @staticmethod
    def _factory(node):
        """
        Sets Reference data from a given reference node.

        Parameters
        ----------
        node: dict
            Dictionary representing a child element from the "references" node.

        Returns
        -------
        Reference
            Reference object with data parsed from node.
        """
        reference = Reference()

        ref_node = node["ref"]
        if ref_node:
            reference._ref = str(ref_node)  # noqa: SLF001

        type_node = node["type"]
        if type_node:
            reference._type = str(type_node)  # noqa: SLF001

        return reference

    def get_ref(self):
        """Accessor which returns _ref value."""
        return self._ref

    def get_type(self):
        """Accessor which returns _type value."""
        return self._type
