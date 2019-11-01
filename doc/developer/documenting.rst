Documenting ARMI
================


Using Jupyter notebooks
-----------------------
For interactive tutorials, it's convenient to build actual Jupyter notebooks and 
commit them to the documentation to be rendered by Sphinx using the nbsphinx plugin.
When this is done, notebooks without any output should be committed to the repository
so that Sphinx actually executes the notebooks with the up-to-date code when the 
documentation is built. To do this, you can clean the output with::

	jupyter-nbconvert --clear-output tutorial.ipynb

This should clear the output and overwrite the file. If this doesn't work, you can clear
all output cells in the notebook web interface itself before committing the file.