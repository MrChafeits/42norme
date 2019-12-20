#!/usr/bin/env python3

import argparse
import os
import re
import json
import threading
import uuid
import socket

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

    def sync_if_needed(self, max=os.cpu_count()):
        if self.counter >= max:
            self.connection.process_data_events()

    def sync(self):
        while self.counter != 0:
            self.sync_if_needed(0)


class Norminette:
    files = None
    sender = None
    lock = None
    options = None

    def setup(self, options):
        self.options = options
        self.files = []
        self.lock = threading.Lock()
        self.sender = Sender()
        self.sender.setup(lambda payload: self.manage_result(json.loads(payload)))

    def teardown(self):
        print("\r\x1b", end="")
        self.sender.teardown()

    def check(self):
        if self.options.version:
            self.version()
        else:
            # print(self.options)
            if len(self.options.files_or_directories) is not 0:
                self.populate_recursive(self.options.files_or_directories)
            else:
                self.populate_recursive([os.getcwd()])
            self.send_files(self.options)

        self.sender.sync()
        print()

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

    def version(self):
        print("Local version:\n0.1.2 unofficial")
        print("Norminette help:")
        self.send_content(json.dumps({"action": "help"}))

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
            self.manage_result({"filename": f, "display": "Warning: Not a valid file"})
            return
        self.files.append(f)

    def send_files(self, options):
        disabled_rules = []
        if options.rules is not None:
            disabled_rules = options.rules.split(",")
        for f in self.files:
            self.send_file(f, disabled_rules)
            self.sender.sync_if_needed

    def send_file(self, f, rules):
        self.send_content(self.file_description(f, rules))

    def send_content(self, content):
        self.sender.publish(content)

    def cleanify_path(self, filename):
        return filename.replace(os.getcwd() + "/", "", 1)

    def manage_result(self, result):
        self.lock.acquire()
        if "filename" in result:
            print(
                "\r\x1b[K\x1b[;1mNorme: "
                + self.cleanify_path(result["filename"] + "\x1b[m"),
                end="",
            )
        if "display" in result and result["display"] is not None:
            res = result["display"]
            if "Unvalid" not in res:
                print()
            # Pretty print rules perhaps?
            print(res)
        self.lock.release()
        if "stop" in result and result["stop"] is True:
            # print()
            exit(0)


class Parser:
    def parse(self):
        parser = argparse.ArgumentParser(
            usage="Usage: %(prog)s [options] [files_or_directories]", allow_abbrev=False
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
        n.check()
        n.teardown()
    except socket.gaierror:
        print("This script must be run while connected to a 42 LAN")
        exit(1)
    except Exception as ex:
        print(f"Unexpected exception: {ex}")
        raise
