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

    def __init__(self, name: str, minValue: float, maxValue: float, isBalance: bool):
        """
        Constructor for Constituent object.

        Parameters
        ----------
        name: str
            Name of constituent element
        minValue: float
            Minimum value of constituent
        maxValue: float
            Maximum value of constituent
        isBalance: bool
            Boolean used to denote if constituent is balance element (True) or not (False).
        """
        self.name = name
        """Name of the constituent"""
        self.minValue = minValue
        """Min value of the constituent"""
        self.maxValue = maxValue
        """Max value of the constituent"""
        self.isBalance = isBalance
        """Flag for indicating if the consitituent is intended to the balance of the composition"""

        if self.minValue < 0.0:
            msg = f"Constituent {self.name} has a negative minimum composition value."
            raise ValueError(msg)
        elif self.maxValue < self.minValue:
            msg = f"Constituent {self.name} has an invalid maximum composition value. (max < min)"
            raise ValueError(msg)
        elif self.maxValue > 100.0:
            msg = f"Constituent {self.name} has an invalid maximum composition value. (max > 100.0)"
            raise ValueError(msg)

    def __repr__(self):
        """Provides string representation of Constituent object."""
        msg = f"<Constituent {self.name} min: {self.minValue} max: {self.maxValue}"
        if self.isBalance:
            msg += " computed based on balance"
        msg += ">"
        return msg

    @staticmethod
    def parseComposition(node):
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
        balanceName = ""
        balanceMin = 100.0
        balanceMax = 100.0
        sumMin = 0.0
        sumMax = 0.0
        numBalance = 0
        for element, nodeContent in node.items():
            if element == "references":
                continue

            elementSet.add(element)

            if nodeContent == "balance":
                balanceName = element
                numBalance += 1
            elif type(nodeContent) is str or len(nodeContent) != 2:
                msg = (
                    f"Composition values must be either a tuple of min/max values, or `balance`, but got: {nodeContent}"
                )
                raise TypeError(msg)
            else:
                constituentMin = nodeContent[0]
                constituentMax = nodeContent[1]
                sumMin += constituentMin
                sumMax += constituentMax
                part = Constituent(element, constituentMin, constituentMax, False)
                composition.append(part)

        if numBalance != 1:
            msg = (
                f"Composition node must have exactly one balance element. Composition node has {numBalance} balance "
                "elements instead."
            )
            raise ValueError(msg)

        if balanceName:
            if sumMin > 100.0:
                raise ValueError("Composition has a minimum composition summation greater than 100.0")

            if sumMax >= 100.0:
                balanceMin = 0.0
            else:
                balanceMin -= sumMax

            balanceMax -= sumMin
            balance = Constituent(balanceName, balanceMin, balanceMax, True)
            composition.append(balance)

        return composition
