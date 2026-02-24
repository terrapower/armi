# Copyright 2026 TerraPower, LLC
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

"""Script to validate data format using schema."""

import json
import os
import pathlib

import jsonschema
from ruamel.yaml import YAML


def keysToString(d):
    """Used to change numeric keys in YAML, to strings, because JSON cannot parse numbers as keys."""
    if isinstance(d, dict):
        newDict = {str(key): keysToString(value) for key, value in d.items()}
    elif isinstance(d, list):
        newDict = [keysToString(value) for value in d]
    else:
        newDict = d

    return newDict


def loadSchema():
    """This function loads the schema for validation."""
    schemaPath = os.path.realpath(os.path.join(os.path.dirname(os.path.realpath(__file__)), "dataSchema.json"))
    with open(schemaPath, encoding="utf-8") as jsonFile:
        return json.load(jsonFile)


def validateFile(file_name):
    """This function validates a single YAML given a file after --file."""
    yaml = YAML()
    schema = loadSchema()
    yamlData = yaml.load(pathlib.Path(file_name))
    yamlData = keysToString(yamlData)
    jsonschema.validate(yamlData, schema, format_checker=jsonschema.FormatChecker)


def validateDir(dir_name):
    """
    Validate a folder of YAMLs within dataShema.

    It combines the path to data_schema with the folder provided, then loops through the YAMLs in the folder.
    """
    fileList = os.listdir(os.path.join(os.getcwd(), dir_name))
    directoryName = os.path.join(os.getcwd(), dir_name)
    for file in fileList:
        validateFile(os.path.join(directoryName, file))
