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


"""Unit tests for the symbolic function class."""

import copy
import math
import pickle
import unittest

import numpy as np

from armi.matProps.material import Material


class TestSymbolicFunction(unittest.TestCase):
    """Unit tests for the symbolic function class."""

    def setUp(self):
        self.yaml = {
            "file format": "TESTS",
            "material type": "Metal",
            "composition": {"a": "balance"},
            "density": {
                "function": {
                    "type": "symbolic",
                    "X": {"min": -10, "max": 500.0},
                    "Y": {"min": 1.0, "max": 20.0},
                    "Z": {"min": -30.0, "max": -10.0},
                    "equation": 1.0,
                }
            },
        }

    def loadMaterial(self, num=1):
        """Loads the material file based on `self.yaml` and returns the material object."""
        mat = Material()
        mat.loadNode(self.yaml)

        return mat

    def functionTest(self, func, num=1):
        """
        Takes a function as input to compare against matProps material output.
        It is assumed that `self.yaml` has been updated to match the provided evaluation function.
        """
        mat = self.loadMaterial(num=num)
        prop = mat.rho
        for x in np.linspace(prop.getMinBound("X"), prop.getMaxBound("X"), 20):
            for y in np.linspace(prop.getMinBound("Y"), prop.getMaxBound("Y"), 20):
                for z in np.linspace(prop.getMinBound("Z"), prop.getMaxBound("Z"), 20):
                    received = prop.calc({"X": x, "Y": y, "Z": z})
                    expected = func(x, y, z)
                    self.assertAlmostEqual(
                        received,
                        expected,
                        msg=(
                            f"Material property evaluation does not match for: {prop.sympyStr} at ({x}, {y}, {z}).\n"
                            f" Received: {received}, Expected: {expected}"
                        ),
                        delta=abs(
                            expected / 1e8
                        ),  # very large numbers can have floating point differences at low decimal count
                    )

    def setEqnField(self, eqn):
        self.yaml["density"]["function"]["equation"] = eqn

    def test_symbolicMult(self):
        """
        Test multiplication operator for symbolic equations.

        Four combinations of spacing and the operator are tested for multiplying a variable and a constant as well as
        multiplying two variables. For each input, the property is evaluated at 20 evenly spaced points per independent
        variable within the valid range.
        """
        func = lambda x, y, z: x * 20
        self.setEqnField("X * 20")
        self.functionTest(func, 1)

        self.setEqnField("X*20")
        self.functionTest(func, 2)

        self.setEqnField("X* 20")
        self.functionTest(func, 3)

        self.setEqnField("X *20")
        self.functionTest(func, 4)

        func = lambda x, y, z: x * y
        self.setEqnField("X * Y")
        self.functionTest(func, 5)

        self.setEqnField("X*Y")
        self.functionTest(func, 6)

        self.setEqnField("X*Y")
        self.functionTest(func, 7)

        self.setEqnField("X *Y")
        self.functionTest(func, 8)

    def test_symbolicExponent(self):
        """
        Test exponent operator for symbolic equations.

        Four combinations of spacing and the operator are tested for raising a variable by a constant as well as raising
        a constant by a constant. For each input, the property is evaluated at 20 evenly spaced points per independent
        variable within the valid range.
        """
        func = lambda x, y, z: x**3
        self.setEqnField("X ** 3")
        self.functionTest(func, 1)

        self.setEqnField("X**3")
        self.functionTest(func, 2)

        self.setEqnField("X** 3")
        self.functionTest(func, 3)

        self.setEqnField("X **3")
        self.functionTest(func, 4)

        func = lambda x, y, z: 1.1**y
        self.setEqnField("1.1 ** Y")
        self.functionTest(func, 5)

        self.setEqnField("1.1**Y")
        self.functionTest(func, 6)

        self.setEqnField("1.1** Y")
        self.functionTest(func, 7)

        self.setEqnField("1.1 **Y")
        self.functionTest(func, 8)

    def test_symbolicDiv(self):
        """
        Test division operator for symbolic equations.

        The four combinations of spacing and the operator are tested for dividing a variable and a constant as well as
        dividing two variables. For each input, the property is evaluated at 20 evenly spaced points per independent
        variable within the valid range.
        """
        func = lambda x, y, z: x / 3
        self.setEqnField("X / 3")
        self.functionTest(func, 1)

        self.setEqnField("X/3")
        self.functionTest(func, 2)

        self.setEqnField("X/ 3")
        self.functionTest(func, 3)

        self.setEqnField("X /3")
        self.functionTest(func, 4)

        func = lambda x, y, z: x / y
        self.setEqnField("X / Y")
        self.functionTest(func, 5)

        self.setEqnField("X/Y")
        self.functionTest(func, 6)

        self.setEqnField("X/ Y")
        self.functionTest(func, 7)

        self.setEqnField("X /Y")
        self.functionTest(func, 8)

    def test_symbolicAdd(self):
        """
        Test addition operator for symbolic equations.

        Four combinations of spacing and the operator are tested for adding a variable and a constant as well as adding
        two variables. For each input, the property is evaluated at 20 evenly spaced points per independent variable
        within the valid range.
        """
        func = lambda x, y, z: x + 3
        self.setEqnField("X + 3")
        self.functionTest(func, 1)

        self.setEqnField("X+3")
        self.functionTest(func, 2)

        self.setEqnField("X+ 3")
        self.functionTest(func, 3)

        self.setEqnField("X +3")
        self.functionTest(func, 4)

        func = lambda x, y, z: x + y
        self.setEqnField("X + Y")
        self.functionTest(func, 5)

        self.setEqnField("X+Y")
        self.functionTest(func, 6)

        self.setEqnField("X+ Y")
        self.functionTest(func, 7)

        self.setEqnField("X +Y")
        self.functionTest(func, 8)

    def test_symbolicSub(self):
        """
        Test subtraction operator for symbolic equations.

        Four combinations of spacing and the operator are tested for subtracting a variable and a constant as well
        as subtracting two variables. For each input, the property is evaluated at 20 evenly spaced points per
        independent variable within the valid range.
        """
        func = lambda x, y, z: x - 3
        self.setEqnField("X - 3")
        self.functionTest(func, 1)

        self.setEqnField("X-3")
        self.functionTest(func, 2)

        self.setEqnField("X- 3")
        self.functionTest(func, 3)

        self.setEqnField("X -3")
        self.functionTest(func, 4)

        func = lambda x, y, z: x - z
        self.setEqnField("X - Z")
        self.functionTest(func, 5)

        self.setEqnField("X-Z")
        self.functionTest(func, 6)

        self.setEqnField("X- Z")
        self.functionTest(func, 7)

        self.setEqnField("X -Z")
        self.functionTest(func, 8)

    def test_symbolicParens(self):
        """
        Test the grouping operator for symbolic equations.

        Various combinations of grouping is tested with spacing on a simple addition operation. For each input, the
        property is evaluated at 20 evenly spaced points per independent variable within the valid range.
        """
        func = lambda x, y, z: x + 3
        self.setEqnField("(X + 3)")
        self.functionTest(func, 1)

        self.setEqnField("(X) + 3")
        self.functionTest(func, 2)

        self.setEqnField("X + (3)")
        self.functionTest(func, 3)

        self.setEqnField("(X) + (3)")
        self.functionTest(func, 4)

        self.setEqnField("(X ) + 3")
        self.functionTest(func, 5)

        self.setEqnField("( X) + 3")
        self.functionTest(func, 6)

        self.setEqnField("( X ) + 3")
        self.functionTest(func, 7)

        self.setEqnField("( X + 3)")
        self.functionTest(func, 8)

        self.setEqnField("(X + 3 )")
        self.functionTest(func, 9)

    def test_symbolicSine(self):
        """
        Test sine operator for symbolic equations.

        Four combinations of spacing and the operator are tested. For each input, the property is evaluated at 20
        evenly spaced points per independent variable within the valid range.
        """
        func = lambda x, y, z: math.sin(x)
        self.setEqnField("sin(X)")
        self.functionTest(func, 1)

        self.setEqnField("sin (X)")
        self.functionTest(func, 2)

        self.setEqnField("sin( X)")
        self.functionTest(func, 3)

        self.setEqnField("sin(X )")
        self.functionTest(func, 4)

    def test_symbolicCosine(self):
        """
        Test cosine operator for symbolic equations.

        Four combinations of spacing and the operator are tested. For each input, the property is evaluated at 20 evenly
        spaced points per independent variable within the valid range.
        """
        func = lambda x, y, z: math.cos(x)
        self.setEqnField("cos(X)")
        self.functionTest(func, 1)

        self.setEqnField("cos (X)")
        self.functionTest(func, 2)

        self.setEqnField("cos( X)")
        self.functionTest(func, 3)

        self.setEqnField("cos(X )")
        self.functionTest(func, 4)

    def test_symbolicTan(self):
        """
        Test tangent operator for symbolic equations.

        Four combinations of spacing and the operator are tested. For each input, the property is evaluated at 20 evenly
        spaced points per independent variable within the valid range.
        """
        func = lambda x, y, z: math.tan(x)
        self.setEqnField("tan(X)")
        self.functionTest(func, 1)

        self.setEqnField("tan (X)")
        self.functionTest(func, 2)

        self.setEqnField("tan( X)")
        self.functionTest(func, 3)

        self.setEqnField("tan(X )")
        self.functionTest(func, 4)

    def test_symbolicSinh(self):
        """
        Test hyperbolic sine operator for symbolic equations.

        Four combinations of spacing and the operator are tested. For each input, the property is evaluated at 20 evenly
        spaced points per independent variable within the valid range.
        """
        func = lambda x, y, z: math.sinh(x)
        self.setEqnField("sinh(X)")
        self.functionTest(func, 1)

        self.setEqnField("sinh (X)")
        self.functionTest(func, 2)

        self.setEqnField("sinh( X)")
        self.functionTest(func, 3)

        self.setEqnField("sinh(X )")
        self.functionTest(func, 4)

    def test_symbolicCosh(self):
        """
        Test hyperbolic cosine operator for symbolic equations.

        Four combinations of spacing and the operator are tested. For each input, the property is evaluated at 20 evenly
        spaced points per independent variable within the valid range.
        """
        func = lambda x, y, z: math.cosh(x)
        self.setEqnField("cosh(X)")
        self.functionTest(func, 1)

        self.setEqnField("cosh (X)")
        self.functionTest(func, 2)

        self.setEqnField("cosh( X)")
        self.functionTest(func, 3)

        self.setEqnField("cosh(X )")
        self.functionTest(func, 4)

    def test_symbolicTanh(self):
        """
        Test hyperbolic tangent operator for symbolic equations.

        Four combinations of spacing and the operator are tested. For each input, the property is evaluated at 20 evenly
        spaced points per independent variable within the valid range.
        """
        func = lambda x, y, z: math.tanh(x)
        self.setEqnField("tanh(X)")
        self.functionTest(func, 1)

        self.setEqnField("tanh (X)")
        self.functionTest(func, 2)

        self.setEqnField("tanh( X)")
        self.functionTest(func, 3)

        self.setEqnField("tanh(X )")
        self.functionTest(func, 4)

    def test_symbolicNatLog(self):
        """
        Test natural logarithm operator for symbolic equations.

        Both log and ln variations of the function name are tested. Four combinations of spacing and the operator are
        tested for each function name. For each input, the property is evaluated at 20 evenly spaced points per
        independent variable within the valid range.
        """
        func = lambda x, y, z: math.log(y)
        self.setEqnField("ln(Y)")
        self.functionTest(func, 1)

        self.setEqnField("ln (Y)")
        self.functionTest(func, 2)

        self.setEqnField("ln( Y)")
        self.functionTest(func, 3)

        self.setEqnField("ln(Y )")
        self.functionTest(func, 4)

        self.setEqnField("log(Y)")
        self.functionTest(func, 5)

        self.setEqnField("log (Y)")
        self.functionTest(func, 6)

        self.setEqnField("log( Y)")
        self.functionTest(func, 7)

        self.setEqnField("log(Y )")
        self.functionTest(func, 8)

    def test_symbolicLog10(self):
        """
        Test base ten logarithm operator for symbolic equations.

        Four combinations of spacing and the operator are tested. For each input, the property is evaluated at 20 evenly
        spaced points per independent variable within the valid range.
        """
        func = lambda x, y, z: math.log10(y)
        self.setEqnField("log10(Y)")
        self.functionTest(func, 1)

        self.setEqnField("log10 (Y)")
        self.functionTest(func, 2)

        self.setEqnField("log10( Y)")
        self.functionTest(func, 3)

        self.setEqnField("log10(Y )")
        self.functionTest(func, 4)

    def test_symbolicExp(self):
        """
        Test exponential operator for symbolic equations.

        Four combinations of spacing and the operator are tested. For each input, the property is evaluated at 20 evenly
        spaced points per independent variable within the valid range.
        """
        func = lambda x, y, z: math.exp(y)
        self.setEqnField("exp(Y)")
        self.functionTest(func, 1)

        self.setEqnField("exp (Y)")
        self.functionTest(func, 2)

        self.setEqnField("exp( Y)")
        self.functionTest(func, 3)

        self.setEqnField("exp(Y )")
        self.functionTest(func, 4)

    def test_symbolicComposition(self):
        """
        Test composition of functions for symbolic equations.

        Four different functions are tested that are composites of other functions. For each input, the property is
        evaluated at 20 evenly spaced points per independent variable within the valid range.
        """
        # Multiple functions on one side of multiplication/divide
        func = lambda x, y, z: x / (math.exp(y) + z)
        self.setEqnField("X / (exp(Y) + Z)")
        self.functionTest(func, 1)

        # Multiple functions inside trig function
        func = lambda x, y, z: x * math.sin(z**y)
        self.setEqnField("X * sin(Z**Y)")
        self.functionTest(func, 2)

        # Multiple functions inside hyperbolic function
        func = lambda x, y, z: math.tanh((x + 30) ** math.cos(y) + z * 0.2)
        self.setEqnField("tanh((X+30) ** cos(Y) + Z*0.2)")
        self.functionTest(func, 3)

        # Many sets of nested parentheses
        func = lambda x, y, z: ((x / (y * z + 1.0)) + 2.5) * 10.2
        self.setEqnField("((X / (Y*Z + 1.0)) + 2.5)*10.2")
        self.functionTest(func, 4)

    def test_symbolicOrdop(self):
        """
        Test order of operations for symbolic equations.

        Five different equations are evaluated that test different components of order precedence. For each input, the
        property is evaluated at 20 evenly spaced points per independent variable within the valid range.
        """
        # multiplication and division before addition and subtraction
        func = lambda x, y, z: (x * y) + z
        self.setEqnField("X * Y + Z")
        self.functionTest(func, 1)

        func = lambda x, y, z: x + (y * z)
        self.setEqnField("X + Y * Z")
        self.functionTest(func, 2)

        # Left to right for same precedence operators
        func = lambda x, y, z: (x * y) / z
        self.setEqnField("X * Y / Z")
        self.functionTest(func, 3)

        # Exponents before multiplication/division
        func = lambda x, y, z: ((x + 30) ** 1.1) * (y**2)
        self.setEqnField("(X+30) ** 1.1 * Y ** 2")
        self.functionTest(func, 4)

        # Parentheses before exponents
        func = lambda x, y, z: (x + 30) ** (y / 2) - z
        self.setEqnField("(X+30) ** (Y/2) - Z")
        self.functionTest(func, 5)

    def test_symbolicWhitespace(self):
        """
        Test excess whitespace is ignored for symbolic equations.

        Two different equations are evaluated with varying amounts of whitespace introduced to ensure they produce the
        same results. For each input, the property is evaluated at 20 evenly spaced points per independent variable
        within the valid range of the property.
        """
        func = lambda x, y, z: x + y + z
        self.setEqnField("           X + Y + Z")
        self.functionTest(func, 1)

        self.setEqnField(" X  +   Y +    Z")
        self.functionTest(func, 2)

        self.setEqnField("X                + Y + Z")
        self.functionTest(func, 3)

        self.setEqnField("X              +            Y + Z")
        self.functionTest(func, 4)

        self.setEqnField("           X + Y + Z")
        self.functionTest(func, 5)

        func = lambda x, y, z: math.sin(x) * y + z
        self.setEqnField("sin          (X) * Y + Z")
        self.functionTest(func, 6)

        self.setEqnField("   sin(     X         ) * Y + Z")
        self.functionTest(func, 7)

        self.setEqnField("sin(X         )                  * Y +           Z")
        self.functionTest(func, 8)

    def test_symbolicIntFloat(self):
        """
        Test handling of integers and floats for symbolic equations.

        Multiple equations are tested that verify that when integers are used in equations they do not result in integer
        multiplication and division in Python and are instead treated as floating point numbers. For each input, the
        property is evaluated at 20 evenly spaced points per independent variable within the valid range.
        """
        func = lambda x, y, z: x / 2.0 + 3.0
        self.setEqnField("X / 2 + 3")
        self.functionTest(func, 1)

        self.setEqnField("X / 2.0 + 3.0")
        self.functionTest(func, 2)

        func = lambda x, y, z: (x + 30) ** (4.0 / 3.0)
        self.setEqnField("(X + 30) ** (4/3)")
        self.functionTest(func, 3)

        self.setEqnField("(X + 30) ** (4.0/3.0)")
        self.functionTest(func, 4)

    def test_symbolicBadParens(self):
        """
        Test unbalanced parentheses results in errors for symbolic equations.

        Multiple equations are tested that verify that various combinations of unbalanced parentheses are detected and
        result in an error when parsing the input. Additionally, an expression with extraneous but balanced parentheses
        is tested for correctness. For that input, the property is evaluated at 20 evenly spaced points per independent
        variable within the valid range.
        """
        with self.assertRaises(ValueError):
            self.setEqnField("(X + Y")
            self.loadMaterial(num=1)

        with self.assertRaises(ValueError):
            self.setEqnField("((X) + Y")
            self.loadMaterial(num=2)

        with self.assertRaises(ValueError):
            self.setEqnField("(X) + Y)")
            self.loadMaterial(num=3)

        with self.assertRaises(ValueError):
            self.setEqnField("exp(X")
            self.loadMaterial(num=4)

        with self.assertRaises(ValueError):
            self.setEqnField("exp X")
            self.loadMaterial(num=5)

        with self.assertRaises(ValueError):
            self.setEqnField("(((((X + Y)))) + (Z)))")
            self.loadMaterial(num=6)

        # Test extraneous parentheses as well
        func = lambda x, y, z: x + y + z
        self.setEqnField("(((((X + Y)))) + (Z))")
        self.functionTest(func, 7)

    def test_symbolicUndefined(self):
        """
        Test that undefined functions results in errors for symbolic equations.

        A logarthmic function is evaluated at two points in the valid range to show that the material input is parsed
        correctly. The function is then evaluated at a value that results in a negative expression inside the logarithm
        which is undefined.
        """
        self.setEqnField("ln(X)")
        mat = self.loadMaterial(num=1)
        prop = mat.rho

        self.assertAlmostEqual(prop.calc({"X": 3, "Y": 3, "Z": -20}), math.log(3))
        self.assertAlmostEqual(prop.calc({"X": 100, "Y": 3, "Z": -20}), math.log(100))

        with self.assertRaises(ValueError):
            prop.calc({"X": -5, "Y": 3, "Z": -20})

    def test_symbolicCaps(self):
        """
        Test bad capitalization results in errors for symbolic equations.

        Multiple equations are tested that verify that various combinations of capitalization are detected and result in
        an error when parsing the inputs.
        """
        with self.assertRaises(ValueError):
            self.setEqnField("x + Y")
            self.loadMaterial(num=1)

        with self.assertRaises(ValueError):
            self.setEqnField("TAN(X) + Y")
            self.loadMaterial(num=2)

        with self.assertRaises(ValueError):
            self.setEqnField("Tan(X) + Y")
            self.loadMaterial(num=3)

        with self.assertRaises(ValueError):
            self.setEqnField("eXP(X) + Y")
            self.loadMaterial(num=4)

    def test_symbolicImpmult(self):
        """
        Test implicit multiplication results in errors for symbolic equations.

        Multiple equations are tested that verify that various combinations of implicit multiplication are detected and
        result in an error when parsing the inputs.
        """
        with self.assertRaises(ValueError):
            self.setEqnField("2 X")
            self.loadMaterial(num=1)

        with self.assertRaises(ValueError):
            self.setEqnField("X 2")
            self.loadMaterial(num=2)

        with self.assertRaises(ValueError):
            self.setEqnField("2X")
            self.loadMaterial(num=3)

        with self.assertRaises(ValueError):
            self.setEqnField("2(X)")
            self.loadMaterial(num=4)

        with self.assertRaises(ValueError):
            self.setEqnField("X(2)")
            self.loadMaterial(num=5)

        with self.assertRaises(ValueError):
            self.setEqnField("X (2)")
            self.loadMaterial(num=6)

        with self.assertRaises(ValueError):
            self.setEqnField("2 sin(X)")
            self.loadMaterial(num=7)

    def test_symbolicVarVar(self):
        """
        Test repeat variables for symbolic equations.

        Multiple equations are tested that verify that various combinations of repeat variable usage evaluate correctly.
        For each input, the property is evaluated at 20 evenly spaced points per independent variable within the valid
        range.
        """
        func = lambda x, y, z: x * x + y / x + z * x
        self.setEqnField("X * X + Y / X + Z * X")
        self.functionTest(func, 1)

        func = lambda x, y, z: math.tan(x * y) + math.cos(x * y) + math.exp(z * y)
        self.setEqnField("tan(X * Y) + cos(X * Y) + exp(Z * Y)")
        self.functionTest(func, 2)

    def test_symbolicScientific(self):
        """
        Test scientific notation for symbolic equations.

        Multiple equations are tested that verify that various combinations of both upper and lower case scientific
        notation evaluate correctly. For each input, the property is evaluated at 20 evenly spaced points per
        independent variable within the valid range.
        """
        # Test upper case E
        func = lambda x, y, z: 3e5 / x
        self.setEqnField("3E5 / X")
        self.functionTest(func, 1)

        func = lambda x, y, z: 1.23e-3 * x
        self.setEqnField("1.23E-3 * X")
        self.functionTest(func, 2)

        # Test lower case e
        func = lambda x, y, z: 3e5 / x
        self.setEqnField("3e5 / X")
        self.functionTest(func, 3)

        func = lambda x, y, z: 1.23e-3 * x
        self.setEqnField("1.23e-3 * X")
        self.functionTest(func, 4)

    def test_symbolicExamples(self):
        """Test a handful of representative equations from materials_database for symbolic equations."""
        # Hypothetical HT9 Yield Strength
        func = lambda x, y, z: 10**6 * (
            (-640 / (1 + math.exp(-0.018 * (x - 520))) + 580) + (-120 / (1 + math.exp(-0.0432 * (x - 120))) + 95)
        )
        self.setEqnField("10**6*((-640/(1+exp(-0.018*(X-520)))+ 580)+ (-120/(1+exp(-0.0432*(X-120)))+ 95))")
        self.functionTest(func, 1)

        # Sodium Density, from open literature
        func = (
            lambda x, y, z: 219.0 + 275.32 * (1 - (x + 273.15) / 2503.7) + 511.58 * (1 - (x + 273.15) / 2503.7) ** 0.5
        )
        self.setEqnField("219.0 + 275.32 * (1 - (X + 273.15) / 2503.7) + 511.58 * (1 - (X + 273.15) / 2503.7) ** 0.5")
        self.functionTest(func, 2)

        # B4C Modulus, multi-variable
        func = lambda x, y, z: (5.2e11 - 7.1e6 * x - 4.1e3 * x**2) * (y / (4.512 - 3.1 * y))
        self.setEqnField("(5.2E11 - 7.1E6 * X - 4.1E3 * X**2) * (Y / (4.512 - 3.1 * Y))")
        self.functionTest(func, 3)

    def test_symbolicBadparse(self):
        """Test incorrect expressions results in errors for symbolic equations."""
        # Not a math equation
        self.setEqnField("Not an equation")
        with self.assertRaises(ValueError):
            self.loadMaterial(num=1)

        # Unknown variable
        self.setEqnField("X + Y + W")
        with self.assertRaises(ValueError):
            self.loadMaterial(num=2)

        # Missing an operator
        self.setEqnField("X Y")
        with self.assertRaises(ValueError):
            self.loadMaterial(num=3)

        # Missing equation field
        del self.yaml["density"]["function"]["equation"]
        with self.assertRaises(KeyError):
            self.loadMaterial(num=4)

    def test_pickleSymbolicFunction(self):
        """Downstream usages might need to pickle a material. Ensure symbolic expression can be pickled."""
        self.setEqnField("X + Y")
        mat = self.loadMaterial()
        stream = pickle.dumps(mat)
        mat2 = pickle.loads(stream)

        self.assertEqual(mat.rho.getMinBound("X"), mat2.rho.getMinBound("X"))
        self.assertEqual(
            mat.rho.calc({"X": 0.0, "Y": 10, "Z": -10}),
            mat2.rho.calc({"X": 0.0, "Y": 10, "Z": -10}),
        )
        self.assertEqual(
            mat.rho.calc({"X": 300.0, "Y": 15, "Z": -10}),
            mat2.rho.calc({"X": 300.0, "Y": 15, "Z": -10}),
        )

    def test_numpyEvals(self):
        """Test that numpy floats and integers work in evaluations same as integers and floats."""
        self.setEqnField("X * 2.0")
        mat = self.loadMaterial()

        func = lambda x: x * 2

        self.assertAlmostEqual(mat.rho.calc(X=np.float64(10), Y=5.0, Z=-10.0), func(10))
        self.assertAlmostEqual(mat.rho.calc(X=np.int64(10), Y=5.0, Z=-10.0), func(10))

    def test_largeExponentials(self):
        """Test that exponentials don't overflow."""
        # If sympy is allowed to simplify this expression it will try to evaluate e^-1400 which will overflow. The
        # remainder of the values are chosen just to get a reasonable magnitude expression based on the min/max bounds
        # for X/Y.
        self.setEqnField("exp(-1400.0 + 2.6*(X*0.1+30*Y))")
        mat = self.loadMaterial()

        func = lambda x, y: math.exp(-1400 + 2.6 * (x * 0.1 + 30 * y))

        self.assertAlmostEqual(mat.rho.calc(X=300, Y=5.0, Z=-10.0), func(300, 5))

    def test_symbolicOutofbounds(self):
        """Test evaluation outside of bounds results in ValueError for symbolic equations."""
        mat = self.loadMaterial()
        prop = mat.rho

        mins = [prop.getMinBound(var) for var in ["X", "Y", "Z"]]
        maxs = [prop.getMaxBound(var) for var in ["X", "Y", "Z"]]

        for i in range(3):
            minsEdited = copy.copy(mins)
            maxsEdited = copy.copy(maxs)

            minsEdited[i] -= 0.1
            maxsEdited[i] += 0.1
            with self.assertRaises(ValueError):
                prop.calc({"X": minsEdited[0], "Y": minsEdited[1], "Z": minsEdited[2]})
            with self.assertRaises(ValueError):
                prop.calc({"X": maxsEdited[0], "Y": maxsEdited[1], "Z": maxsEdited[2]})
