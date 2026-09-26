# Copyright 2026 TerraPower, LLC
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

"""Tests for the YAML-to-object mapping that replaces yamlize."""

import io
import unittest

from armi.utils.yamlSchema import (
    WIDTH,
    Field,
    FloatList,
    IntList,
    KeyedList,
    Map,
    Sequence,
    StrList,
    YamlObject,
    YamlSchemaError,
)


class Pitch(YamlObject):
    x = Field(type=float, default=0.0)
    y = Field(type=float, default=0.0)


class Grid(YamlObject):
    name = Field(type=str)
    geom = Field(type=str, default="hex")
    latticeMap = Field(key="lattice map", type=str, default=None)
    pitch = Field(key="lattice pitch", type=Pitch, default=None)


class Grids(KeyedList):
    itemType = Grid
    keyField = Grid.name


class Component(YamlObject):
    name = Field(type=str)
    shape = Field(type=str)
    od = Field(type=float, default=None)


class Block(KeyedList):
    itemType = Component
    keyField = Component.name
    name = Field(type=str)
    gridName = Field(key="grid name", type=str, default=None)


class TestField(unittest.TestCase):
    def test_keyDefaultsToName(self):
        self.assertEqual(Grid.geom.key, "geom")

    def test_explicitKeyWins(self):
        self.assertEqual(Grid.latticeMap.key, "lattice map")

    def test_requiredWhenNoDefault(self):
        self.assertTrue(Grid.name.isRequired)
        self.assertFalse(Grid.geom.isRequired)

    def test_coercionThatPreservesValueIsAllowed(self):
        grid = Grid.load("name: core\n")
        grid.pitch = Pitch()
        grid.pitch.x = 3  # an int, but equal to 3.0
        self.assertIsInstance(grid.pitch.x, float)

    def test_coercionThatChangesValueIsRejected(self):
        with self.assertRaises(YamlSchemaError) as cm:
            Grid.load("name: core\nlattice pitch: {x: not-a-number}\n")

        self.assertIn("x", str(cm.exception))

    def test_defaultIsExemptFromCoercion(self):
        """``default=None`` on a typed field is how optional fields are spelled."""
        grid = Grid.load("name: core\n")
        self.assertIsNone(grid.latticeMap)

    def test_validatorRejectsBadValue(self):
        class Thing(YamlObject):
            size = Field(type=int, default=1)

            @size.validator
            def size(self, value):
                return value > 0

        thing = Thing.load("size: 5\n")
        self.assertEqual(thing.size, 5)
        with self.assertRaises(ValueError):
            thing.size = -1


class TestLoading(unittest.TestCase):
    def test_missingRequiredKeyIsReported(self):
        with self.assertRaises(YamlSchemaError) as cm:
            Grid.load("geom: cartesian\n")

        self.assertIn("name", str(cm.exception))

    def test_unknownKeyIsReported(self):
        with self.assertRaises(YamlSchemaError) as cm:
            Grid.load("name: core\nwidgets: 3\n")

        self.assertIn("widgets", str(cm.exception))

    def test_errorNamesTheLine(self):
        with self.assertRaises(YamlSchemaError) as cm:
            Grid.load("name: core\n\n\nwidgets: 3\n")

        self.assertIn("line 4", str(cm.exception))

    def test_nestedObject(self):
        grid = Grid.load("name: core\nlattice pitch: {x: 1.5, y: 2.5}\n")
        self.assertEqual(grid.pitch.x, 1.5)
        self.assertEqual(grid.pitch.y, 2.5)

    def test_keyedListKeySuppliesField(self):
        grids = Grids.load("core:\n    geom: cartesian\nsfp:\n    geom: hex\n")
        self.assertEqual(grids["core"].name, "core")
        self.assertEqual(grids["core"].geom, "cartesian")
        self.assertEqual(grids["sfp"].name, "sfp")

    def test_keyedListIteratesValues(self):
        grids = Grids.load("core:\n    geom: cartesian\nsfp:\n    geom: hex\n")
        self.assertEqual([g.name for g in grids], ["core", "sfp"])

    def test_keyedListMixesFieldsAndEntries(self):
        block = Block.load("name: fuel\ngrid name: twoPin\nclad:\n    shape: Circle\n    od: 1.0\n")
        self.assertEqual(block.name, "fuel")
        self.assertEqual(block.gridName, "twoPin")
        self.assertEqual([c.name for c in block], ["clad"])
        self.assertEqual(block["clad"].od, 1.0)

    def test_keyedListRejectsMismatchedKey(self):
        grids = Grids.load("core:\n    geom: hex\n")
        with self.assertRaises(KeyError):
            grids["sfp"] = grids["core"]


