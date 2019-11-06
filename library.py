# AtmelStart_PlatformIO library build script
# Author: Frank Leon Rose
# Copyright (c) 2019
#
# Given an .atstart configuration file downloaded from the web app at start.atmel.com,
# this library will download and correctly build the generated code as a simple
# dependenty library in PlatformIO.

import json
import requests
import yaml
from yaml import CLoader as Loader
import zipfile
import os
import os.path
import sys

input_filename = "atmel_start_config.atstart"
output_filename = "output.json"
DOWNLOAD_DIR = ".downloads"
PACKAGES_DIR = "packages"

def convert_config_yaml_to_json(input, output):
    def dictToArray(d, idKey):
        a = []
        for (key, value) in d.items():
            if idKey:
                value[idKey] = key
            a.append(value)
        return a

    def fixDefinition(a):
        for element in a:
            element["definition"] = {
              "identifier": element["definition"],
              "base": element["definition"]
            }

    def sort_config(config):
        config["middlewares"].sort(key=lambda x: x["identifier"])
        config["drivers"].sort(key=lambda x: x["identifier"])
        config["pads"].sort(key=lambda x: x["name"])

        # Force order of keys in configuration. Fails to accept configuration without this.
        sorted_config = {}
        for key in ['jsonForm', 'formatVersion', 'board', 'identifier', 'name', 'details', 'application', 'middlewares', 'drivers', 'pads']:
            sorted_config[key] = config[key]

        return sorted_config

    def load_yaml(input_filename):
        with open(input_filename, "r") as f:
            config = yaml.load(f, Loader=Loader)
        config["middlewares"] = dictToArray(config["middlewares"], "identifier")
        config["drivers"] = dictToArray(config["drivers"], "identifier")
        config["pads"] = dictToArray(config["pads"], None)
        config["jsonForm"] = "=1"
        config["formatVersion"] = 2
        config["identifier"] = ""
        fixDefinition(config["drivers"])

        return config

    def load_json(input_filename):
        with open(input_filename, "r") as f:
            return json.load(f)

    def dump(config, output_filename, pretty = False):
        with open(output_filename, "w") as f:
            indent = 2
            separators = (',', ': ')
            if not pretty:
                indent = None
                separators = (',', ':')
            json.dump(config, f, indent=indent, separators=separators, sort_keys=pretty)

    # json_file = load("atmel_start_config.json")
    config = load_yaml(input)
    config = sort_config(config)
    dump(config, output)

def hash_file(file):
    import hashlib
    m = hashlib.md5()
    with open(file, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            m.update(chunk)
    return m.hexdigest()

def download_package(config_file, download_dir, packages_dir):
    hash = hash_file(config_file)
    os.makedirs(download_dir, exist_ok=True)
    filename = os.path.join(download_dir, hash + '.zip')
    if os.path.isfile(filename):
        print('NOTE:', filename, 'already downloaded. Delete it and re-run if you want to re-download')
    else:
        print("Downloading", filename, "...")
        with open(config_file, 'r') as project_json:
            headers = {'content-type': 'text/plain'}
            r = requests.post('http://start.atmel.com/api/v1/generate/?format=atzip&compilers=[atmel_studio,make]&file_name_base=atmel_start_config', headers=headers, data=project_json)
        if not r.ok:
            # Double check that the JSON is minified. If it's not, you'll get a 404.
            print(r.text)
            sys.exit(1)
        with open(filename, 'wb') as out:
            out.write(r.content)

    package_dir = os.path.join(packages_dir, hash)
    if not os.path.isdir(package_dir):
        print("Unzipping ...")
        z = zipfile.ZipFile(filename)
        z.extractall(package_dir)

    return package_dir

convert_config_yaml_to_json(input_filename, output_filename)
package_dir = download_package(output_filename, DOWNLOAD_DIR, PACKAGES_DIR)

global_env = DefaultEnvironment()

Import('env')

def valid_source(p):
    return "armcc" not in p and "IAR" not in p and "RVDS" not in p

include_paths = []
source_paths = []
linker_script = None
for dirpath, dirnames, filenames in os.walk(package_dir):
    # if "portable" not in dirpath or "GCC" in dirpath: # Exclude 'portable' include_paths for compilers other than GCC
    if valid_source(dirpath):
        if any(".h" in fn for fn in filenames):
            include_paths.append(dirpath)
        if any(".c" in fn for fn in filenames):
            source_paths.append(dirpath)

    if "gcc" in dirpath:
        for fn in filenames:
            if "flash.ld" in fn:
                linker_script = os.path.realpath(os.path.join(dirpath, fn))

if linker_script is None:
    sys.stderr.write("Error: Failed to find linker script in downloaded package.\n")
    env.Exit(1)

global_env.Append(CPPPATH=[os.path.realpath(p) for p in include_paths])
env.Append(
    CPPPATH=[os.path.realpath(p) for p in include_paths]
)

def src_dir(*x):
    return os.path.realpath(os.path.join(*x))

sources = ["-<*>"]
sources.extend(["+<{}>".format(src_dir(sp, '*.c')) for sp in source_paths])
sources.append("-<{}>".format(src_dir(package_dir, 'main.c')))

env.Append(
    srcDir=package_dir,
    SRC_FILTER=sources
)

global_env.Replace(
    LDSCRIPT_PATH=linker_script)