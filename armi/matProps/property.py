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

"""A particular material property."""

# TODO: I don't like that this design depends on globals.
properties = set()


class Property:
    """A Property of a material. Most properties are computed as temperature-dependent functions."""

    def __init__(self, name: str, symbol: str, tex: str, units: str):
        """
        Constructor for Property class.

        Parameters
        ----------
        name: str
            Name of the property.
        symbol: str
            Symbol of the property.
        tex: str
            TeX symbol used to represent the property.
        units: str
            String representing the units of the property.
        """
        self.name: str = name
        """Name of the Property, used to retrieve the property from the data file"""

        self.symbol: str = symbol
        """Symbol of the property, same as the module-level attribute and Material attribute"""

        self.TeX: str = tex
        """math-style TeX symbol"""

        self.units: str = units
        """Units of the Property"""

    def __repr__(self):
        """Provides string representation of Property instance."""
        return f"<Property {self.name}, {self.symbol}, in {self.units}>"

    @staticmethod
    def contains(name: str):
        """
        Checks to see if a string representing a desired property is in the global properties list.

        Parameters
        ----------
        name: str
            Name of the property whose value is searched for in global properties list.

        Returns
        -------
        bool
            True if name is in properties, False otherwise.
        """
        """FIXME: This is mixing a global collection of this class inside this class. I hate it."""
        global properties
        return any(name == p.name for p in properties)

    @staticmethod
    def properties():
        """
        Returns a copy list of all the Property object instances.

        Returns
        -------
        list of Property
            Copy list of all Property objects
        """
        # TODO: This is mixing a global collection of this class inside this class. I hate it.
        global properties

        props = []
        for p in properties:
            props.append(p)

        return props


def defProp(symbol: str, name: str, tex: str, units: str):
    """
    Method which constructs and adds Property objects to global properties object.

    Parameters
    ----------
    name: str
        Name of the property.
    symbol: str
        Symbol of the property.
    tex: str
        TeX symbol used to represent the property.
    units: str
        String representing the units of the property.
    """
    global properties
    if Property.contains(name):
        raise KeyError(f"Property already defined: {name}")

    p = Property(name, symbol, tex, units)
    exec(f"global {symbol};{symbol} = p")  # TODO: Not myfavorite. Not very Python.
    properties.add(p)


def initialize():
    """Method which constructs list of approved properties in armi.matProps."""
    defProp("alpha_d", "thermal diffusivity", r"(\alpha_d)", "m^2/s")
    defProp(
        "alpha_inst",
        "instantaneous coefficient of thermal expansion",
        r"(\alpha_{inst})",
        r"(1/^\circ{}C)",
    )
    defProp(
        "alpha_mean",
        "mean coefficient of thermal expansion",
        r"(\alpha_{mean})",
        r"(1/^\circ{}C)",
    )
    defProp("c_p", "specific heat capacity", "c_p", r"U(J/(kg\dot{}^\circ{}C))U")
    defProp("E", "Young's modulus", "E", "Pa")
    defProp("S", "shear modulus", "S", "Pa")
    defProp("Elong", "elongation", r"\epsilon", "%")
    defProp("k", "thermal conductivity", "k", r"U(W/(m\dot{}^\circ{}C))U")
    defProp("mu_d", "dynamic viscosity", r"(\mu_d)", r"(Pa\dot{}s)")
    defProp("mu_k", "kinematic viscosity", r"(\mu_k)", "m^2/s")
    defProp("nu", "Poisson's ratio", r"(\nu)", "unitless")
    defProp("rho", "density", r"(\rho)", "kg/m^3")
    defProp("Sa", "allowable stress", "Sa", "Pa")
    defProp("Sm", "design stress", "Sm", "Pa")
    defProp("Smt", "service reference stress", "Smt", "Pa")
    defProp("So", "design reference stress", "So", "Pa")
    defProp("Sr", "stress to rupture", "Sr", "Pa")
    defProp("St", "time dependent design stress", "St", "Pa")
    defProp("Su", "tensile strength", "Su", "Pa")
    defProp("Sy", "yield strength", "Sy", "Pa")
    defProp("tMaxSr", "allowable time to rupture", "tMaxSr", "s")
    defProp("tMaxSt", "allowable time to allowable stress", "tMaxSt", "s")
    defProp("TSRF", "tensile strength reduction factor", "TSRF", "unitless")
    defProp("YSRF", "yield strength reduction factor", "YSRF", "unitless")
    defProp("WSRF", "weld strength reduction factor", "WSRF", "unitless")
    defProp("eps_t", "design fatigue strain range", "eps_t", "unitless")
    defProp("eps_iso", "strain from isochronous stress-strain curve", "eps_iso", "unitless")
    defProp("SaFat", "design fatigue stress", "SaFat", "Pa")
    defProp("gamma", "surface tension", r"(\gamma)", r"(N\dot m)")
    defProp("G", "electrical conductance", "G", r"U(1/(\Omega\dot m))U")
    defProp("P_sat", "vapor pressure", "P_{sat}", r"(Pa)")
    defProp("kappa", "isothermal compressibility", r"(\kappa)", r"(1/Pa)")
    defProp("T_melt", "melting temperature", r"(T_{melt})", r"(^\circ{}C)")
    defProp("T_boil", "boiling temperature", r"(T_{boil})", r"(^\circ{}C)")
    defProp("dl_l", "linear expansion", r"\Delta l_{percent}", "unitless")
    defProp("nu_g", "vapor specific volume", r"\nu", "m^3/kg")
    defProp("v_sound", "speed of sound", r"(v_{sound})", "m/s")
    defProp("T_sol", "solidus temperature", r"(T_{sol})", r"(^\circ{}C)")
    defProp("T_liq", "liquidus temperature", r"(T_{liq})", r"(^\circ{}C)")
    defProp("dV", "volumetric expansion", r"\Delta V", r"m^3/(^\circ{}C)")
    defProp("H", "enthalpy", "H", "J/kg")
    defProp("H_calc_T", "temperature from enthalpy", r"(^\circ{}C)", r"(^\circ{}C)")
    defProp("dH_fus", "enthalpy of fusion", r"(\Delta H_{f})", "J/kg")
    defProp("dH_vap", "latent heat of vaporization", r"(\Delta H_{v})", "J/kg")
    defProp("K_IC", "fracture toughness", r"K_{IC}", r"MPa\dot\sqrt(m)")
    defProp("HBW", "Brinell Hardness", "HBW", "BHN")
    defProp("f", "factor f from ASME.III.5 Fig. HBB-T-1432-2", "f", "unitless")
    defProp(
        "Kv_prime",
        "factor Kv' from ASME.III.5 Fig. HBB-T-1432-3",
        r"K_{v}^{'}",
        "unitless",
    )


initialize()
