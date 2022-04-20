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

"""Tests for operators"""

# pylint: disable=abstract-method,no-self-use,unused-argument
import unittest

from armi import settings
from armi.interfaces import Interface
from armi.reactor.tests import test_reactors


class InterfaceA(Interface):
    function = "A"
    name = "First"


class InterfaceB(InterfaceA):
    """Dummy Interface that extends A"""

    function = "A"
    name = "Second"


class InterfaceC(Interface):
    function = "A"
    name = "Third"


# TODO: Add a test that shows time evolution of Reactor (REQ_EVOLVING_STATE)
class OperatorTests(unittest.TestCase):
    def test_addInterfaceSubclassCollision(self):
        self.cs = settings.Settings()
        o, r = test_reactors.loadTestReactor()

        interfaceA = InterfaceA(r, self.cs)

        interfaceB = InterfaceB(r, self.cs)
        o.addInterface(interfaceA)

        # 1) Adds B and gets rid of A
        o.addInterface(interfaceB)
        self.assertEqual(o.getInterface("Second"), interfaceB)
        self.assertEqual(o.getInterface("First"), None)

        # 2) Now we have B which is a subclass of A,
        #    we want to not add A (but also not have an error)
        o.addInterface(interfaceA)
        self.assertEqual(o.getInterface("Second"), interfaceB)
        self.assertEqual(o.getInterface("First"), None)

        # 3) Also if another class not a subclass has the same function,
        #    raise an error
        interfaceC = InterfaceC(r, self.cs)

        self.assertRaises(RuntimeError, o.addInterface, interfaceC)

        # 4) Check adding a different function Interface

        interfaceC.function = "C"

        o.addInterface(interfaceC)
        self.assertEqual(o.getInterface("Second"), interfaceB)
        self.assertEqual(o.getInterface("Third"), interfaceC)


if __name__ == "__main__":
    unittest.main()
