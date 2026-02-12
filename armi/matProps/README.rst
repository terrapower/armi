########
MatProps
########

**MatProps** is a Python library for defining materials for use in scientific modeling. The MatProps library takes in
YAML-formatted files that define various properties of materials, like density. MatProps produces custom Material
objects from the YAML data.

**MatProps** is packaged inside the ARMI Framework, but can also be installed and used entirely independently from ARMI.


Installation
************

To install **MatProps**, along with ARMI, via PIP:

.. code-block:: bash

    cd armi
    pip install -e .


To install **MatProps**, without ARMI, via PIP:

.. code-block:: bash

    cd armi/armi/matProps
    pip install -e .


Testing
*******

If you install ARMI and run its unit tests, the matProps unit tests are run as well:

.. code-block:: bash

    cd armi
    pip install -e .[test]
    python -m pytest .


or, to run the tests faster in parllel:

.. code-block:: bash

    python -m pytest -n 4 .


Or you can run just the matProps tests, independently from ARMI:

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
