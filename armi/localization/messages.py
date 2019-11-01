# Copyright 2019 TerraPower, LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Some messages.
"""

from armi.localization import important


def general_DirectoryListing(fileNames):
    return "Directory listing:\n    {}".format("\n    ".join(fileNames))


@important
def latticePhysics_SkippingXsGen_BuChangedLessThanTolerance(tolerance):
    return "Skipping XS Generation this cycle because median block burnups changes less than {}%".format(
        tolerance
    )


@important
def general_submittedJob(job):
    return "Submitted {} ... {}".format(job, job.get_state())


@important
def general_waitingForJob(job):
    return "Waiting for {} to complete".format(job)
