#########
mat-props
#########

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

    cd armi/armi/matProps
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

TODO:

.. code-block:: python

    import matProps

    pathToMaterialYAMLs = "xyz"
    matProps.loadSafe(pathToMaterialYAMLs)


TODO default path:

.. code-block:: python

    import matProps

    matProps.loadSafe()


Building a Wheel
****************

Because mat-props can be built and installed independently from ARMI, you may want to build a mat-props wheel. This is
easy to do, using standard PIP tools:

.. code-block:: bash

    TODO: We need to add some stuff to the pyproject.toml here.


TODO: Ensure the mat-props API shows up in the API docs, that will be needed for sphinx-needs later.
