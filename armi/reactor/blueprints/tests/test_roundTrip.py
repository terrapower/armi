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

ARMI is in the middle of replacing the unmaintained ``yamlize`` package with an in-tree schema
layer over ``ruamel.yaml``. These tests pin down what a load/dump cycle does *today*, across every
blueprint the repository ships, so that the replacement can be held to the same behavior.

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

Layout -- indentation width, comment columns, where a line wraps -- is deliberately not asserted;
none of it changes what the file means. Comment preservation mostly works and is covered by the one
case that does not, in ``TestKnownRoundTripLimitations``.
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

#: Blueprints whose dump cannot currently be read back in. See
#: ``TestKnownRoundTripLimitations.test_systemNameMatchingGridNameWithBlankLine`` for the mechanism.
#: Remove entries here as the underlying defect is fixed; do not add to it.
NOT_RELOADABLE = {"c5g7/c5g7-blueprints.yaml"}


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
            if relPath in NOT_RELOADABLE:
                continue

            with self.subTest(blueprint=relPath):
                dumped = blueprints.Blueprints.dump(blueprints.Blueprints.load(io.StringIO(_readResolved(relPath))))
                blueprints.Blueprints.load(io.StringIO(dumped))

    def test_knownNotReloadableStillFails(self):
        """Guard the ``NOT_RELOADABLE`` list, so entries get removed once they start working."""
        for relPath in sorted(NOT_RELOADABLE):
            with self.subTest(blueprint=relPath):
                dumped = blueprints.Blueprints.dump(blueprints.Blueprints.load(io.StringIO(_readResolved(relPath))))
                with self.assertRaises(Exception, msg=f"{relPath} now reloads; drop it from NOT_RELOADABLE"):
                    blueprints.Blueprints.load(io.StringIO(dumped))

    def test_dumpIsIdempotent(self):
        """A second dump must equal the first, so repeated round trips do not drift."""
        for relPath in BLUEPRINTS:
            if relPath in NOT_RELOADABLE:
                continue

            with self.subTest(blueprint=relPath):
                first = blueprints.Blueprints.dump(blueprints.Blueprints.load(io.StringIO(_readResolved(relPath))))
                second = blueprints.Blueprints.dump(blueprints.Blueprints.load(io.StringIO(first)))
                self.assertEqual(first, second)

    def test_semanticContentPreserved(self):
        """The meaning of the document must survive a dump."""
        for relPath in BLUEPRINTS:
            if relPath in NOT_RELOADABLE:
                # a dump that cannot be parsed back cannot be compared against its source
                continue

            with self.subTest(blueprint=relPath):
                source = _readResolved(relPath)
                dumped = blueprints.Blueprints.dump(blueprints.Blueprints.load(io.StringIO(source)))
                self.assertEqual(_semanticContent(source), _semanticContent(dumped))


class TestKnownRoundTripLimitations(unittest.TestCase):
    """Things a load/dump cycle gets wrong today.

    Each of these is expected to start passing when blueprints move off yamlize. ``unittest`` fails
    an ``expectedFailure`` test that unexpectedly succeeds, so the suite will say so.
    """

    @unittest.expectedFailure
    def test_systemNameMatchingGridNameWithBlankLine(self):
        """A blank line in a ``systems:`` entry produces YAML that ARMI cannot read back.

        yamlize stashes each value's YAML metadata (tag, quote style, comments) in a per-container
        cache keyed on the value itself. A system conventionally has the same name as its grid::

            systems:
                core:
                    grid name: core

                    origin: {...}

        so the string ``"core"`` appears twice in one cache and the two entries collide. The blank
        line -- which ruamel.yaml carries as a comment on the ``grid name`` value -- gets reapplied
        to the system's *key* node on the way out, and the emitter splits the key from its colon::

            systems:
              core

            :
                grid name: core

        which is still valid YAML but no longer the mapping that ``Blueprints`` expects. This is
        why ``c5g7-blueprints.yaml`` is in ``NOT_RELOADABLE``.

        Unlike the hash collisions handled in :py:mod:`armi.reactor.blueprints._yamlizeShims`, this
        one cannot be patched from the outside: the two colliding values are genuinely equal, so no
        choice of cache key separates them. It goes away only when round-trip metadata stops being
        keyed by value.
        """
        source = "systems:\n    core:\n        grid name: core\n\n        origin:\n            x: 0.0\n"
        dumped = blueprints.Blueprints.dump(blueprints.Blueprints.load(io.StringIO(source)))
        blueprints.Blueprints.load(io.StringIO(dumped))

    @unittest.expectedFailure
    def test_commentFollowingAListValuedKeySurvives(self):
        """A comment that follows a list-valued key is dropped.

        Comments survive most positions -- above a key, at end of line, inside a block, at the top
        of the file -- because yamlize copies ruamel.yaml's node metadata across. The exception is
        a comment sitting between a *sequence* value and the next key. yamlize rebuilds sequence
        nodes from scratch in ``Sequence.to_yaml``, and the parent mapping's comment record for
        that slot does not come along.

        A comment after the *last* key still survives, because it lands on the parent mapping
        instead.
        """
        dumped = blueprints.Blueprints.dump(blueprints.Blueprints.load(io.StringIO(self._assemblyWithComment)))
        self.assertIn(self._marker, dumped)

    def test_plainRuamelKeepsCommentFollowingAListValuedKey(self):
        """The same comment survives plain ruamel.yaml, showing the loss is not ruamel.yaml's."""
        yaml = YAML(typ="rt")
        buf = io.StringIO()
        yaml.dump(yaml.load(io.StringIO(self._assemblyWithComment)), buf)
        self.assertIn(self._marker, buf.getvalue())

    _marker = "how tall each block is"

    _assemblyWithComment = """\
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


if __name__ == "__main__":
    unittest.main()