class TestMap(unittest.TestCase):
    def test_typedKeysAndValues(self):
        class Isotopics(Map):
            keyType = str
            valueType = float
            inputFormat = Field(key="input format", type=str, default="mass fractions")

        iso = Isotopics.load("input format: number densities\nU235: 0.1\nU238: 0.9\n")
        self.assertEqual(iso.inputFormat, "number densities")
        self.assertEqual(iso["U235"], 0.1)
        self.assertEqual(sorted(iso.keys()), ["U235", "U238"])

    def test_mapIteratesKeys(self):
        class Simple(Map):
            keyType = str

        simple = Simple.load("a: 1\nb: 2\n")
        self.assertEqual(sorted(simple), ["a", "b"])


class TestSequence(unittest.TestCase):
    def test_typedLists(self):
        self.assertEqual(list(FloatList.load("[1, 2.5]")), [1.0, 2.5])
        self.assertEqual(list(IntList.load("[1, 2]")), [1, 2])
        self.assertEqual(list(StrList.load("[a, b]")), ["a", "b"])

    def test_coercionThatChangesValueIsRejected(self):
        with self.assertRaises(YamlSchemaError):
            IntList.load("[1.5]")

    def test_untypedSequencePassesValuesThrough(self):
        self.assertEqual(list(Sequence.load('["", 0.0, true]')), ["", 0.0, True])


class TestRoundTrip(unittest.TestCase):
    """The reason this module exists: dumping must give the document back."""

    SOURCE = """\
# how the core is laid out
core:
  geom: cartesian          # square lattice
  lattice pitch:
    x: 1.26
    y: 1.26
  lattice map: |
    1 1 1
    1 2 1
    1 1 1
sfp:
  geom: hex
"""

    def test_untouchedDocumentComesBackVerbatim(self):
        self.assertEqual(Grids.dump(Grids.load(self.SOURCE)), self.SOURCE)

    def test_commentsSurvive(self):
        dumped = Grids.dump(Grids.load(self.SOURCE))
        self.assertIn("# how the core is laid out", dumped)
        self.assertIn("# square lattice", dumped)

    def test_literalBlockScalarSurvives(self):
        self.assertIn("lattice map: |", Grids.dump(Grids.load(self.SOURCE)))

    def test_editedFieldIsWrittenAndTheRestIsUntouched(self):
        grids = Grids.load(self.SOURCE)
        grids["sfp"].geom = "cartesian"
        dumped = Grids.dump(grids)

        self.assertIn("# how the core is laid out", dumped)
        self.assertIn("# square lattice", dumped)
        self.assertIn("lattice map: |", dumped)
        self.assertEqual(dumped, self.SOURCE.replace("sfp:\n  geom: hex", "sfp:\n  geom: cartesian"))

    def test_dumpIsIdempotent(self):
        first = Grids.dump(Grids.load(self.SOURCE))
        self.assertEqual(first, Grids.dump(Grids.load(first)))

    def test_anchorsAndAliasesSurvive(self):
        source = "core: &shared\n    geom: cartesian\nsfp: *shared\n"
        dumped = Grids.dump(Grids.load(source))
        self.assertIn("&shared", dumped)
        self.assertIn("*shared", dumped)

    def test_mergeKeysSurvive(self):
        source = "core: &shared\n    geom: cartesian\nsfp:\n    <<: *shared\n    lattice map: x\n"
        grids = Grids.load(source)
        self.assertEqual(grids["sfp"].geom, "cartesian")
        self.assertIn("<<: *shared", Grids.dump(grids))

    def test_loadDoesNotMutateOnDump(self):
        """Dumping twice must give the same answer, i.e. dump must not consume the document."""
        grids = Grids.load(self.SOURCE)
        self.assertEqual(Grids.dump(grids), Grids.dump(grids))


