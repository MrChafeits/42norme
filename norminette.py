#!/usr/bin/env python3

import argparse
import os
import re
import json
import threading
import uuid
import socket

import sys

import time

try:
    import pika

    if (
        pika.__version__ != "0.12.0"
        and pika.__version__ != "0.13.0"
        and pika.__version__ != "0.13.1"
    ):
        print(f"Found: pika=={pika.__version__}")
        print("If this version functions as expected, please send a pull request or\n"
            "create an issue to add it to the list of known compatible versions.")
except ModuleNotFoundError as ex:
    print(f"{ex}")
    print(
            "This python script requires pika and is known to be compatible with the\n"
            "following versions:\n"
            "\tpika==0.12.0\n"
            "\tpika==0.13.0\n"
            "\tpika==0.13.1\n"
    )
    print("\nInstall it by running:")
    print("\tpython3 -m pip install --user pika==0.12.0")
    exit(1)
except Exception as ex:
    print(f"Unexpected Error: {ex}")
    raise


class Sender:
    connection = None
    channel = None
    exchange = None
    reply_queue = None
    routing_key = "norminette"
    cb = None
    counter = 0
    corr_id = str(uuid.uuid4())

    def setup(self, cb):
        self.cb = cb
        self.connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                "norminette.42.fr", 5672, "/", pika.PlainCredentials("guest", "guest")
            )
        )
        self.channel = self.connection.channel()
        self.exchange = self.channel.exchange_declare(exchange=self.routing_key)
        self.reply_queue = self.channel.queue_declare(exclusive=True).method.queue
        self.channel.queue_bind(exchange=self.routing_key, queue=self.reply_queue)
        self.channel.basic_consume(self.consume, queue=self.reply_queue, no_ack=True)
        self.counter = 0

    def teardown(self):
        if self.channel is not None:
            self.channel.close()
        if self.connection is not None:
            self.connection.close()

    def publish(self, content):
        self.counter += 1
        self.channel.basic_publish(
            exchange="",
            routing_key=self.routing_key,
            body=content,
            properties=pika.BasicProperties(
                reply_to=self.reply_queue, correlation_id=self.corr_id
            ),
        )

    def consume(self, channel, method_frame, properties, body):
        self.counter -= 1
        self.cb(body.decode("utf-8"))

    def sync_if_needed(self, jobs=os.cpu_count()):
        if self.counter >= jobs:
            self.connection.process_data_events()

    def sync(self):
        while self.counter != 0:
            self.sync_if_needed(0)


class Norminette:
    files = None
    sender = None
    lock = None
    options = None
    stop = False

    def setup(self, options):
        self.options = options
        self.files = []
        self.lock = threading.Lock()
        self.sender = Sender()
        self.sender.setup(lambda payload: self.manage_result(json.loads(payload)))

    def teardown(self):
        # print("\r\x1b", end="")
        self.sender.teardown()

    def check(self):
        if self.options.version:
            self.version()
        else:
            if len(self.options.files_or_directories) > 0:
                self.scan_files(self.options.files_or_directories)
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

    def test_scan(self, path=None):
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
        print("\nRemote Norminette Rules:")
        self.sender.publish(json.dumps({"action": "help"}))

    def version(self):
        print(f"{sys.argv[0]}: 0.1.2 unofficial")
        print("Remote Norminette:", end=" ")
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


class Parser:
    def parse(self):
        parser = argparse.ArgumentParser(
            # usage="Usage: %(prog)s [options] [files_or_directories]",
            allow_abbrev=False
        )
        parser.add_argument(
            "--version", "-v", help="Print version", action="store_true"
        )
        parser.add_argument("--rules", "-R", help="Rules to disable", type=str)
        parser.add_argument("files_or_directories", nargs=argparse.REMAINDER)

        args = parser.parse_args()
        return args


if __name__ == "__main__":
    try:
        addr = socket.gethostbyname("vogsphere")
        n = Norminette()
        n.setup(Parser().parse())
        # n.test_scan(n.options.files_or_directories)
        n.check()
        n.teardown()
    except socket.gaierror:
        print("This script must be run while connected to a 42 LAN")
        exit(1)
    except Exception as ex:
        print(f"Unexpected exception: {ex}")
        raise
