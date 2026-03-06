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

"""Some definition of material types: fluid, fuel, metal, etc."""


class MaterialType:
    """
    A container for the methods used to differentiate between the types of materials.

    The MaterialType class is used to determine whether the material contain ASME, fluid, fuel, or metal properties. It
    may also be used for the phase of the material.
    """

    """Dictionary mapping material type strings to enum values."""
    types = {
        "Fuel": 1,
        "Metal": 2,
        "Fluid": 4,
        "Ceramic": 8,
        "ASME2015": 16,
        "ASME2017": 32,
        "ASME2019": 64,
    }

    def __init__(self, value: int = 0):
        """
        Constructor for MaterialType class.

        Parameters
        ----------
        value: int
            Integer enum value denoting material type.
        """
        self._value: int = value
        """Enum value representing type of material."""

    @staticmethod
    def fromString(name: str) -> "MaterialType":
        """
        Provides MaterialType object from a user provided string.

        Parameters
        ----------
        name: str
            String from which a MaterialType object will be derived.

        Returns
        -------
        MaterialType
        """
        value: int = MaterialType.types.get(name, 0)

        if value == 0:
            msg = f"Invalid material type `{name}`, valid names are: {list(MaterialType.types.keys())}"
            raise KeyError(msg)

        return MaterialType(value)

    def __repr__(self):
        """Provides string representation of MaterialType instance."""
        name = "None"
        for typ, val in self.types.items():
            if val == self._value:
                name = typ
                break

        return f"<MaterialType {name}>"

    def __eq__(self, other) -> bool:
        """
        Support for "==" comparison operator.

        Parameters
        ----------
        other: MaterialType or int
            RHS object that is compared to MaterialType instance.

        Returns
        -------
        bool
            True if objects ._value data members are equivalent, False otherwise.
        """
        if type(other) is int:
            return self._value == other
        elif type(other) is MaterialType:
            return self._value == other._value
        else:
            raise TypeError(f"Cannot compare MaterialType to type {type(other)}")
