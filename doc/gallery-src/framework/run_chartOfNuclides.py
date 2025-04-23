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
"""
Plot a chart of the nuclides.
=============================

Use the nuclide directory of ARMI to plot a chart of the nuclides
coloring the squares with the natural abundance.

.. admonition:: More details

    Our :ref:`extended tutorial for nuclides </tutorials/nuclide_demo.ipynb>` and
    detailed :py:mod:`nucDirectory docs <armi.nucDirectory>` may also be of interest.

"""

import matplotlib.pyplot as plt

from armi import configure
from armi.nucDirectory import nuclideBases

configure(permissive=True)

xyc = []
for name, base in nuclideBases.byName.items():
    if not base.a:
        continue
    xyc.append((base.a - base.z, base.z, base.abundance or 0.5))
x, y, c = zip(*xyc)
plt.figure(figsize=(12, 8))
plt.scatter(x, y, c=c, marker="s", s=6)
plt.title("Chart of the nuclides")
plt.xlabel("Number of neutrons (N)")
plt.ylabel("Number of protons (Z)")
plt.show()
