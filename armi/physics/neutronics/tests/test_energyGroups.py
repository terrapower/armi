"""Energy group tests."""
import unittest


from .. import energyGroups


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
