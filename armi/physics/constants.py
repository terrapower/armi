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

"""Some constants."""

DPA_CROSS_SECTIONS = {}
"""Multigroup dpa cross sections.

Displacements per atom are correlated to material damage.

Notes
-----
This data structure can be updated by plugins with design-specific dpa data.

:meta hide-value:
"""

# The following are multigroup DPA XS for EBR II. They were generated using an ultra hard MCC spectrum
# that calculated buckling and had an initial keff of 2. Even so, Inc600/625/X750 33 group dpa XS values are less than
# 5% for all but 5 energy groups. The maximum deviation is 18% in INC625 between .192 and .331 MeV.

DPA_CROSS_SECTIONS["dpa_EBRII_HT9"] = [
    2.34569e03,
    1.92004e03,
    1.58640e03,
    1.25670e03,
    8.24006e02,
    5.20750e02,
    3.96146e02,
    3.28749e02,
    2.06149e02,
    1.42452e02,
    1.15189e02,
    6.60183e01,
    8.23281e01,
    1.31771e01,
    1.94552e01,
    3.33861e01,
    1.27099e01,
    6.20510e00,
    3.58651e00,
    3.74080e00,
    4.52607e-01,
    1.62650e-01,
    1.24318e-01,
    1.56210e-01,
    1.89583e-01,
    2.36694e-01,
    2.97445e-01,
    3.92136e-01,
    5.07320e-01,
    6.81782e-01,
    1.07978e00,
    2.43258e00,
    4.35563e00,
]

DPA_CROSS_SECTIONS["dpa_EBRII_INC600"] = [
    2.57204e03,
    2.11682e03,
    1.64031e03,
    1.21591e03,
    8.69816e02,
    6.47128e02,
    4.25248e02,
    3.59778e02,
    2.89208e02,
    1.89443e02,
    1.55667e02,
    1.22460e02,
    8.25721e01,
    1.15026e02,
    9.90510e01,
    2.42252e01,
    1.73504e01,
    9.34915e00,
    5.67409e00,
    3.13557e00,
    5.95081e-01,
    1.95832e-01,
    1.93791e-01,
    2.52465e-01,
    3.11159e-01,
    3.71897e-01,
    4.95951e-01,
    6.50177e-01,
    8.39344e-01,
    1.12626e00,
    1.78500e00,
    4.02021e00,
    7.19616e00,
]

DPA_CROSS_SECTIONS["dpa_EBRII_INC625"] = [
    2.49791e03,
    2.05899e03,
    1.60441e03,
    1.20292e03,
    8.68237e02,
    6.39219e02,
    4.16975e02,
    3.50177e02,
    2.74491e02,
    1.89846e02,
    1.53178e02,
    1.16379e02,
    7.35708e01,
    1.05281e02,
    8.96142e01,
    2.58537e01,
    1.91218e01,
    8.44318e00,
    5.16493e00,
    2.67000e00,
    5.66731e-01,
    2.20242e-01,
    1.92435e-01,
    3.31226e-01,
    3.69475e-01,
    5.24326e-01,
    4.78120e-01,
    6.22211e-01,
    8.15999e-01,
    1.07725e00,
    1.70732e00,
    3.84540e00,
    6.88285e00,
]

DPA_CROSS_SECTIONS["dpa_EBRII_INCX750"] = [
    2.59270e03,
    2.13361e03,
    1.65837e03,
    1.23739e03,
    8.86458e02,
    6.51012e02,
    4.27294e02,
    3.58449e02,
    2.88178e02,
    1.88428e02,
    1.56886e02,
    1.27132e02,
    8.89576e01,
    1.31703e02,
    1.04350e02,
    2.55248e01,
    1.77532e01,
    9.43101e00,
    5.60558e00,
    3.06838e00,
    5.85632e-01,
    1.90347e-01,
    1.89737e-01,
    2.50070e-01,
    3.08765e-01,
    3.69079e-01,
    4.92257e-01,
    6.45369e-01,
    8.33181e-01,
    1.11802e00,
    1.77196e00,
    3.98945e00,
    7.13947e00,
]

DPA_CROSS_SECTIONS["dpa_EBRII_PE16"] = [
    2.47895e03,
    2.03583e03,
    1.61943e03,
    1.23864e03,
    8.58439e02,
    5.95879e02,
    4.10632e02,
    3.42948e02,
    2.49940e02,
    1.69919e02,
    1.39511e02,
    1.00171e02,
    8.21254e01,
    7.94117e01,
    6.73353e01,
    2.84413e01,
    1.61127e01,
    7.13145e00,
    4.59314e00,
    3.12973e00,
    5.17916e-01,
    1.51560e-01,
    1.56357e-01,
    2.37675e-01,
    2.81173e-01,
    3.65433e-01,
    4.12907e-01,
    5.40601e-01,
    7.03084e-01,
    9.37963e-01,
    1.48726e00,
    3.34954e00,
    5.99536e00,
]
