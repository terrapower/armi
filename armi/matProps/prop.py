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

"""
In the parlance of matProps, a material 'Property' is a physical characteristic of the material that can be described
mathematically. For instance, density, specific heat, specific gravity, coefficient of linear expansion, etc.
"""

properties = set()

PROPERTIES = {
    "alpha_d": ("thermal diffusivity", "m^2/s", r"(\alpha_d)"),
    "alpha_inst": ("instantaneous coefficient of thermal expansion", r"(1/^\circ{}C)", r"(\alpha_{inst})"),
    "alpha_mean": ("mean coefficient of thermal expansion", r"(1/^\circ{}C)", r"(\alpha_{mean})"),
    "c_p": ("specific heat capacity", r"U(J/(kg\dot{}^\circ{}C))U"),
    "dH_fus": ("enthalpy of fusion", "J/kg", r"(\Delta H_{f})"),
    "dH_vap": ("latent heat of vaporization", "J/kg", r"(\Delta H_{v})"),
    "dl_l": ("linear expansion", "unitless", r"\Delta l_{percent}"),
    "dV": ("volumetric expansion", r"m^3/(^\circ{}C)", r"\Delta V"),
    "E": ("Young's modulus", "Pa"),
    "Elong": ("elongation", "%", r"\epsilon"),
    "eps_iso": ("strain from isochronous stress-strain curve", "unitless"),
    "eps_t": ("design fatigue strain range", "unitless"),
    "f": ("factor f from ASME.III.5 Fig. HBB-T-1432-2", "unitless"),
    "G": ("electrical conductance", r"U(1/(\Omega\dot m))U"),
    "gamma": ("surface tension", r"(N\dot m)", r"(\gamma)"),
    "H": ("enthalpy", "J/kg"),
    "H_calc_T": ("temperature from enthalpy", r"(^\circ{}C)", r"(^\circ{}C)"),
    "HBW": ("Brinell Hardness", "BHN"),
    "k": ("thermal conductivity", r"U(W/(m\dot{}^\circ{}C))U"),
    "K_IC": ("fracture toughness", r"MPa\dot\sqrt(m)", r"K_{IC}"),
    "kappa": ("isothermal compressibility", r"(1/Pa)", r"(\kappa)"),
    "Kv_prime": ("factor Kv' from ASME.III.5 Fig. HBB-T-1432-3", "unitless", r"K_{v}^{'}"),
    "mu_d": ("dynamic viscosity", r"(Pa\dot{}s)", r"(\mu_d)"),
    "mu_k": ("kinematic viscosity", "m^2/s", r"(\mu_k)"),
    "nu": ("Poisson's ratio", "unitless", r"(\nu)"),
    "nu_g": ("vapor specific volume", "m^3/kg", r"\nu"),
    "P_sat": ("vapor pressure", r"(Pa)", "P_{sat}"),
    "rho": ("density", "kg/m^3", r"(\rho)"),
    "S": ("shear modulus", "Pa"),
    "Sa": ("allowable stress", "Pa"),
    "SaFat": ("design fatigue stress", "Pa"),
    "Sm": ("design stress", "Pa"),
    "Smt": ("service reference stress", "Pa"),
    "So": ("design reference stress", "Pa"),
    "Sr": ("stress to rupture", "Pa"),
    "St": ("time dependent design stress", "Pa"),
    "Su": ("tensile strength", "Pa"),
    "Sy": ("yield strength", "Pa"),
    "T_boil": ("boiling temperature", r"(^\circ{}C)", r"(T_{boil})"),
    "T_liq": ("liquidus temperature", r"(^\circ{}C)", r"(T_{liq})"),
    "T_melt": ("melting temperature", r"(^\circ{}C)", r"(T_{melt})"),
    "T_sol": ("solidus temperature", r"(^\circ{}C)", r"(T_{sol})"),
    "tMaxSr": ("allowable time to rupture", "s"),
    "tMaxSt": ("allowable time to allowable stress", "s"),
    "TSRF": ("tensile strength reduction factor", "unitless"),
    "v_sound": ("speed of sound", "m/s", r"(v_{sound})"),
    "WSRF": ("weld strength reduction factor", "unitless"),
    "YSRF": ("yield strength reduction factor", "unitless"),
}


class Property:
    """A Property of a material. Most properties are computed as temperature-dependent functions."""

    def __init__(self, name: str, symbol: str, units: str, tex: str = None):
        """
        Constructor for Property class.

        Parameters
        ----------
        name: str
            Name of the property.
        symbol: str
            Symbol of the property.
        units: str
            String representing the units of the property.
        tex: str (optional)
            TeX symbol used to represent the property. Defaults to symbol.
        """
        self.name: str = name
        """Name of the Property, used to retrieve the property from the data file"""

        self.symbol: str = symbol
        """Symbol of the property, same as the module-level attribute and Material attribute"""

        self.units: str = units
        """Units of the Property"""

        self.TeX: str = tex if tex is not None else symbol
        """math-style TeX symbol"""

    def __repr__(self):
        """Provides string representation of Property instance."""
        return f"<Property {self.name}, {self.symbol}, in {self.units}>"


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
    global properties
    return any(name == p.name for p in properties)


def defProp(symbol: str, name: str, units: str, tex: str = None):
    """
    Method which constructs and adds Property objects to global properties object.

    Parameters
    ----------
    name: str
        Name of the property.
    symbol: str
        Symbol of the property.
    units: str
        String representing the units of the property.
    tex: str (optional)
        TeX symbol used to represent the property. Defaults to symbol.
    """
    global properties
    if contains(name):
        raise KeyError(f"Property already defined: {name}")

    if tex is None:
        tex = symbol

    p = Property(name, symbol, units, tex)
    properties.add(p)


def initialize():
    """Construct the global list of default properties in matProps."""
    for symbol, vals in PROPERTIES.items():
        name = vals[0]
        units = vals[1]
        tex = vals[2] if len(vals) > 2 else None
        defProp(symbol, name, units, tex)


initialize()
