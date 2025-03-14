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
        """Test that the reverse lookup fails on non-existent energy group bounds.

        .. test:: Check the neutron energy group bounds logic fails correctly for the wrong structure.
            :id: T_ARMI_EG_NE0
            :tests: R_ARMI_EG_NE
        """
        modifier = 1e-5
        for groupStructureType in energyGroups.GROUP_STRUCTURE:
            energyBounds = energyGroups.getGroupStructure(groupStructureType)
            energyBounds[0] = energyBounds[0] * modifier
            with self.assertRaises(ValueError):
                energyGroups.getGroupStructureType(energyBounds)

    def test_consistenciesBetweenGSAndGSType(self):
        """Test that the reverse lookup of the energy group structures work.

        .. test:: Check the neutron energy group bounds for a given group structure.
            :id: T_ARMI_EG_NE1
            :tests: R_ARMI_EG_NE
        """
        for groupStructureType in energyGroups.GROUP_STRUCTURE:
            self.assertEqual(
                groupStructureType,
                energyGroups.getGroupStructureType(energyGroups.getGroupStructure(groupStructureType)),
            )

    def test_getFastFluxGroupCutoff(self):
        """Test ability to get the ARMI energy group index contained in energy threshold.

        .. test:: Return the energy group index which contains a given energy threshold.
            :id: T_ARMI_EG_FE
            :tests: R_ARMI_EG_FE
        """
        group, frac = energyGroups.getFastFluxGroupCutoff([100002, 100001, 100000, 99999, 0])

        self.assertListEqual([group, frac], [2, 0])
