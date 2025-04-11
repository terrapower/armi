**************
Profiling ARMI
**************

Python in slow, so it's important to profile code to keep it running reasonably quickly. Using the basic `Python profiler <https://docs.python.org/3/library/profile.html>`_ is the best way to get started. Once you have a ``.stats`` file, however, we highly recommend using a visualizer.

The profiler visualizer `gprof2dot <http://code.google.com/p/jrfonseca/wiki/Gprof2Dot#Windows_users>`_ is an invaluable tool for taking a look at the profiler traces. You have to install graphvis also, which contains the ``dot`` program.

The basic commands to run are::

    python -m gprof2dot -f pstats <mystatsfile>.stats | dot -Tpng -o <mydesiredimagename>.png

This produces images like this:

.. figure:: /.static/buildMacros.png
    :align: center

    An example of the profiler output rendered to a png.
