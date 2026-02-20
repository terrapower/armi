#########
mat-props
#########

``armi.matProps`` is a Python library for defining materials for use in scientific modeling. The ``armi.matProps``
library takes in YAML files that allow a user to easily and flexibly define a material and its properties. In the lingo
of matProps, a "property" is a mathematical curve related to the material. Some common examples would be: the density of
a material as a function of temperature, the melting point as a function of pressure, or the coefficient of linear
expansion as a function of temperature and pressure. The ``matProps`` format also provides a place to explicitly list
references for each of these material properties: a crucial feature for any valid scientific calculation.

``armi.matProps`` is packaged inside the ARMI framework, but can also be installed and used entirely independently from
ARMI.


Installation
************

To install ``armi.matProps``, along with the rest of ARMI, via PIP:

.. code-block:: bash

    cd armi
    pip install -e .


You can install ``armi.matProps`` without the rest of ARMI. But there are various namespace concerns involved in that.
The best solution is just to (temporarily) wipe out ``armi/__init__.py``, and then install ``armi.mat-props`` with
the secondary ``pyproject.toml`` file provided:

.. code-block:: bash

    # temporarily wipe out armi/__init__.py
    cd armi
    mv __init__.py backup_init
    touch __init__.py

    # install armi.matProps without the rest of ARMI
    cd ../mat-props
    pip install -e .

    # revert the init file from the backup
    mv ../armi/backup_init ../armi/__init__.py


Testing
*******

If you install ARMI and run its unit tests, the matProps unit tests are run as well:

.. code-block:: bash

    cd armi
    pip install -e .[test]
    python -m pytest .


or, to run the ARMI tests faster in parllel:

.. code-block:: bash

    python -m pytest -n 4 .


Or you can run just the mat-props tests, independently from ARMI:

.. code-block:: bash

    cd armi/mat-props
    python -m pytest .


or, to run the mat-props tests faster in parllel:

.. code-block:: bash

    python -m pytest -n 4 .


Loading Data
************

In your Python code, you can load a full set of mat-props materials into memory with just one or two lines of code. You
just have to provide a path to a directory filled with correctly-formatted YAML files:

.. code-block:: python

    import armi.matProps

    pathToMaterialYAMLs = "path/to/materialDir/"
    armi.matProps.loadSafe(pathToMaterialYAMLs)


If you do not specify a directory for the YAML files, there is a default location in your virtual environment you can
store the data files (in a package named ``material_data``):

.. code-block:: python

    import armi.matProps

    armi.matProps.loadSafe()



Building a Wheel
****************

Because mat-props can be built and installed independently from ARMI, you may want to build a mat-props wheel. This is
easy to do, using standard PIP tools:

.. code-block:: bash

    # as above, temporarily clear the armi/__init__.py file
    cd armi
    mv __init__.py backup_init
    touch __init__.py

    # create the mat-props wheel
    cd ../mat-props
    mkdir dist
    pip wheel . -w dist/

    # rever the ARMI init file from the backup
    mv ../armi/backup_init ../armi/__init__.py

And now, in the directory ``mat-props/dist/`` you will have several wheels, one of which will be the one you want:
``mat_props-1.2.3-py3-none-any.whl``.
