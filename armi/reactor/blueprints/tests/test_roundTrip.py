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

"""Characterization tests for blueprint round tripping.

These exercise a load/dump cycle over every blueprint the repository ships. They were written to
hold the replacement of the unmaintained ``yamlize`` package to the behavior it replaced, and they
go on guarding the invariants afterwards.

There are three invariants worth keeping honest here:

``reloadable``
    Whatever ``Blueprints.dump`` writes, ``Blueprints.load`` has to be able to read. Writing a file
    we cannot read back is the worst failure mode there is, because it is silent at write time.

``idempotent``
    A second dump of a reloaded blueprint must equal the first. Without this, every round trip
    through the case system slowly rewrites the user's input.

``semantically stable``
    The resolved content -- what the YAML *means* after anchors, aliases and merge keys are
    expanded -- must survive the cycle.

Layout -- indentation width, comment columns, where a line wraps -- is deliberately not asserted
here; none of it changes what the file means, and it is normalized to one house style on the way
out. :py:mod:`armi.utils.tests.test_yamlSchema` covers the formatting rules themselves.
"""

import io
import os
import unittest

from ruamel.yaml import YAML

from armi.reactor import blueprints
from armi.testing import TESTING_ROOT
from armi.utils import textProcessors

#: Every blueprint shipped in the package, relative to ``armi/testing/reactors``.
BLUEPRINTS = [
    "anl-afci-177/anl-afci-177-blueprints.yaml",
    "c5g7/c5g7-blueprints.yaml",
    "detailedAxialExpansion/refSmallReactorBase.yaml",
    "godiva/godiva-blueprints.yaml",
    "smallCartesian/refSmallCartesian.yaml",
    "smallestTestReactor/refOneBlockReactor.yaml",
    "smallHexReactor/smallHexReactor-bp.yaml",
    "sodiumHexReactor/refSmallReactorBase.yaml",
    "thirdSmallHexReactor/thirdSmallHexReactor-bp.yaml",
    "zppr/1DslabXSByCompTest.yaml",
]


def _readResolved(relPath):
    r"""Read a blueprint and paste in its ``!include``\ s, the way ``loadFromCs`` does."""
    path = os.path.join(TESTING_ROOT, "reactors", relPath)
    with open(path, "r") as f:
        return textProcessors.resolveMarkupInclusions(f, os.path.dirname(path)).getvalue()


def _semanticContent(text):
    """Reduce YAML text to the plain data it denotes, with anchors and merge keys expanded.

    A safe load resolves ``*alias`` and ``<<:`` for us, so two documents that differ only in how
    they factor shared content through anchors compare equal here.
    """
    content = YAML(typ="safe").load(io.StringIO(text))
    return _normalize(content)


def _normalize(node, parentKey=None, inBlockList=False):
    """Drop the redundant ``name:`` keys that a dump adds to keyed-list entries.

    A ``BlockBlueprint`` carries its name as the key of the mapping it sits in, so the source never
    spells it out. A dump sometimes has to relocate a block into an assembly's ``blocks`` *list*,
    where there is no key to carry the name, and writes it out explicitly instead. That is
    additive rather than a change in meaning, so it is normalized away here.
    """
    if isinstance(node, dict):
        return {
            k: _normalize(v, parentKey=k, inBlockList=(k == "blocks" and isinstance(v, list)))
            for k, v in node.items()
            if not (k == "name" and (v == parentKey or inBlockList))
        }
    elif isinstance(node, list):
        return [_normalize(v, inBlockList=inBlockList) for v in node]

    return node


class TestBlueprintRoundTrip(unittest.TestCase):
    """Load/dump behavior across every blueprint in the package."""

    def test_dumpIsReloadable(self):
        """Anything ``dump`` writes, ``load`` must be able to read."""
        for relPath in BLUEPRINTS:
            with self.subTest(blueprint=relPath):
                dumped = blueprints.Blueprints.dump(blueprints.Blueprints.load(io.StringIO(_readResolved(relPath))))
                blueprints.Blueprints.load(io.StringIO(dumped))

    def test_dumpIsIdempotent(self):
        """A second dump must equal the first, so repeated round trips do not drift."""
        for relPath in BLUEPRINTS:
            with self.subTest(blueprint=relPath):
                first = blueprints.Blueprints.dump(blueprints.Blueprints.load(io.StringIO(_readResolved(relPath))))
                second = blueprints.Blueprints.dump(blueprints.Blueprints.load(io.StringIO(first)))
                self.assertEqual(first, second)

    def test_semanticContentPreserved(self):
        """The meaning of the document must survive a dump."""
        for relPath in BLUEPRINTS:
            with self.subTest(blueprint=relPath):
                source = _readResolved(relPath)
                dumped = blueprints.Blueprints.dump(blueprints.Blueprints.load(io.StringIO(source)))
                self.assertEqual(_semanticContent(source), _semanticContent(dumped))


class TestFormerRoundTripDefects(unittest.TestCase):
    """Two round-trip defects that blueprints carried until they moved off yamlize.

    Both came from the same design: yamlize discarded the parsed document and reattached YAML
    metadata at dump time from a cache keyed on the values, so equal values shared an entry. The
    document is now kept and nothing is keyed by value, so neither can recur.
    """

    def test_blankLineInSystemsEntry(self):
        """A blank line in a ``systems:`` entry used to produce YAML that ARMI could not read.

        A system conventionally has the same name as its grid, so ``"core"`` appeared twice in one
        metadata cache. The blank line -- which ruamel.yaml carries as a comment on the ``grid
        name`` value -- was reapplied to the system's *key* node, and the emitter split the key from
        its colon::

            systems:
              core

            :
                grid name: core

        which is still valid YAML but no longer the mapping ``Blueprints`` expects. It is why
        ``c5g7-blueprints.yaml`` could not be round tripped at all.
        """
        source = "systems:\n  core:\n    grid name: core\n\n    origin:\n      x: 0.0\n"
        dumped = blueprints.Blueprints.dump(blueprints.Blueprints.load(io.StringIO(source)))

        self.assertEqual(dumped, source)
        self.assertEqual(blueprints.Blueprints.load(io.StringIO(dumped)).systemDesigns["core"].gridName, "core")

    def test_commentFollowingAListValuedKey(self):
        """A comment between a sequence value and the next key used to be dropped.

        yamlize rebuilt sequence nodes from scratch, and the parent mapping's comment record for
        that slot did not come along.
        """
        source = """\
blocks:
  fuel: &block_fuel
    fuel:
      shape: Hexagon
      material: UZr
      Tinput: 25.0
      Thot: 600.0
      op: 1.0
assemblies:
  ig:
    specifier: IC
    blocks: [*block_fuel]
    height: [1.0]
    # how tall each block is
    axial mesh points: [1]
    xs types: [A]
"""
        dumped = blueprints.Blueprints.dump(blueprints.Blueprints.load(io.StringIO(source)))
        self.assertIn("how tall each block is", dumped)


if __name__ == "__main__":
    unittest.main()
