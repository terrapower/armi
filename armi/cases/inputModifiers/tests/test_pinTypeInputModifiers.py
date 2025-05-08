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
"""Unit tests for input modifiers."""
import math
import unittest

from armi import settings
from armi.cases.inputModifiers import pinTypeInputModifiers
from armi.cases.inputModifiers.tests.test_inputModifiers import BLUEPRINT_INPUT
from armi.reactor import blueprints


class TestBlueprintModifiers(unittest.TestCase):
    def setUp(self):
        self.bp = blueprints.Blueprints.load(BLUEPRINT_INPUT)
        self.bp._prepConstruction(settings.Settings())

    def test_AdjustSmearDensity(self):
        r"""
        Compute the smear density where clad.id is 1.0.

        .. math::

            areaFuel = smearDensity * innerCladArea
            fuelOD^2 / 4 = 0.5 * cladID^2 / 4
            fuelOD = \sqrt{0.5}

        Notes
        -----
        The area of fuel is 0.5 * inner area of clad.
        """
        bp = self.bp
        self.assertEqual(1.0, bp.blockDesigns["fuel 1"]["clad"].id)
        self.assertEqual(0.5, bp.blockDesigns["fuel 1"]["fuel"].od)
        self.assertEqual(0.5, bp.blockDesigns["fuel 2"]["fuel"].od)
        self.assertEqual(0.5, bp.blockDesigns["block 3"]["fuel"].od)
        self.assertEqual(0.5, bp.blockDesigns["block 4"]["fuel"].od)
        self.assertEqual(0.5, bp.blockDesigns["block 5"]["fuel"].od)

        pinTypeInputModifiers.SmearDensityModifier(0.5)(settings.Settings(), bp)

        self.assertEqual(math.sqrt(0.5), bp.blockDesigns["fuel 1"]["fuel"].od)
        self.assertEqual(math.sqrt(0.5), bp.blockDesigns["fuel 2"]["fuel"].od)
        self.assertEqual(math.sqrt(0.5), bp.blockDesigns["block 3"]["fuel"].od)
        self.assertEqual(math.sqrt(0.5), bp.blockDesigns["block 4"]["fuel"].od)
        self.assertEqual(0.5, bp.blockDesigns["block 5"]["fuel"].od)  # unique instance

    def test_CladThickenessByODModifier(self):
        """
        Adjust the clad thickness by outer diameter.

        .. math::

            cladThickness = (clad.od - clad.id) / 2
            clad.od = 2 * cladThicness - clad.id

        when ``clad.id = 1.0`` and ``cladThickness = 0.12``,

        .. math::

            clad.od = 2 * 0.12 - 1.0
            clad.od = 1.24
        """
        bp = self.bp
        self.assertEqual(1.1, bp.blockDesigns["fuel 1"]["clad"].od)
        self.assertEqual(1.1, bp.blockDesigns["fuel 2"]["clad"].od)
        self.assertEqual(1.1, bp.blockDesigns["block 3"]["clad"].od)
        self.assertEqual(1.1, bp.blockDesigns["block 4"]["clad"].od)
        self.assertEqual(1.1, bp.blockDesigns["block 5"]["clad"].od)

        pinTypeInputModifiers.CladThicknessByODModifier(0.12)(settings.Settings(), bp)

        self.assertEqual(1.24, bp.blockDesigns["fuel 1"]["clad"].od)
        self.assertEqual(1.24, bp.blockDesigns["fuel 2"]["clad"].od)
        self.assertEqual(1.24, bp.blockDesigns["block 3"]["clad"].od)
        self.assertEqual(1.24, bp.blockDesigns["block 4"]["clad"].od)
        self.assertEqual(
            1.24, bp.blockDesigns["block 5"]["clad"].od
        )  # modifies all blocks

    def test_CladThickenessByIDModifier(self):
        """
        Adjust the clad thickness by inner diameter.

        .. math::

            cladThickness = (clad.od - clad.id) / 2
            clad.id = cladod - 2 * cladThicness

        when ``clad.id = 1.1`` and ``cladThickness = 0.025``,

        .. math::

            clad.od = 1.1 - 2 * 0.025
            clad.od = 1.05
        """
        bp = self.bp
        self.assertEqual(1.0, bp.blockDesigns["fuel 1"]["clad"].id)
        self.assertEqual(1.0, bp.blockDesigns["fuel 2"]["clad"].id)
        self.assertEqual(1.0, bp.blockDesigns["block 3"]["clad"].id)
        self.assertEqual(1.0, bp.blockDesigns["block 4"]["clad"].id)
        self.assertEqual(1.0, bp.blockDesigns["block 5"]["clad"].id)

        pinTypeInputModifiers.CladThicknessByIDModifier(0.025)(settings.Settings(), bp)

        self.assertEqual(1.05, bp.blockDesigns["fuel 1"]["clad"].id)
        self.assertEqual(1.05, bp.blockDesigns["fuel 2"]["clad"].id)
        self.assertEqual(1.05, bp.blockDesigns["block 3"]["clad"].id)
        self.assertEqual(1.05, bp.blockDesigns["block 4"]["clad"].id)
        self.assertEqual(
            1.05, bp.blockDesigns["block 5"]["clad"].id
        )  # modifies all blocks
