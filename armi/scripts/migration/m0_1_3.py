"""
Cleans up blueprints.
"""
import re
import io

from armi.scripts.migration.base import BlueprintsMigration
from armi import runLog


class RemoveCentersFromBlueprints(BlueprintsMigration):
    """Removes now-invalid `centers:` lines from auto-generated component inputs"""

    fromVersion = "0.1.2"
    toVersion = "0.1.3"

    def _applyToStream(self):
        runLog.info("Removing `centers:` sections.")
        migrated = []
        for line in self.stream.read().split("\n"):
            if re.search(r"^\s*centers:\s*$", line):
                continue
            migrated.append(line)
        result = "\n".join(migrated)
        return io.StringIO(result)


class UpdateElementalNuclides(BlueprintsMigration):
    """Update elemental nuclide flags."""

    fromVersion = "0.1.2"
    toVersion = "0.1.3"

    swaps = (
        ("NA23", "NA"),
        ("MN55", "MN"),
        ("HE4", "HE"),
        ("W182", "W"),
        ("O16", "O"),
        ("AL27", "AL"),
        ("N14", "N"),
    )
    # these get absorbed into W
    deletions = ("W183", "W184", "W186")

    def _applyToStream(self):
        # Change both nuclide flags as well as custom isotopics
        # Custom isotopics: `        MN: 0.0015135`
        # Nuclide flags: `    MN55: {burn: false, xs: true}`
        migrated = []
        for line in self.stream.read().split("\n"):
            for deletion in self.deletions:
                if re.search(r"^\s*{0}: ".format(deletion), line):
                    continue
            for swapFrom, swapTo in self.swaps:
                line = re.sub(
                    r"^(\s+)({0})(:.+)".format(swapFrom),
                    r"\1{0}\3".format(swapTo),
                    line,
                )
            migrated.append(line)
        result = "\n".join(migrated)
        return io.StringIO(result)
