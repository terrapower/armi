Accessing Entry Points 
======================


Reports Entry Point
-------------------

There are two ways to access the reports entry point in ARMI.

The first way is through a yaml settings file.
Here, the call is as follows

``(venv) C:\Users\username\codes> tparmi report anl-afci-177.yaml``

It is also possible to call this on an h5 file,


``(venv) C:\Users\username\codes> tparmi report -h5db refTestBase.h5``

.. note:: When working with a h5 file, -h5db must be included

Once these are called, a report is generated and outputed as an html file in reportsOutputFiles.
