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

r"""
The reactor package houses the data model used in ARMI to represent the reactor during its
simulation. It contains definitions of the reactor, assemblies, blocks, components, etc.

The key classes of the reactor package are shown below:

.. _reactor-class-diagram:

.. pyreverse:: armi.reactor -A -k --ignore=
               assemblyParameters.py,
               basicShapes.py,
               blockParameters.py,
               blueprints,
               complexShapes.py,
               componentParameters.py,
               converters,
               excoreStructure.py,
               flags.py,
               geometry.py,
               grids.py,
               parameters,
               plugins.py,
               reactorParameters.py,
               shapes.py,
               spentFuelPool.py,
               tests,
               volumetricShapes.py,
               zones.py
    :align: center
    :alt: Reactor class diagram
    :width: 90%

    Class inheritance diagram for :py:mod:`armi.reactor`.

See :doc:`/developer/index`.
"""

from typing import Dict, Callable, Union, TYPE_CHECKING

from armi import plugins

# Provide type checking but avoid circular imports
# Not used during runtime so we could have a coverage drop here. Add the
# pragma line to tell coverage.py to skip this
# https://coverage.readthedocs.io/en/stable/excluding.html
if TYPE_CHECKING:  # pragma: no cover
    from armi.reactor.reactors import Core
    from armi.reactor.excoreStructure import ExcoreStructure
    from armi.reactor.spentFuelPool import SpentFuelPool


class ReactorPlugin(plugins.ArmiPlugin):
    """Plugin exposing built-in reactor components, blocks, assemblies, etc."""

    @staticmethod
    @plugins.HOOKIMPL
    def defineBlockTypes():
        from armi.reactor.components.basicShapes import Rectangle, Hexagon
        from armi.reactor.components.volumetricShapes import RadialSegment
        from armi.reactor import blocks

        return [
            (Rectangle, blocks.CartesianBlock),
            (RadialSegment, blocks.ThRZBlock),
            (Hexagon, blocks.HexBlock),
        ]

    @staticmethod
    @plugins.HOOKIMPL
    def defineAssemblyTypes():
        from armi.reactor.blocks import HexBlock, CartesianBlock, ThRZBlock
        from armi.reactor.assemblies import HexAssembly, CartesianAssembly, ThRZAssembly

        return [
            (HexBlock, HexAssembly),
            (CartesianBlock, CartesianAssembly),
            (ThRZBlock, ThRZAssembly),
        ]

    @staticmethod
    @plugins.HOOKIMPL(trylast=True)
    def defineSystemBuilders() -> Dict[
        str, Callable[[str], Union["Core", "ExcoreStructure", "SpentFuelPool"]]
    ]:
        from armi.reactor.spentFuelPool import SpentFuelPool
        from armi.reactor.excoreStructure import ExcoreStructure
        from armi.reactor.reactors import Core

        return {
            "core": Core,
            "excore": ExcoreStructure,
            "sfp": SpentFuelPool,
        }
