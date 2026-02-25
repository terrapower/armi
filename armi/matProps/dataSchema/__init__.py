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
The dataSchema module contains tools for validating mat-props data files.

dataSchema module
=================
Below is listed each section in the local ``dataSchema.json`` file, which is used as the source of truth when validating
mat-props data files.

Sections in the dataSchema.json file
------------------------------------

Schema
^^^^^^
Links to the exact library version we are using to define this schema.


refDataSchema
^^^^^^^^^^^^^
Defines what a "reference" will look like. Since nearly everything in a mat-props data file can have a reference, this
is a generic type of schema that can be used elsewhere as "$ref": "referenceSchema". These are lists or arrays, an
ordered sequence. In the YAML format, a reference will look like this::

    - ref: Bibliographic citation in your favorite format.
      refType: open literature


tabDataSchema
^^^^^^^^^^^^^
A description of tabulated data in the mat-props data files. This will appear in multiple places in the JSON file as
"$ref": "tabulatedData". Tabulated data are listed in YAML as a sequence, and might look like the following example::

    tabulated data:
      - [ 25, 6.974E+08]
      - [ 50, 6.965E+08]
      - [100, 6.940E+08]
      - [150, 6.902E+08]
      - [200, 6.842E+08]
      - [250, 6.753E+08]

The example above is a 1D table. Each row has two items: the position and the value. Of course, for 2D tables that value
might be a list. Thus, a 2D table might look like this::

    tabulated data:
      - [null,   [   375.,    400.,    425.,    450.,    475.,    500.,    525.,    550.,    575.,    600.,    625.]]
      - [10.,    [487.e+6, 475.e+6, 459.e+6, 440.e+6, 419.e+6, 374.e+6, 322.e+6, 274.e+6, 231.e+6, 192.e+6, 159.e+6]]
      - [30.,    [487.e+6, 475.e+6, 459.e+6, 440.e+6, 404.e+6, 353.e+6, 301.e+6, 251.e+6, 213.e+6, 176.e+6, 145.e+6]]
      - [100.,   [487.e+6, 475.e+6, 459.e+6, 440.e+6, 385.e+6, 329.e+6, 278.e+6, 234.e+6, 194.e+6, 160.e+6, 130.e+6]]
      - [300.,   [487.e+6, 475.e+6, 459.e+6, 418.e+6, 361.e+6, 307.e+6, 259.e+6, 216.e+6, 179.e+6, 146.e+6, 117.e+6]]
      - [1000.,  [487.e+6, 475.e+6, 459.e+6, 396.e+6, 338.e+6, 285.e+6, 239.e+6, 198.e+6, 163.e+6, 132.e+6, 105.e+6]]
      - [3000.,  [487.e+6, 475.e+6, 436.e+6, 374.e+6, 317.e+6, 266.e+6, 222.e+6, 178.e+6, 149.e+6, 118.e+6,  94.e+6]]
      - [10000., [487.e+6, 475.e+6, 412.e+6, 350.e+6, 295.e+6, 247.e+6, 204.e+6, 166.e+6, 135.e+6, 106.e+6,  81.e+6]]

Notice the "null" value in the top-left of the table above. That is because the rows are number 10-10000 and the columns
are numbered 375-625. The null is there because it is not an index value in the rows or the columns.


file format
^^^^^^^^^^^
This communicates which version of the mat-props data format is being used, and is the first line in the YAML file.


material type
^^^^^^^^^^^^^
This is an enum of a small set of values describing the material.  Allowed values include: Fuel, Metal, Fluid, Ceramic,
ASME2015, ASME2017, and ASME2019. Though items may get added to that list over time.


composition
^^^^^^^^^^^
This describes the chemical make-up of the material. Other than the references, this is meant be a simple list of
elemental composition with two values: min and max percentages of the materials. For instance, an example steel-like
material might be::

    composition:
      C: [0.03, 0.03]
      Si: [0.4, 0.4]
      Ni: [10.0, 15.0]
      Cr: [16.0, 19.0]
      Fe: balance

Above we can see that Chromium (Cr) makes up between 16 and 19% of the total mass of the material. And we also see the
special keyword "balance" on Fe, which just says that Iron makes up whatever percentage of the material is left over
after the others. The keys above are limited to strings of length 1 or 2, and can only include letters.


material property
^^^^^^^^^^^^^^^^^
This is another generic tool, meant to be used throughout the schema with the keyword ``"$ref": "materialProperty"``.
This has the properties: tabulated data, references, and function. (The "tabulated data" and "references" are global,
defined above.)

* **function**: can be of any ``function type`` listed in the ``enum``. This enum lists the supported mathematical
  functions. It also has the properties ``min degrees C`` and ``max degrees C``, both of which are required numbers.

    * **allOf**: This is a long switch statement mapping each ``function type`` above to its number and type of inputs.
    * **constant**: always returns the same ``value``.
    * **polynomial**: the list of ``coefficients`` here represent the float coefficents of terms summed together with
      exponents from 0 to 9. This is a limitation if someone needs higher-order terms.
    * **hyperbolic**: a list of ``coefficients``. Each coefficient has a set of properties:
      "hyperbolic function" (string), "intercept" (number), "outer multiplier" (number), "inner denominator" (number),
      and "inner adder" (number).  Currently, mat-props only supports the hyperbolic tangent function.
    * **power law**: has one property: "coefficients". This has three required properties: "exponent"
      (number), "outer multiplier" (number), and "inner adder" (number).
    * **piecewise** (piecewiseFunction.py): a recursive description that has one property: "functions". Each "function"
      is mapped to "tabulated data".
    * **temperature dependent table** (tableFunction1D.py): has one required number, "rounding scheme".
    * **time and temperature dependent table** and "cycles and temperature dependent table" (tableFunction2D.py): both
      have two required properties: "interpolation scheme" (string), and "rounding scheme" (number). "interpolation
      scheme" can only be the values (strings): "log-lin," and "lin-lin".

* The last ``allOf`` simplifies the logic for ``constant`` functions. This conditional just removes the requirement that
constant functions take tabulated data.

The final block is a hard-coded list of all the material properties in mat-props (for instance, density). But you can
easily add more material properties to mat-props and if you do so you will need to amend this list before validation.


Example
-------
There is an example, ideal mat-props YAML file at: ``matProps/dataSchema/tests/inputs/example.yaml``.


Running Validation
------------------
This folder includes the python script ``dataSchemaValidator.py``. This is used to validate mat-props YAML files. This
script must be run in the same directory as the folder of YAML files. The tool is easy to run::

    python dataSchemaValidator.py example.yaml
    python dataSchemaValidator.py --dir inputs


Test Files
^^^^^^^^^^
There are a variety of files to test the JSON schema at: ``armi/matProps/dataValidator/tests/inputs/``. Some of these
have purposefully incorrect file formats, for testing purposes.
"""
