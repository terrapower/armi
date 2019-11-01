*******
Outputs
*******

ARMI output files are described in this section. Many outputs may be generated during an ARMI run. They fall into
various categories:

Framework outputs
    Files like the **stdout** and the **database** are produced in nearly all runs.

Interface outputs
    Certain plugins/interfaces produce intermediate output files

Physics kernel outputs
    If ARMI executes an external physics kernel during a run, its associated output files are often available in the
    working directory. These files are typically read by ARMI during the run, and relevant data is transferred onto the
    reactor model (and ends up in the ARMI **database**).

Together the output fully define the analyzed
ARMI case.

-----------

.. toctree::

   stdout
   database
