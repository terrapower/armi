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

* Python 3.6+ (preferably 64-bit)
* Git
* MS Windows or Linux operating system

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

    $ python3 -m venv armi-venv

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
..  If you plan on running ARMI without modifying it, you may simply install it with pip, which will 
	automatically discover and install its dependencies::

   	(armi-venv) $ pip3 install armi

    That's it!

	If, on the other hand, you'd like to change the ARMI source code, you will want to 
	clone the ARMI source first and then install its dependencies.

Clone the ARMI source code from the git repository with::

   (armi-venv) $ git clone https://github.com/terrapower/armi
   
.. tip:: If you plan to contribute to ARMI (please do!), you may want to use
	SSH keys and use ``git clone git@github.com:terrapower/armi.git``.

Now install the ARMI dependencies::

    (armi-venv) $ cd armi
    (armi-venv) $ pip3 install -r requirements.txt

Then, install ARMI into your venv with::

	(armi-venv) $ python3 setup.py install 

.. tip:: If you don't want to install ARMI into your venv, you will need to add the ARMI source 
	location to your system's ``PYTHONPATH`` environment variable so that
	Python will be able to find the code when you import it from other directories.
	
	In Windows, click *Start* and type ``Edit Environmental Variable`` to adjust ``PYTHONPATH``. 
	In Linux, add ``export PYTHONPATH=/path/to/armi/source`` in a  user profile script (like ``.bashrc``).

To see if it worked, run the ARMI launcher script::

    (armi-venv) $ armi

If it worked, you should see the (classic) ARMI splash screen and no errors::

                       ---------------------------------------------------
                      |             _      ____     __  __    ___         |
                      |            / \    |  _ \   |  \/  |  |_ _|        |
                      |           / _ \   | |_) |  | |\/| |   | |         |
                      |          / ___ \  |  _ <   | |  | |   | |         |
                      |         /_/   \_\ |_| \_\  |_|  |_|  |___|        |
                      |         Advanced  Reactor  Modeling Interface     |
                       ---------------------------------------------------


If it works, congrats! So far so good.
