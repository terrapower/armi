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

from ruamel.yaml import YAML

import armi.matProps.property
from armi.matProps.constituent import Constituent
from armi.matProps.function import Function
from armi.matProps.materialType import MaterialType
from armi.matProps.property import Property


class Material:
    """
    The Material class is a generic container for all Material types, whether they contain ASME properties, fluid
    properties, or steel properties.

    It may be necessary to have multiple Material definitions for a single material containing different phases.
    """

    validFileFormatVersions = [3.0, "TESTS"]

    def __init__(self):
        """Constructor for Material class."""
        self._saved = False
        """Boolean denoting whether or not Material object is saved in materials dict."""

        self.materialType = None
        """Enum represting type for the Material object"""

        self.composition = []
        """List of Constituent objects representing composition of Material."""

        self.name = None
        """Name of Material object."""

        self._sha1 = None
        """SHA1 value of parsed material file."""

    def __repr__(self):
        """Provides string representation for Material class."""
        return f"<Material {self.name} {str(self.materialType)}>"

    def hash(self) -> str:
        """Returns the SHA1 hash value of a Material instance."""
        return self._sha1

    def saved(self) -> bool:
        """
        Returns a bool value indicating whether the Material has been stored internally in the matProps.materials map
        via matProps.addMaterial().
        """
        return self._saved

    def save(self):
        """Sets Material._saved flag to True."""
        self._saved = True

    @staticmethod
    def dataCheckMaterialFile(filePath, rootNode):
        """
        This is a partial data check of the material data file.

        Checks the first level of data keywords and also check that the file format is a valid version.

        Parameters
        ----------
        filePath: str
            Path containing name of YAML file whose file format and property nodes are checked.
        rootNode: dict
            Root YAML node of file parsed from filePath.
        """
        file_format = Material.getNode(rootNode, "file format")
        if file_format not in Material.validFileFormatVersions:
            msg = f"Invalid file format version `{file_format}` used in: {filePath}"
            raise ValueError(msg)

        for propName in rootNode:
            if propName in {"composition", "material type", "file format"}:
                continue

            if not Property.contains(propName):
                msg = f"Invalid property node `{propName}` found in: {filePath}"
                raise KeyError(msg)

    @staticmethod
    def getValidFileFormatVersions():
        """Get a vector of strings with all of the valid file format versions."""
        return Material.validFileFormatVersions

    @staticmethod
    def getNode(node: dict, subnodeName: str):
        """
        Searches a node for a child element and returns it.

        Parameters
        ----------
        node: dict
            Parent level node from which a child element is searched.
        subnodeName: str
            Name of the child element that is queried from node.
        """
        if subnodeName not in node:
            msg = f"Missing YAML node `{subnodeName}`"
            raise KeyError(msg)

        return node[subnodeName]

    def loadNode(self, node: dict):
        """
        Loads YAML and parses information to fill in Material data members including all relevant Function objects.

        Parameters
        ----------
        node: dict
            Material defition, like a YAML taht become a dict.
        """
        self.materialType = MaterialType.fromString(self.getNode(node, "material type"))
        self.composition = Constituent.parseComposition(self.getNode(node, "composition"))

        for p in armi.matProps.property.properties:
            if p.name and p.name in node:
                setattr(self, p.symbol, Function._factory(self, node[p.name], p))
            else:
                # Any property not in the input file will be set to None.
                setattr(self, p.symbol, None)

    def loadFile(self, filePath: str):
        """
        Loads yaml file and parses information to fill in Material data members including all relevant Function objects.

        Parameters
        ----------
        filePath: str
            Path containing name of YAML file to parse.
        """
        # load the file path
        y = YAML(pure=True)
        node = y.load(Path(filePath))

        # grab the material name from the file name
        n = Path(filePath).name
        if n.endswith(".yaml"):
            n = n[:-5]
        elif n.endswith(".yml"):
            n = n[:-4]
        self.name = n

        # Generate SHA1 value and set data member
        sha1 = hashlib.sha1()
        with open(filePath, "rb") as materialFile:
            sha1.update(materialFile.read())
        self._sha1 = sha1.hexdigest()

        self.dataCheckMaterialFile(filePath, node)
        self.loadNode(node)
