************
Installation
************
This section will guide you through installing the ARMI Framework on your machine.

Prerequisites
-------------
These instructions target users with some software development knowledge. In
particular, we assume familiarity with `Python <https://www.python.org/>`_, 
`virtual environments <https://docs.python.org/3/tutorial/venv.html>`_, and `Git <https://git-scm.com/>`_. 

You must have the following before proceeding:

* `Python <https://www.python.org/downloads/>`_ version 3.6 or later (preferably 64-bit)

  .. admonition:: The right Python command

     Python 2 and Python 3 often co-exist on the same system. Whether the
     ``python`` command refers to Python 2 or 3 depends on operating system and
     configuration. Under some circumstances ``python3`` or ``pip3`` will need
     to be used in place of ``python`` or ``pip`` to target the correct
     version. You can verify your version by running ``python -VV``.  You can
     also refer to the Python executable with a full path.

You also likely need the following for interacting with the source code repository:

* `Git <https://git-scm.com/>`_

Preparing a Virtual Environment
-------------------------------
While not *technically* required, we highly recommend installing ARMI into a `virtual
environment <https://docs.python.org/3/library/venv.html>`_  to assist in dependency
management.  In short, virtual environments are a mechanism by which a Python user can
maintain separate sets of Python packages for various applications on the same machine.
This prevents dependencies from various tools conflicting with one another. ARMI has a lot
of requirements and may conflict with other libraries on your system unless you do this
step.

Start a terminal and navigate to the directory you'd like to install ARMI into. 
To create a new virtual environment, use a command like:: 

    $ python -m venv armi-venv

The result is a folder named ``armi-venv``, which contains a minimal set of Python
packages, and a set of scripts for activating and deactivating that environment.
To activate the environment, invoke the appropriate script. On Windows::

    $ armi-venv\Scripts\activate.bat

Or on Linux::

    $ source armi-venv/bin/activate
    
.. note:: You'll have to activate the venv every time you open a new command line. 
	Many people set up scripts to activate this automatically.
	
If you will be running ARMI in parallel over MPI, you must also install the ``mpi4py`` Python
library. On Linux, doing so will require some MPI development libraries 
(e.g. ``sudo apt install libopenmpi-dev``).

Getting the code
----------------
Choose one of the following two installation methods depending on your needs.

Option 1: Install as a library
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
If you plan on running ARMI without viewing or modifying source code, you may
install it with ``pip``, which will automatically discover and install the
dependencies. This is useful for quick evaluations or to use it as a dependency
in another project::

   	(armi-venv) $ pip install https://github.com/terrapower/armi/archive/master.zip

Option 2: Install as a repository (for developers)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
If you'd like to view or change the ARMI source code (common!), you need to
clone the ARMI source and then install its dependencies. Clone the ARMI source code from
the git repository with::

   (armi-venv) $ git clone https://github.com/terrapower/armi

.. tip:: If you plan to contribute to ARMI (please do!), you may want to use
	SSH keys and use ``git clone git@github.com:terrapower/armi.git``.

Now install the ARMI dependencies::

    (armi-venv) $ cd armi
    (armi-venv) $ pip install -r requirements.txt

Then, install ARMI into your venv with::

	(armi-venv) $ pip install -e .

.. tip:: If you don't want to install ARMI into your venv, you will need to add the ARMI source 
	location to your system's ``PYTHONPATH`` environment variable so that
	Python will be able to find the code when you import it from other directories.
	
	In Windows, click *Start* and type ``Edit Environmental Variable`` to adjust ``PYTHONPATH``. 
	In Linux, add ``export PYTHONPATH=/path/to/armi/source`` in a  user profile script (like ``.bashrc``).


Verifying installation
^^^^^^^^^^^^^^^^^^^^^^
Check the installation status by running::

    (armi-venv) $ armi

or, equivalently:: 
    
    (armi-venv) $ python -m armi

If it worked, you should see the ARMI splash screen and no errors::

                       ---------------------------------------------------
                      |             _      ____     __  __    ___         |
                      |            / \    |  _ \   |  \/  |  |_ _|        |
                      |           / _ \   | |_) |  | |\/| |   | |         |
                      |          / ___ \  |  _ <   | |  | |   | |         |
                      |         /_/   \_\ |_| \_\  |_|  |_|  |___|        |
                      |         Advanced  Reactor  Modeling Interface     |
                       ---------------------------------------------------


If it works, congrats! So far so good.


Optional Setup
--------------
This subsection provides setup for optional items.

GUI input
^^^^^^^^^
To use the :py:mod:`graphical core-map editor <armi.utils.gridEditor>` you will need to also install
`wxPython <https://wxpython.org/pages/downloads/index.html>`_. This is not installed
by default during armi installation because it can cause installation complexities on some platforms.
In many cases, a ``pip install`` should suffice::

    (armi-venv) $ pip install wxpython

.. warning:: On some platforms, ``pip`` may try to compile wxpython from 
    source which can take a long time and require additional dependencies.

GUI output
^^^^^^^^^^
ARMI can write VTK and XDMF output files which can be viewed in tools such as
`ParaView <https://www.paraview.org/>`_ and 
`VisIT <https://wci.llnl.gov/simulation/computer-codes/visit>`_. Download and install those
tools from their websites.

RIPL-3 Nuclide Decay Database
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The RIPL-3 decay files (``levels.zip``) can be downloaded from `<https://www-nds.iaea.org/RIPL-3/levels/>`_.

By default, nuclides within :py:mod:`armi.nucDirectory.nuclideBases` are initialized from 
a subset of the RIPL-3 database, which ships with ARMI. The base data set contains 2339 
nuclides and RIPL-3 decay data set increases this to 4379 nuclides. The RIPL-3 decay data 
files mainly add metastable nuclides and other exotic nuclides that could be important for 
detailed depletion/decay models or activation analyses.

Once the ``levels.zip`` file is downloaded and unzipped, an environment variable :envvar:`ARMI_RIPL_PATH` 
should be created and set to the directory containing the ``z*.dat`` files.

