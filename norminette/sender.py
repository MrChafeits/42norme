from os import os.cpu_count
from uuid import uuid4

known_compat_pika = ["0.12.0", "0.13.0", "0.13.1"]
try:
    import pika

    if (pika.__version__ not in known_compat_pika):
        print(f"Found: pika=={pika.__version__}")
        print("If this version functions as expected, please send a pull request or\n"
            "create an issue to add it to the list of known compatible versions.")
except ModuleNotFoundError as ex:
    print(f"{ex}")
    print("This python script requires pika and is known to be compatible with the following versions:\n")
    for ver in known_compat_pika:
        print(f"\tpika=={ver}")
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
    corr_id = str(uuid4())

    def setup(self, cb):
        self.cb = cb
        try:
            self.connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    "norminette.42.fr", 5672, "/", pika.PlainCredentials("guest", "guest")
                )
            )
        except pika.exceptions.ConnectionClosed as ex:
            print(f"{ex}")
            print(f"Ensure that you are connected to the 42 Student WiFi network")
            exit(2)
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

    def sync_if_needed(self, jobs=cpu_count()):
        if self.counter >= jobs:
            self.connection.process_data_events()

    def sync(self):
        while self.counter != 0:
            self.sync_if_needed(0)
