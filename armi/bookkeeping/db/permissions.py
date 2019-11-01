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


class Permissions:
    """Mappings to HDF5 permissions flags"""

    READ_ONLY_FME = "r"  # File Must Exist
    READ_WRITE_FME = "r+"  # File Must Exist
    CREATE_FILE_TIE = "w"  # Truncate If Exists
    CREATE_FILE_FIE = "w-"  # Fail If Exists
    CREATE_FILE_FIE2 = "x"  # Fail If Exists, Alternate option
    READ_WRITE_CREATE = "a"

    DEFAULT = READ_WRITE_CREATE

    # Strictly reading, not writing or creating a file if it doesn't exist
    read = {READ_ONLY_FME, READ_WRITE_FME}

    write = {
        READ_WRITE_FME,
        CREATE_FILE_TIE,
        CREATE_FILE_FIE,
        CREATE_FILE_FIE2,
        READ_WRITE_CREATE,
    }

    create = {CREATE_FILE_TIE, CREATE_FILE_FIE, CREATE_FILE_FIE2, READ_WRITE_CREATE}

    all = {
        READ_ONLY_FME,
        READ_WRITE_FME,
        CREATE_FILE_TIE,
        CREATE_FILE_FIE,
        CREATE_FILE_FIE2,
        READ_WRITE_CREATE,
    }
