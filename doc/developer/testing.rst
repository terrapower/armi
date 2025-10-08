.. _armi-testing:

******************
ARMI Testing Tools
******************

ARMI has many useful tools to streamline tests in the plugins. Included here are some popular ones. If you are trying to write a new unit test, chances are something like it has been done before and you do not need to design it from scratch. Look around ARMI and other plugins for examples of tests. The ``armi.testing`` module is always a good place to start.


Testing with runLog
===================

Use Case: Test code that prints to stdout

While there are some other mocking examples in ARMI, none are as heavily used as ``mockRunLogs``. ``mockRunLogs.BufferLog()`` is used to capture the ``runLog`` output instead of printing it.

In `test_comparedb3.py <https://github.com/terrapower/armi/blob/49f357b2a92aaffaf883642f7b86fbe21b0e0272/armi/bookkeeping/db/tests/test_comparedb3.py>`_, there is a (simplified here) use case. A portion of the test for ``_diffSpecialData`` wants to confirm the below printout has happened, so it uses the ``getStdout()`` method to check that the expected printout exists.

Example of ``mockRunLogs``:

.. code-block:: python

    from armi.tests import mockRunLogs

    class TestCompareDB3(unittest.TestCase):
        # ...

        def test_diffSpecialData(self):
            dr = DiffResults(0.01)
            fileName = "test.txt"
            with OutputWriter(fileName) as out:
                with mockRunLogs.BufferLog() as mock:
                    #... skip for clarity: create refData & srcData
                    _diffSpecialData(refData, srcData, out, dr)
                    self.assertEqual(dr.nDiffs(), 0)
                    self.assertIn("Special formatting parameters for", mock.getStdout())

There are examples of this throughout ARMI. Search for ``BufferLog`` or ``getStdout`` in the code to find examples.


Self-Cleaning Directories
=========================

Use Case: Automatically cleans up tests that create files:

.. code-block:: python

    from armi.utils.directoryChangers import TemporaryDirectoryChanger

Two main uses of this class in testing:

1. Standalone test that calls code that creates something (`test_operators.py <https://github.com/terrapower/armi/blob/2bcb03689954ae39f3044f18a9a77c1fb7a0e63b/armi/operators/tests/test_operators.py#L237-L242>`_):

.. code-block:: python

     def test_snapshotRequest(self, fakeDirList, fakeCopy): 
         fakeDirList.return_value = ["mccAA.inp"] 
         with TemporaryDirectoryChanger(): 
             with mockRunLogs.BufferLog() as mock: 
                 self.o.snapshotRequest(0, 1) 
                 self.assertIn("ISOTXS-c0", mock.getStdout()) 

2. Setup and teardown of a testing class, where all/most of the tests create something (`test_comparedb3.py <https://github.com/terrapower/armi/blob/2bcb03689954ae39f3044f18a9a77c1fb7a0e63b/armi/bookkeeping/db/tests/test_comparedb3.py#L36-L52>`_):

.. code-block:: python

     class TestCompareDB3(unittest.TestCase): 
         """Tests for the compareDB3 module.""" 
      
         def setUp(self): 
             self.td = TemporaryDirectoryChanger() 
             self.td.__enter__() 
      
         def tearDown(self): 
             self.td.__exit__(None, None, None) 
      
         def test_outputWriter(self): 
             fileName = "test_outputWriter.txt" 
             with OutputWriter(fileName) as out: 
                 out.writeln("Rubber Baby Buggy Bumpers") 
      
             txt = open(fileName, "r").read() 
             self.assertIn("Rubber", txt) 

Note that sometimes it is necessary to give the temporary directory change object a non-default root path:

.. code-block:: python

    Include root argument
    THIS_DIR = os.path.dirname(__file__)
    # ...

    def test_something():
        with TemporaryDirectoryChanger(root=THIS_DIR): 
            # test something


Load a Test Reactor
===================

Use Case: You need a full reactor for a unit test

.. warning::
    This is computationally expensive, and historically over-used for unit tests. Consider whether mocking or BYO components (below) can be used instead.


To get the standard ARMI test reactor, import this:

.. code-block:: python

    from armi.reactor.tests.test_reactors import loadTestReactor

This function will return a reactor object. And it takes various input arguments to allow you to customize that reactor:

.. code-block:: python

     def loadTestReactor( 
         inputFilePath=TEST_ROOT, 
         customSettings=None, 
         inputFileName="armiRun.yaml", 
     ): 

So many interfaces and methods require an operator or a reactor, and ``loadTestReactor`` returns both. From there you can use the whole reactor or just grab a single ARMI object, like a `fuel block <https://github.com/terrapower/armi/blob/58b0e8198d2f8a217c1db84e97127adfe7e91c09/armi/reactor/tests/test_blocks.py#L3030-L3036>`_:

.. code-block:: python

     _o, r = loadTestReactor(
        os.path.join(TEST_ROOT, "smallestTestReactor"),
        inputFileName="armiRunSmallest.yaml",
    )

    # grab a pinned fuel block
    b = r.core.getFirstBlock(Flags.FUEL)

If you need a full reactor for a unit test, always try to start with the `smallestTestReactor.yaml` shown above first. Your tests will run faster if you pick the smallest possible reactor that meets your needs. Less is more.

Sidebar: Speed up Test Reactor Tests
------------------------------------
Maybe you do need an entire reactor for your unit test, but you don't need a very large one. In that case, ARMI comes with a few standard tools:

#. ``from armi.testing import reduceTestReactorRings`` - Reduce the size of the test reactor you are using.
#. ``from armi.tests import getEmptyCartesianReactor`` - Provides a test cartesian reactor with no assemblies or blocks inside.
#. ``from armi.tests import getEmptyHexReactor`` - Provides a test hex reactor with no assemblies or blocks inside.


Test Blocks and Assemblies
==========================

Use Case: Your unit test needs some ARMI objects, but not a full test reactor.

ARMI provides several helpful tools for generating simple blocks and assemblies for unit tests:

* ``from armi.reactor.tests.test_assemblies import buildTestAssemblies`` - Two hex blocks.
* ``from armi.reactor.tests.test_blocks import buildSimpleFuelBlock`` - A simple hex block containing fuel, clad, duct, and coolant.
* ``from armi.reactor.tests.test_blocks import loadTestBlock`` - An annular test block.

