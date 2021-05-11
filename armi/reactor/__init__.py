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

.. pyreverse:: armi.reactor -A -k --ignore=complexShapes.py,grids.py,componentParameters.py,dodecaShapes.py,volumetricShapes.py,tests,converters,blockParameters.py,assemblyParameters.py,reactorParameters.py,batchParameters.py,basicShapes.py,shapes.py,zones.py,parameters,flags.py,geometry.py,blueprints,batch.py,assemblyLists.py,plugins.py
    :align: center
    :alt: Reactor class diagram
    :width: 90%

    Class inheritance diagram for :py:mod:`armi.reactor`.

See :doc:`/developer/index`.
"""

from armi import plugins


class ReactorPlugin(plugins.ArmiPlugin):
    """
    Plugin exposing built-in reactor components, blocks, assemblies, etc.
    """

    @staticmethod
    @plugins.HOOKIMPL
    def defineBlockTypes():
        from .components.basicShapes import Rectangle, Hexagon
        from .components.volumetricShapes import RadialSegment
        from . import blocks

        return [
            (Rectangle, blocks.CartesianBlock),
            (RadialSegment, blocks.ThRZBlock),
            (Hexagon, blocks.HexBlock),
        ]

    @staticmethod
    @plugins.HOOKIMPL
    def defineAssemblyTypes():
        from .blocks import HexBlock, CartesianBlock, ThRZBlock
        from .assemblies import (
            HexAssembly,
            CartesianAssembly,
            ThRZAssembly,
        )

        return [
            (HexBlock, HexAssembly),
            (CartesianBlock, CartesianAssembly),
            (ThRZBlock, ThRZAssembly),
        ]
