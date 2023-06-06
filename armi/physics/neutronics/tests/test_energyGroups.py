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

"""Energy group tests."""
import unittest

from armi.physics.neutronics import energyGroups


class TestEnergyGroups(unittest.TestCase):
    def test_invalidGroupStructureType(self):
        """Test that the reverse lookup fails on non-existent energy group bounds."""
        modifier = 1e-5
        for groupStructureType in energyGroups.GROUP_STRUCTURE:
            energyBounds = energyGroups.getGroupStructure(groupStructureType)
            energyBounds[0] = energyBounds[0] * modifier
            with self.assertRaises(ValueError):
                energyGroups.getGroupStructureType(energyBounds)

    def test_consistenciesBetweenGroupStructureAndGroupStructureType(self):
        """
        Test that the reverse lookup of the energy group structures work.

        Notes
        -----
        Several group structures point to the same energy group structure so the reverse lookup will fail to
        get the correct group structure type.
        """
        for groupStructureType in energyGroups.GROUP_STRUCTURE:
            self.assertEqual(
                groupStructureType,
                energyGroups.getGroupStructureType(
                    energyGroups.getGroupStructure(groupStructureType)
                ),
            )


if __name__ == "__main__":
    unittest.main()
