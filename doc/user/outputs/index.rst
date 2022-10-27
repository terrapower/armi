*******
Outputs
*******

ARMI output files are described in this section. Many outputs may be generated during an ARMI run. They fall into
various categories:

Framework outputs
    Files like the **stdout** and the **database** are produced in nearly all runs.

Interface outputs
    Certain plugins/interfaces produce intermediate output files.

Physics kernel outputs
    If ARMI executes an external physics kernel during a run, its associated output files are often available in the
    working directory. These files are typically read by ARMI during the run, and relevant data is transferred onto the
    reactor model (and ends up in the ARMI **database**). The files are stored in folders organized by cycle and time 
    step number (e.g., c2n1 for cycle 2, step 1). Within each cXnY folder, files are stored in folders organized by the 
    label or name of the Executer that uses them.

Together the output fully define the analyzed
ARMI case.

-----------

.. toctree::

   stdout
   database
