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

"""Unit tests for transmutations."""

import random
import string
import unittest

from armi import nuclideBases
from armi.nucDirectory import transmutations


def randomString(length):
    return "".join(random.choice(string.ascii_lowercase) for _ in range(length))


class TransmutationTests(unittest.TestCase):
    def test_Transmutation_validReactionTypes(self):
        data = {"products": [""]}
        for rxn in transmutations.TRANSMUTATION_TYPES:
            data["type"] = rxn
            temp = transmutations.Transmutation(nuclideBases.byName["AM242M"], data)
            self.assertEqual(temp.type, rxn)
            self.assertEqual(temp.productParticle, transmutations.PRODUCT_PARTICLES.get(temp.type))

    def test_Transmutation_productParticle(self):
        temp = transmutations.Transmutation(nuclideBases.byName["AM242M"], {"products": [""], "type": "nalph"})
        self.assertEqual(temp.productParticle, "HE4")

    def test_Transmutation_invalidReactionTypes(self):
        data = {"products": [""], "branch": 1.0}
        errorCount = 0
        for _ in range(0, 5):
            rxn = randomString(3)
            data["type"] = rxn
            if rxn in transmutations.TRANSMUTATION_TYPES:
                self.assertIsNotNone(transmutations.Transmutation(nuclideBases.byName["AM242M"], data))
            else:
                with self.assertRaises(KeyError):
                    errorCount += 1
                    transmutations.Transmutation(nuclideBases.byName["AM242M"], data)
        self.assertGreater(errorCount, 2)


class DecayModeTests(unittest.TestCase):
    def test_DecayMode_validReactionTypes(self):
        data = {"products": [""], "branch": 1.0, "halfLifeInSeconds": 1.0}
        for rxn in transmutations.DECAY_MODES:
            data["type"] = rxn
            decay = transmutations.DecayMode(nuclideBases.byName["AM242M"], data)
            self.assertEqual(decay.type, rxn)

    def test_DecayMode_invalidReactionTypes(self):
        data = {"products": [""], "branch": 1.0, "halfLifeInSeconds": 1.0}
        for _ in range(0, 25):
            rxn = randomString(3)
            data["type"] = rxn
            if rxn in transmutations.DECAY_MODES:
                self.assertIsNotNone(transmutations.DecayMode(nuclideBases.byName["AM242M"], data))
            else:
                with self.assertRaises(KeyError):
                    transmutations.DecayMode(nuclideBases.byName["AM242M"], data)
