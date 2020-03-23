Documenting ARMI
================
ARMI uses the `Sphinx <https://www.sphinx-doc.org/en/master/>`_ documentation system to compile the 
web-based documentation from in-code docstrings and hand-created 
`ReStructedText files <https://www.sphinx-doc.org/en/master/usage/restructuredtext/basics.html>`_.
This provides several benefits:
 
* We can revise and track the documentation in lock-step with the code itself, in the same 
  source code repository
* We can make use of hyperlinked cross-references that stay up to date as the code is expanded 
  or refactored.
* We can run specific code tests during documentation building to ensure the documentation 
  examples remain valid
* We can auto-generate class diagrams based on the latest status of the code

We use some special Sphinx plugins that run the tutorial jupyter notebooks during documentation
build with the most up-to-date code. 

Building the documentation
--------------------------
To build the ARMI documentation, go to the ``doc`` folder and run ``make html``. This will invoke
Sphinx and generate a series of html files in the ``_build/html`` folder. Open up ``index.html`` 
to see the documentation from there. A copy of the documentation is hosted online at 
https://terrapower.github.io/armi/.

Using Jupyter notebooks
-----------------------
For interactive tutorials, it's convenient to build actual Jupyter notebooks and 
commit them to the documentation to be rendered by Sphinx using the nbsphinx plugin.
When this is done, notebooks without any output should be committed to the repository
so that Sphinx actually executes the notebooks with the up-to-date code when the 
documentation is built. To do this, you can clean the output with::

	jupyter nbconvert --ClearOutputPreprocessor.enabled=True --inplace mynotebook.ipynb

This should clear the output and overwrite the file. If this doesn't work, you can clear
all output cells in the notebook web interface itself before committing the file.

Documentation for ARMI plugins
------------------------------
The following subsections apply to documentation for ARMI plugins.

Linking to ARMI documentation from plugins
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
ARMI plugin documentation can feature rich hyperlinks to the ARMI API documentation 
with the help of the
`intersphinx Sphinx plugin <http://www.sphinx-doc.org/en/master/usage/extensions/intersphinx.html>`_.
The ARMI plugin documentation config file should add ``"sphinx.ext.intersphinx",`` to
its active Sphinx plugin list, and change the default config to read::

    intersphinx_mapping = {
        "python": ("https://docs.python.org/3", None),
        "armi": ("https://terrapower.github.io/armi/", None),
    }

Now you can link to the ARMI documentation with links like::

    :doc:`armi:developer/documenting`
    :py:mod:`armi.physics.executers`


Automatically building apidocs of namespace packages
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Activating the ``"sphinxcontrib.apidoc",`` 
`Sphinx plugin <https://github.com/sphinx-contrib/apidoc>`_
enables plugin API documentation to be built with the standard ``make html`` Sphinx workflow. If 
your ARMI plugin is a namespace package, the following extra config is required::

    apidoc_extra_args = ["--implicit-namespaces"]
