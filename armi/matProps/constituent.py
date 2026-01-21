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

"""Basic material composition."""


class Constituent:
    """Makeup of the Material.composition."""

    def __init__(self, name: str, min_value: float, max_value: float, is_balance: bool):
        """
        Constructor for Constituent object.

        Parameters
        ----------
        name: str
            Name of constituent element
        min_value: float
            Minimum value of constituent
        max_value: float
            Maximum value of constituent
        is_balance: bool
            Boolean used to denote if constituent is balance element (True) or not (False).
        """
        self.name = name
        """Name of the constituent"""
        self.min_value = min_value
        """Min value of the constituent"""
        self.max_value = max_value
        """Max value of the constituent"""
        self.is_balance = is_balance
        """Flag for indicating if the consitituent is intended to the balance of the composition"""

        if self.min_value < 0.0:
            msg = f"Constituent {self.name} has a negative minimum composition value."
            raise ValueError(msg)
        elif self.max_value < self.min_value:
            msg = f"Constituent {self.name} has an invalid maximum composition value. (max < min)"
            raise ValueError(msg)
        elif self.max_value > 100.0:
            msg = f"Constituent {self.name} has an invalid maximum composition value. (max > 100.0)"
            raise ValueError(msg)

    def __repr__(self):
        """Provides string representation of Constituent object."""
        msg = f"<Constituent {self.name} min: {self.min_value} max: {self.max_value}"
        if self.is_balance:
            msg += " computed based on balance"
        msg += ">"
        return msg

    @staticmethod
    def _parse_composition(node):
        """
        Method which parses "composition" node from yaml file and returns container of Contituent objects.

        Returns list of Constituent objects. Each element is constructed from a map element in the "composition node".

        Parameters
        ----------
        node: dict
            YAML object representing composition node.

        Returns
        -------
        list : Constituent
            List of Constituent objects representing elements of Material.
        """
        composition = []
        elementSet = set()
        balance_name = ""
        balance_min = 100.0
        balance_max = 100.0
        sum_min = 0.0
        sum_max = 0.0
        numBalance = 0
        for nodeName, nodeContent in node.items():
            element = nodeName
            if element == "references":
                continue

            if element in elementSet:
                msg = f"Composition has a duplicate element {element} present."
                raise KeyError(msg)
            else:
                elementSet.add(element)

            if type(nodeContent) is str and nodeContent == "balance":
                balance_name = element
                numBalance += 1
            elif type(nodeContent) is str or len(nodeContent) != 2:
                msg = (
                    f"Composition values must be either a tuple of min/max values, or `balance`, but got: {nodeContent}"
                )
                raise TypeError(msg)
            else:
                constituent_min = nodeContent[0]
                constituent_max = nodeContent[1]
                sum_min += constituent_min
                sum_max += constituent_max
                part = Constituent(element, constituent_min, constituent_max, False)
                composition.append(part)

        if numBalance != 1:
            msg = (
                f"Composition node must have exactly one balance element. Composition node has {numBalance} balance "
                "elements instead."
            )
            raise ValueError(msg)

        if balance_name:
            if sum_min > 100.0:
                raise ValueError("Composition has a minimum composition summation greater than 100.0")

            if sum_max >= 100.0:
                balance_min = 0.0
            else:
                balance_min -= sum_max

            balance_max -= sum_min
            balance = Constituent(balance_name, balance_min, balance_max, True)
            composition.append(balance)

        return composition
