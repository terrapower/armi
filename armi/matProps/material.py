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

"""How matProps defines a material class."""

import hashlib
from pathlib import Path

import matProps.property
from matProps.constituent import Constituent
from matProps.function import Function
from matProps.materialType import MaterialType
from matProps.property import Property
from ruamel.yaml import YAML


class Material:
    """
    The Material class is a generic container for all Material types, whether they contain ASME properties, fluid
    properties, or steel properties.

    It may be necessary to have multiple Material definitions for a single material containing different phases.
    """

    valid_file_format_versions = [3.0, "TESTS"]

    def __init__(self):
        """Constructor for Material class."""
        self._saved = False
        """Boolean denoting whether or not Material object is saved in materials dict."""

        self.material_type = None
        """Enum represting type for the Material object"""

        self.composition = []
        """List of Constituent objects representing composition of Material."""

        self.name = None
        """Name of Material object."""

        self._sha1 = None
        """SHA1 value of parsed material file."""

    def __repr__(self):
        """Provides string representation for Material class."""
        return f"<Material {self.name} {str(self.material_type)}>"

    def saved(self) -> bool:
        """
        Returns a bool value indicating whether the Material has been stored internally in the matProps.materials map
        via matProps.add_material().
        """
        return self._saved

    def save(self):
        """Sets Material._saved flag to True."""
        self._saved = True

    @staticmethod
    def data_check_material_file(file_path, root_node):
        """
        This is a partial data check of the material data file.

        Checks the first level of data keywords and also check that the file format is a valid version.

        Parameters
        ----------
        file_path: str
            Path containing name of YAML file whose file format and property nodes are checked.
        root_node: dict
            Root YAML node of file parsed from file_path.
        """
        file_format = Material.get_node(root_node, "file format")
        if file_format not in Material.valid_file_format_versions:
            msg = f"Invalid file format version `{file_format}` used in: {file_path}"
            raise ValueError(msg)

        for prop_name in root_node:
            if prop_name in {"composition", "material type", "file format"}:
                continue

            if not Property.contains(prop_name):
                msg = f"Invalid property node `{prop_name}` found in: {file_path}"
                raise KeyError(msg)

    @staticmethod
    def get_valid_file_format_versions():
        """Get a vector of strings with all of the valid file format versions."""
        return Material.valid_file_format_versions

    @staticmethod
    def get_node(node, subnode_name):
        """
        Searches a node for a child element and returns it.

        Parameters
        ----------
        node: dict
            Parent level node from which a child element is searched.
        subnode_name: str
            Name of the child element that is queried from node.
        """
        if subnode_name not in node:
            msg = f"Missing YAML node `{subnode_name}`"
            raise KeyError(msg)

        return node[subnode_name]

    def load_file(self, file_path: str):
        """
        Loads yaml file and parses information to fill in Material data members including all relevant Function objects.

        Parameters
        ----------
        file_path: str
            Path containing name of YAML file to parse.
        """
        # load the YAML file
        y = YAML(pure=True)
        node = y.load(Path(file_path))

        # grab the material name from the file name
        n = Path(file_path).name
        if n.endswith(".yaml"):
            n = n[:-5]
        elif n.endswith(".yml"):
            n = n[:-4]
        self.name = n

        # Generate SHA1 value and set data member.
        sha1 = hashlib.sha1()
        with open(file_path, "rb") as materialFile:
            sha1.update(materialFile.read())
        self._sha1 = sha1.hexdigest()

        self.data_check_material_file(file_path, node)
        self.material_type = MaterialType.from_string(self.get_node(node, "material type"))

        self.composition = Constituent._parse_composition(  # noqa: SLF001
            self.get_node(node, "composition")
        )

        for p in matProps.property.properties:
            if p.name and p.name in node:
                setattr(
                    self,
                    p.symbol,
                    Function._factory(self, node[p.name], p),  # noqa: SLF001
                )
            else:
                # Any property not in the input file will be set to None.
                setattr(self, p.symbol, None)

    def print_sha1(self):
        """Prints the sha1 value and saved status of a Material instance."""
        if self.saved():
            status = "is"
        else:
            status = "is not"
        print(f"SHA1 value for material {self.name} is {self._sha1}. Material {status} saved into matProps.\n")