class TestFormattingIsNormalized(unittest.TestCase):
    """Layout is written in one house style rather than copied from each source file.

    ruamel.yaml applies indentation globally at dump time, so matching a source exactly would mean
    guessing its conventions -- and real blueprints mix two- and four-space mappings within a single
    file, so no guess can be right. Normalizing keeps ARMI's output uniform. It changes whitespace
    only; content, comments, anchors and styles are untouched.
    """

    def test_indentIsNormalized(self):
        for source in (
            "core:\n  geom: cartesian\n",
            "core:\n    geom: cartesian\n",
            "core:\n        geom: cartesian\n",
        ):
            with self.subTest(source=source):
                self.assertEqual(Grids.dump(Grids.load(source)), "core:\n  geom: cartesian\n")

    def test_normalizedOutputIsStable(self):
        """Normalizing once must be enough: a second pass changes nothing."""
        once = Grids.dump(Grids.load("core:\n        geom: cartesian\n"))
        self.assertEqual(Grids.dump(Grids.load(once)), once)

    def test_normalizingDoesNotDisturbContent(self):
        source = "# leading\ncore:\n        geom: cartesian    # trailing\n        lattice map: |\n            1 1\n"
        dumped = Grids.dump(Grids.load(source))

        self.assertIn("# leading", dumped)
        self.assertIn("# trailing", dumped)
        self.assertIn("lattice map: |", dumped)
        self.assertEqual(Grids.load(dumped)["core"].geom, "cartesian")

    def test_sequenceIndentIsNormalized(self):
        class Holder(YamlObject):
            name = Field(type=str)
            values = Field(type=FloatList, default=None)

        expected = "name: a\nvalues:\n  - 1.0\n  - 2.0\n"
        for source in (
            "name: a\nvalues:\n- 1.0\n- 2.0\n",
            "name: a\nvalues:\n    - 1.0\n    - 2.0\n",
        ):
            with self.subTest(source=source):
                self.assertEqual(Holder.dump(Holder.load(source)), expected)

    def test_longFlowSequenceIsWrappedAtTheHouseWidth(self):
        """A flow sequence too long for one line is broken up; its contents are unchanged.

        Only sequences can be wrapped. A single long scalar -- a lattice map row, say -- has no
        break point, so real files can still carry lines past :py:data:`WIDTH`.
        """

        class Holder(YamlObject):
            name = Field(type=str)
            values = Field(type=StrList, default=None)

        source = "name: a\nvalues: [{}]\n".format(", ".join("block_{}".format(i) for i in range(40)))
        dumped = Holder.dump(Holder.load(source))

        self.assertTrue(all(len(line) <= WIDTH for line in dumped.splitlines()))
        self.assertEqual(list(Holder.load(dumped).values), list(Holder.load(source).values))

    def test_wrappingIsStable(self):
        """Re-wrapping must converge, or every round trip would reflow the file again."""

        class Holder(YamlObject):
            name = Field(type=str)
            values = Field(type=StrList, default=None)

        source = "name: a\nvalues: [{}]\n".format(", ".join("block_{}".format(i) for i in range(40)))
        once = Holder.dump(Holder.load(source))
        self.assertEqual(Holder.dump(Holder.load(once)), once)

    def test_shortLinesAreLeftOnOneLine(self):
        class Holder(YamlObject):
            name = Field(type=str)
            values = Field(type=StrList, default=None)

        source = "name: a\nvalues: [b, c, d]\n"
        self.assertEqual(Holder.dump(Holder.load(source)), source)

    def test_unreferencedAnchorIsKept(self):
        """An anchor nothing aliases yet is still part of the user's input."""
        source = "core: &unused\n  geom: cartesian\n"
        self.assertIn("&unused", Grids.dump(Grids.load(source)))


