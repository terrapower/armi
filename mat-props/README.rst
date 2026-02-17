#########
mat-props
#########

TODO: This is no longer accurate. We are back to "armi.matProps"

**mat-props** is a Python library for defining materials for use in scientific modeling. The mat-props library takes in
YAML-formatted files that define various properties of materials, like density. mat-props produces custom Material
objects from the YAML data.

**mat-props** is packaged inside the ARMI Framework, but can also be installed and used entirely independently from ARMI.


Installation
************

To install **mat-props**, along with ARMI, via PIP:

.. code-block:: bash

    cd armi
    pip install -e .


To install **mat-props**, without ARMI, via PIP:

.. code-block:: bash

    cd mat-props
    pip install -e .


Testing
*******

If you install ARMI and run its unit tests, the mat-props unit tests are run as well:

.. code-block:: bash

    cd armi
    pip install -e .[test]
    python -m pytest .


or, to run the tests faster in parllel:

.. code-block:: bash

    python -m pytest -n 4 .


Or you can run just the mat-props tests, independently from ARMI:

.. code-block:: bash

    cd armi/armi/matProps
    pip install -e .[test]
    python -m pytest .


or, to run the tests faster in parllel:

.. code-block:: bash

    python -m pytest -n 4 .


Loading Data
************

In your Python code, you can load a full set of mat-props materials into memory with just one or two lines of code. You just have to provide a path to a directory filled with correctly-formatted YAML files:

.. code-block:: python

    import armi.matProps

    pathToMaterialYAMLs = "path/to/materialDir/"
    armi.matProps.loadSafe(pathToMaterialYAMLs)


If you do not specify a directory for the YAML files, there is a default location in your virtual environment you can
store the data files (in a package named `material_data`):

.. code-block:: python

    import armi.matProps

    armi.matProps.loadSafe()



Building a Wheel
****************

Because mat-props can be built and installed independently from ARMI, you may want to build a mat-props wheel. This is
easy to do, using standard PIP tools:

.. code-block:: bash

    cd mat-props

    mkdir dist
    pip wheel . -w dist/

And now, in the directory `mat-props/dist/` you will have several wheels, but one of them will be the one you want:
`mat_props-1.2.3-py3-none-any.whl`.
