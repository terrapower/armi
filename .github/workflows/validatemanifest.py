"""
Validating the MANIFEST.in

Currently, the only validation we do of the MANIFEST.in file is to make sure
that we are trying to include files that don't exist.
"""

import os


# CONSTANTS
INCLUDE_STR = "include "
MANIFEST_PATH = "MANIFEST.in"


def main():
    # loop through each line in the manifest file and find all the file paths
    errors = []
    lines = open(MANIFEST_PATH, "r", encoding="utf-8")
    for i, line in enumerate(lines):
        # if this is anything but an include line, move on
        if not line.startswith(INCLUDE_STR):
            continue

        # make sure the file exists
        path = line.strip()[len(INCLUDE_STR) :]
        if not os.path.exists(path):
            errors.append((i, path))

    # If there were any missing files, raise an Error.
    if errors:
        for (i, line) in errors:
            print("Nonexistant file on line {}: {}".format(i, line))
        raise ValueError("MANIFEST file is incorrect: includes non-existant files.")


if __name__ == "__main__":
    main()
