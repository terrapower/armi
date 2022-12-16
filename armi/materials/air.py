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
from armi.utils import units

"""Simple air material"""

from armi.materials import material
from armi.utils.units import getTk

class Air(material.Fluid):
    """
    Dry, Near Sea Level
    
    Correlations based off of values in Incropera, Frank P., et al.
    Fundamentals of heat and mass transfer. Vol. 5. New York: Wiley, 2002.
    
    Elemental composition from PNNL-15870 Rev. 1
            https://www.pnnl.gov/main/publications/external/technical_reports/PNNL-15870Rev1.pdf
    """

    name = "Air"
    
    """
    temperature ranges based on where values are more than 1% off of reference
    """
    propertyValidTemperature = {
        "density": ((100, 2400), "K"),
        "heat capacity": ((100, 1300), "K"),
        "thermal conductivity": ((200, 850), "K"),
    }
    
    def setDefaultMassFracs(self):
        """
        Set mass fractions 
        
        Notes
        -----
        Mass fraction reference McConn, Ronald J., et al. Compendium of
        material composition data for radiation transport modeling. No. 
        PNNL-15870 Rev. 1. Pacific Northwest National Lab.(PNNL), Richland, 
        WA (United States), 2011.
        
        https://www.pnnl.gov/main/publications/external/technical_reports/PNNL-15870Rev1.pdf
        """
        self.setMassFrac("C", 0.000124)
        self.setMassFrac("N", 0.755268)
        self.setMassFrac("O", 0.231781)
        self.setMassFrac("AR", 0.012827)
            
    def density(self, Tk=None, Tc=None,):
        """
        Returns density of Air in g/cc.

        This is from Table A.4 in
        Fundamentals of Heat and Mass Transfer Incropera, DeWitt

        Parameters
        ----------
        Tk : float, optional
            temperature in degrees Kelvin
        Tc : float, optional
            temperature in degrees Celsius

        Returns
        -------
        density : float
            mass density in g/cc
        """
        Tk = getTk(Tc, Tk)
        self.checkPropertyTempRange("density", Tk)
        inv_Tk = 1./getTk(Tc, Tk)
        rho_kgPerM3 = (1.15675E+03*inv_Tk**2 + 3.43413E+02*inv_Tk + 2.99731E-03)
        return rho_kgPerM3/units.G_PER_CM3_TO_KG_PER_M3
        
    def specificVolumeLiquid(self, Tk=None, Tc=None):
        """
        Returns the liquid specific volume in m^3/kg of this material given Tk in K or Tc in C.
        """
        return 1 / (1000.0 * self.density(Tk, Tc))
     
    def thermalConductivity(self, Tk=None, Tc=None):
        """
        Returns thermal conductivity of Air in g/cc.

        This is from Table A.4 in Fundamentals of Heat and Mass Transfer
        Incropera, DeWitt

        Parameters
        ----------
        Tk : float, optional
            temperature in degrees Kelvin
        Tc : float, optional
            temperature in degrees Celsius

        Returns
        -------
        thermalConductivity : float
            thermal conductivity in W/m*K
        """
        Tk = getTk(Tc, Tk)
        self.checkPropertyTempRange("thermal conductivity", Tk)
        thermalConductivity = (
            2.13014E-08*Tk**3 - 6.31916E-05*Tk**2 + 1.11629E-01*Tk - 2.00043E+00
        )
        return thermalConductivity*1e-3

    def heatCapacity(self, Tk=None, Tc=None):
        """
        Returns heat capacity of Air in g/cc.

        This is from Table A.4 in Fundamentals of Heat and Mass Transfer
        Incropera, DeWitt

        Parameters
        ----------
        Tk : float, optional
            temperature in degrees Kelvin
        Tc : float, optional
            temperature in degrees Celsius

        Returns
        -------
        heatCapacity : float
            heat capacity in J/kg*K
        """
        Tk = getTk(Tc, Tk)
        self.checkPropertyTempRange("heat capacity", Tk)
        return sum(
            [
                +1.38642E-13*Tk**4,
                -6.47481E-10*Tk**3,
                +1.02345E-06*Tk**2,
                -4.32829E-04*Tk,
                +1.06133E+00
            ]
        )*1000. # kJ / kg K to J / kg K
    