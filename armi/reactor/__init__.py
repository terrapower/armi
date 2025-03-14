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

See :doc:`/developer/index`.
"""

from typing import TYPE_CHECKING, Callable, Dict, Union

from armi import materials, plugins

if TYPE_CHECKING:
    from armi.reactor.excoreStructure import ExcoreStructure
    from armi.reactor.reactors import Core
    from armi.reactor.spentFuelPool import SpentFuelPool


class ReactorPlugin(plugins.ArmiPlugin):
    """Plugin exposing built-in reactor components, blocks, assemblies, etc."""

    @staticmethod
    @plugins.HOOKIMPL
    def beforeReactorConstruction(cs) -> None:
        """Just before reactor construction, update the material "registry" with user settings,
        if it is set. Often it is set by the application.
        """
        from armi.settings.fwSettings.globalSettings import (
            CONF_MATERIAL_NAMESPACE_ORDER,
        )

        if cs[CONF_MATERIAL_NAMESPACE_ORDER]:
            materials.setMaterialNamespaceOrder(cs[CONF_MATERIAL_NAMESPACE_ORDER])

    @staticmethod
    @plugins.HOOKIMPL
    def defineBlockTypes():
        from armi.reactor import blocks
        from armi.reactor.components.basicShapes import Hexagon, Rectangle
        from armi.reactor.components.volumetricShapes import RadialSegment

        return [
            (Rectangle, blocks.CartesianBlock),
            (RadialSegment, blocks.ThRZBlock),
            (Hexagon, blocks.HexBlock),
        ]

    @staticmethod
    @plugins.HOOKIMPL
    def defineAssemblyTypes():
        from armi.reactor.assemblies import CartesianAssembly, HexAssembly, ThRZAssembly
        from armi.reactor.blocks import CartesianBlock, HexBlock, ThRZBlock

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
        from armi.reactor.excoreStructure import ExcoreStructure
        from armi.reactor.reactors import Core
        from armi.reactor.spentFuelPool import SpentFuelPool

        return {
            "core": Core,
            "excore": ExcoreStructure,
            "sfp": SpentFuelPool,
        }

    @staticmethod
    @plugins.HOOKIMPL(trylast=True)
    def getAxialExpansionChanger():
        from armi.reactor.converters.axialExpansionChanger import AxialExpansionChanger

        return AxialExpansionChanger
