import argparse
import logging
import os
import queue
import threading
import time

from pymongo import MongoClient
from pymongo.event_loggers import ServerLogger
from pymongo.monitoring import ServerClosedEvent, ServerDescriptionChangedEvent, ServerOpeningEvent

# Enable logs in this format:
# 2020-06-08 23:49:35,982 DEBUG ocsp_support Peer did not staple an OCSP response
FORMAT = "%(asctime)s %(levelname)s %(module)s %(message)s"
logging.basicConfig(format=FORMAT, level=logging.INFO)
logger = logging.getLogger()


LAMBDA_FUNCTION_URL: str = os.environ.get("LAMBDA_FUNCTION_URL")
LOAD_TEST_DURATION: int = 60 * 5
# M30 repl: 70 triggers timeouts (with streaming SDAM enabled)
# M30 repl: 900-1400 triggers election (with streaming SDAM enabled)
# M30 repl: 3000 succeeds without any timeouts (with streaming SDAM disabled)
# M60 repl: handles 3000 without any timeouts (with streaming SDAM enabled)
# M140 repl: handles 3000 without any timeouts (with streaming SDAM enabled or disabled)
CONCURRENT_REQUESTS_LIMIT: int = 1000

# Session build up on unclosed clients?


# *IMPORTANT*
# M30: Perf falls off of the 3 sec default timeout when creating ~70 MongoClient concurrently
# repro: func that creates/closes new client on each call:
# hey -n 120 -c 60 https://zvzdr2cegmj7ags34g7uame4pa0mnfcg.lambda-url.us-east-1.on.aws/
# Status code distribution:
#  [200] 120 responses
# hey -n 140 -c 70 https://zvzdr2cegmj7ags34g7uame4pa0mnfcg.lambda-url.us-east-1.on.aws/
# Status code distribution:
#  [200] 82 responses
#  [502] 58 responses

# Does this mean we can't jump more than 60~ instances? Load incrementally 60, 120, 180, etc...?


class ServerStateChangeListener(ServerLogger):
    def __init__(self):
        self.versions = {}
        self.events = queue.Queue()

    def opened(self, event: "ServerOpeningEvent") -> None:
        super().opened(event)

    def description_changed(self, event: "ServerDescriptionChangedEvent") -> None:
        super().description_changed(event)
        # Use topologyVersion to detect state changes (Requires MongoDB 4.4+).
        version = event.new_description.topology_version
        if version is not None:
            initial_sd = self.versions.setdefault(event.server_address, event.new_description)
            if version != initial_sd.topology_version:
                self.events.put((initial_sd, event))

    def closed(self, event: "ServerClosedEvent") -> None:
        super().closed(event)


class Worker(threading.Thread):
    def __init__(self, increment, concurrency, url, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stopped = False
        self.increment = increment
        self.limit = concurrency
        self.url = url
        if increment >= 0:
            self.concurrency = 0
        else:
            self.concurrency = concurrency
        self.daemon = True  # Set to avoid blocking on exit.

    def stop(self):
        self.stopped = True

    def run(self) -> None:
        while not self.stopped:
            self.concurrency = min(self.concurrency + self.increment, self.limit)
            cmd = f"hey -n {self.concurrency*2} -c {self.concurrency} {self.url}"
            logger.info(f"running: {cmd}")
            os.system(cmd)
            # Sleep briefly to allow this program to be killed with Ctrl+C.
            time.sleep(0.1)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="Lambda load test",
        description="Generates load to a Lambda function URL until a server state change is detected",
    )
    parser.add_argument(
        "-u",
        "--url",
        default=LAMBDA_FUNCTION_URL,
        help="the Lambda function URL, defaults to $LAMBDA_FUNCTION_URL",
    )
    parser.add_argument(
        "-d",
        "--duration",
        type=int,
        default=LOAD_TEST_DURATION,
        help=f"duration to run the load test, defaults to {LOAD_TEST_DURATION} seconds",
    )
    parser.add_argument(
        "-c",
        "--concurrency",
        type=int,
        default=CONCURRENT_REQUESTS_LIMIT,
        help=f"number of requests to run concurrently, defaults to {CONCURRENT_REQUESTS_LIMIT}",
    )
    parser.add_argument(
        "-i",
        "--increment",
        type=int,
        default=CONCURRENT_REQUESTS_LIMIT,
        help=(
            f"Increase the load incrementally until it reaches the concurrency limit, "
            f"defaults to {CONCURRENT_REQUESTS_LIMIT}"
        ),
    )
    args = parser.parse_args()
    if not args.url:
        print("ERROR: --url <URL> argument or $LAMBDA_FUNCTION_URL env var is required")
        exit(1)
    listener = ServerStateChangeListener()
    client: MongoClient[dict] = MongoClient(
        os.getenv("MONGODB_URI"), serverSelectionTimeoutMS=10000, event_listeners=[listener]
    )
    try:
        client.admin.command("ping")
    except Exception:
        logger.exception(
            f"failed to connect to $MONGODB_URI. topology_description:{client.topology_description}"
        )
        exit(1)

    start_td = client.topology_description
    logger.info(f"initial topology description: {start_td}")
    event = None
    increment = args.increment
    start = time.time()
    for i in range(2):
        if i != 0:
            # Disable incremental load on the second run.
            increment = args.concurrency
            logger.info("pausing the workload for 1 minute...")
            time.sleep(60)
        worker = Worker(increment, args.concurrency, args.url)
        worker.start()
        try:
            initial_sd, event = listener.events.get(timeout=args.duration)
            # Allow the workload to run for a few more seconds to increase the chance it triggers an election.
            time.sleep(15)
            break
        except queue.Empty:
            logger.error(
                f"load test failed to generate a server state change after {args.duration} seconds"
            )
            initial_sd, event = None, None
        finally:
            logger.info("stopping workload thread...")
            worker.stop()
            worker.join()

    if event is None:
        exit(1)
    duration = time.time() - start
    end_td = client.topology_description
    logger.info(
        f"load test caused a server state change after {duration} seconds: {initial_sd} changed event {event}"
    )
    logger.info(
        f"starting topology description:\n{start_td}\nending topology description:\n{end_td}"
    )


if __name__ == "__main__":
    main()
