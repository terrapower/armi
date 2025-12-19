SCR for ARMI 0.6.3
==================

This is a listing of all the Software Change Request (SCR) changes in the ARMI repository, as part of the current release.

Below, this SCR is organized into the individual changes that comprise the net SCR for this release. Each SCR below explicitly lists its impact on ARMI requirements, if any. It is also important to note ARMI and all its requirements are tested entirely by the automated testing that happens during the ARMI build. None of the SCRs below will be allowed to happen if any single test fails, so it can be guaranteed that all SCRs below have fully passed all testing.


SCR Listing
-----------

The following lists display all the SCRs in this release of the ARMI framework.


.. exec::
   import os
   from automateScr import buildScrListing

   thisPrNum = int(os.environ.get('PR_NUMBER', -1) or -1)
   return buildScrListing(thisPrNum, "95d94a4d")
