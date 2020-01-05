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


if __name__ == "__main__":
    n = Norminette()
    n.setup(Parser().parse())
    # n._test_scan(n.options.files_or_directories)
    n.check()
    n.teardown()