class TestLatticeMapsKeepTheirLayout(unittest.TestCase):
    """A multi-line string in a blueprint is a picture, and must survive as one.

    Lattice maps, pin maps and core maps are read and edited in a text editor. Their line breaks
    and column alignment are the data. They must come back as literal block scalars (``|``), never
    quoted-and-folded, no matter how wide the rows are or how the value got there.
    """

    #: 70 pins across -- rows well past :py:data:`WIDTH`
    WIDE_PIN_MAP = "\n".join("  ".join("A{:03d}".format(c) for c in range(70)) for _ in range(4)) + "\n"

    HEX_MAP = "-   -   SH\n  -   SH  SH\n-   SH  OC  SH\n  SH  OC  OC  SH\n"

    @staticmethod
    def _grids(latticeMap):
        grids = Grids()
        grid = Grid()
        grid.name = "core"
        grid.latticeMap = latticeMap
        grids.add(grid)

        return grids

    def test_wideMapIsNotWrapped(self):
        dumped = Grids.dump(self._grids(self.WIDE_PIN_MAP))

        self.assertIn("lattice map: |", dumped)
        self.assertEqual(Grids.load(dumped)["core"].latticeMap, self.WIDE_PIN_MAP)

    def test_everyRowStaysOnItsOwnLine(self):
        """The row count and each row's exact text must be untouched."""
        dumped = Grids.dump(self._grids(self.WIDE_PIN_MAP))
        rows = [line.strip() for line in dumped.splitlines() if line.strip().startswith("A")]

        self.assertEqual(rows, self.WIDE_PIN_MAP.strip().splitlines())
        self.assertGreater(max(len(row) for row in rows), WIDTH)

    def test_mapAssignedFromCodeIsStillABlockScalar(self):
        """Callers must not have to remember ``LiteralScalarString`` to get a readable file."""
        loaded = Grids.load("core:\n  lattice map: |\n    IC  IC\n")
        loaded["core"].latticeMap = self.WIDE_PIN_MAP
        dumped = Grids.dump(loaded)

        self.assertIn("lattice map: |", dumped)
        self.assertNotIn("\\n", dumped)
        self.assertEqual(Grids.load(dumped)["core"].latticeMap, self.WIDE_PIN_MAP)

    def test_awkwardMapsStayLiteral(self):
        """Shapes that can push ruamel.yaml off block style."""
        maps = {
            "leading dashes": self.HEX_MAP,
            "first row indented deepest": "    IC  IC\n  IC  IC  IC\nIC  IC\n",
            "trailing spaces": "IC  IC   \nIC  IC\n",
            "tabs": "IC\tIC\nIC\tIC\n",
        }
        for label, latticeMap in maps.items():
            with self.subTest(shape=label):
                dumped = Grids.dump(self._grids(latticeMap))
                self.assertIn("lattice map: |", dumped)
                self.assertEqual(Grids.load(dumped)["core"].latticeMap, latticeMap)

    def test_loadedMapIsByteIdentical(self):
        source = "core:\n  lattice map: |\n" + "".join(
            "    " + row + "\n" for row in self.WIDE_PIN_MAP.strip().splitlines()
        )
        self.assertEqual(Grids.dump(Grids.load(source)), source)

    def test_singleLineStringIsNotTurnedIntoABlock(self):
        """Only multi-line strings become blocks; ordinary values are left alone."""
        self.assertEqual(Grids.dump(self._grids("IC IC IC")), "core:\n  lattice map: IC IC IC\n")


class TestValuesThatHashAlike(unittest.TestCase):
    """The yamlize defect this module is designed to make structurally impossible.

    ``hash("") == hash(0.0) == hash(0) == hash(False)`` and ``hash(1) == hash(1.0) == hash(True)``.
    yamlize keyed its round-trip metadata on those hashes, so colliding values swapped YAML tags
    and quote styles. Here nothing is keyed by value, because the document is never taken apart.
    """

    def test_collidingValuesInASequence(self):
        for source in ('["", 0.0, 0.0, ""]', "[0, 0.0]", '["a", 1.0, true]', '[false, 0, "", 0.0]'):
            with self.subTest(source=source):
                self.assertEqual(Sequence.dump(Sequence.load(source)).strip(), source)

    def test_collidingValuesAsSiblingKeys(self):
        source = "core:\n  geom: core\n\n  lattice map: x\n"
        grids = Grids.load(source)
        self.assertEqual(Grids.dump(grids), source)
        self.assertEqual(grids["core"].geom, "core")


class TestFieldsAddedAfterClassCreation(unittest.TestCase):
    """ARMI attaches component dimensions and plugin parameters to blueprint classes at import."""

    def test_setattrRegistersTheField(self):
        class Late(YamlObject):
            name = Field(type=str)

        Late.extra = Field(key="extra", type=int, default=None)

        self.assertIn("extra", Late._fields.byKey)
        late = Late.load("name: a\nextra: 3\n")
        self.assertEqual(late.extra, 3)

    def test_subclassInheritsFields(self):
        class Child(Grid):
            depth = Field(type=float, default=1.0)

        child = Child.load("name: core\ndepth: 2.0\n")
        self.assertEqual(child.name, "core")
        self.assertEqual(child.depth, 2.0)
        self.assertIn("geom", Child._fields.byKey)


class TestBuildingInCode(unittest.TestCase):
    """Objects made programmatically, with no source document, still dump."""

    def test_dumpObjectBuiltInCode(self):
        grids = Grids()
        grid = Grid()
        grid.name = "core"
        grid.geom = "cartesian"
        grids.add(grid)

        dumped = Grids.dump(grids)
        self.assertIn("core:", dumped)
        self.assertIn("geom: cartesian", dumped)
        self.assertEqual(Grids.load(dumped)["core"].geom, "cartesian")

    def test_dumpToStream(self):
        stream = io.StringIO()
        self.assertIsNone(Grids.dump(Grids.load("core:\n    geom: hex\n"), stream))
        self.assertIn("core:", stream.getvalue())


if __name__ == "__main__":
    unittest.main()
