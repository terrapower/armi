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
"""Complete the migration from AM242 to AM242M."""

import io
import re

from armi.migration.base import BlueprintsMigration


class UpdateAmericium242(BlueprintsMigration):
    """The current ARMI nuclide modeling uses AM242M as the default metastable isomer of AM242.

    The reason for this little oddity is that AM242M is by a wide margin the most stable isomer, with a half-life in the
    neighborhood of 141 years. Many of the other meta-stable states have half lives in the range of hours or even
    milliseconds.
    """

    swap = ("AM242", "AM242M")

    @property
    def fromVersion(self):
        return "0.6.4"

    @property
    def toVersion(self):
        return "0.7.0"

    def _applyToStream(self):
        """Change both nuclide flags as well as custom isotopics.

        Custom isotopics: `        AM242: 0.0015135`
        Nuclide flags: `    AM242M: {burn: false, xs: true}`
        """
        print("xxxxxxxxxxx")
        migrated = []
        swapFrom, swapTo = self.swap
        for line in self.stream.read().split("\n"):
            line = re.sub(r"^(\s+)({0})(:.+)".format(swapFrom), r"\1{0}\3".format(swapTo), line)
            migrated.append(line)

        result = "\n".join(migrated)
        return io.StringIO(result)
