#!/usr/bin/env python3

import argparse
import os
import re
import json
import threading

import sys

import time

from .sender import (
    Sender,
)
from .rules import (
    ruleList as norminette_rules,
)


class Norminette(object):
    """Norminette class.

    Norminette objects are the ones responsible for getting a list of
    files to check, running said checks and displaying the results.
    """

    files = None
    sender = None
    lock = None
    options = None
    stop = False

    def __init__(self, params=None):
        """Create a Norminette object with the given options."""
        if params is None:
            params = {}

    def setup(self, options):
        self.options = options
        self.files = []
        self.lock = threading.Lock()
        self.sender = Sender()
        self.sender.setup(lambda payload: self.manage_result(json.loads(payload)))

    def teardown(self):
        self.sender.teardown()

    def check(self):
        if self.options.version:
            self.version()
        else:
            if len(self.options.files_or_directories) > 0:
                self.scan_files(self.files, self.options.files_or_directories)
            else:
                self.scan_files([os.getcwd()])
            self.send_files(self.options)

        self.sender.sync()
        print()

    def scan_path(self, lst, path):
        for root, dirs, files in os.walk(path, followlinks=True):
            for ff in files:
                if ff[0] != "." and (ff.endswith(".c") or ff.endswith(".h")):
                    lst.append(os.path.join(root, ff))
            for ii, dd in enumerate(dirs):
                if dd[0] == "." and dd is not path:
                    del dirs[ii]

    def scan_files(self, lst, paths):
        for path in paths:
            if not os.path.isfile(path):
                self.scan_path(lst, path)
            else:
                lst.append(os.path.abspath(path))

    def _test_scan(self, path=None):
        if path is None or len(path) == 0:
            path = [os.getcwd()]
        l1 = []
        print(path)
        start = time.time()
        self.scan_files(l1, path)
        elapsed = time.time() - start
        print(f"        scan_files: {elapsed}")
        start = time.time()
        self.populate_recursive(path)
        elapsed = time.time() - start
        print(f"populate_recursive: {elapsed}")
        l1 = sorted(l1)
        self.files = sorted(self.files)
        print("len(l1):", len(l1), "len(self.files):", len(self.files))
        print(l1 == self.files)

    def populate_recursive(self, objects):
        for o in objects:
            if not os.path.isabs(o):
                o = os.path.abspath(o)
            if os.path.isdir(o):
                self.populate_recursive(self.list_dir(o))
            else:
                self.populate_file(o)

    def list_dir(self, dir):
        entries = os.listdir(dir)
        final = []
        for e in entries:
            if e[0] is not ".":
                final.append(os.path.join(dir, e))
        return final

    def get_rules(self):
        print("\nServer Rules:")
        self.sender.publish(json.dumps({"action": "help"}))

    def version(self):
        print("Client: 0.1.2 unofficial")
        print("Server:", end=" ")
        self.sender.publish(json.dumps({"action":"version"}))

    def file_description(self, file, rules):
        with open(file, "r") as f:
            return json.dumps({"filename": file, "content": f.read(), "rules": rules})

    def is_a_valid_file(self, f):
        return (
            f is not None
            and os.path.isfile(f)
            and re.match(".*\\.[ch]$", f) is not None
        )

    def populate_file(self, f):
        if not self.is_a_valid_file(f):
            # self.manage_result({"filename": f, "display": "Warning: Not a valid file"})
            return
        self.files.append(f)

    def send_files(self, options):
        disabled_rules = []
        if options.rules is not None:
            disabled_rules = options.rules.split(",")
        for f in self.files:
            self.sender.publish(self.file_description(f, disabled_rules))
            self.sender.sync_if_needed

    def cleanify_path(self, filename):
        return filename.replace(os.getcwd() + "/", "", 1)

    def manage_result(self, result):
        self.lock.acquire()
        # print(result)
        if "filename" in result:
            print(
                "\r\x1b[K\x1b[1m" + "Norme: "
                + self.cleanify_path(result["filename"] + "\x1b[m"),
                end="",
            )
        if "display" in result and result["display"] is not None:
            disp = result["display"]
            if "Unvalid" not in disp and "stop" not in result:
                print()
            # Pretty print rules perhaps?
            print(disp)
        self.lock.release()
        if "stop" in result and result["stop"] is True:
            self.stop = True
            # print()
            # exit(0)
            # return

def parse(overrideArguments=None):
    def _comma_sep_rules(string):
        value = string.split(',')
        for _,rule in enumerate(value):
            if rule not in norminette_rules:
                raise argparse.ArgumentTypeError(f"invalid rule: {rule!r}")
        return value

    # usage="Usage: %(prog)s [options] [files_or_directories]",
    kw = {
        'usage': '%prog [OPTIONS] [FILE...]',
        'conflict_handler': 'resolve',
        'allow_abbrev': False
    }

    general = argparse.ArgumentParser(**kw)

    general.add_argument(
        "-h", "--help",
        action='help',
        help='Print this help text and exit')
    general.add_argument(
        "-v","--version",
        action="store_true",
        help="Print program version and exit")
    general.add_argument(
        "-R","--rules",
        type=str,
        help="Rules to disable")
    general.add_argument("files_or_directories", nargs=argparse.REMAINDER)

    args = general.parse_args()
    return args


if __name__ == "__main__":
    n = Norminette()
    n.setup(Parser().parse())
    # n._test_scan(n.options.files_or_directories)
    n.check()
    n.teardown()
