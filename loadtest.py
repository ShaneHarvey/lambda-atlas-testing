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


LAMBDA_FUNCTION_URL: str = os.environ["LAMBDA_FUNCTION_URL"]
LOAD_TEST_TIMEOUT: int = 60 * 5
# M30 repl: 70 triggers timeouts (with streaming SDAM enabled)
# M30 repl: 900-1400 triggers election (with streaming SDAM enabled)
# M30 repl: 3000 succeeds without any timeouts (with streaming SDAM disabled)
# M60 repl: handles 3000 without any timeouts (with streaming SDAM enabled)
# M140 repl: handles 3000 without any timeouts (with streaming SDAM enabled or disabled)
CONCURRENT_REQUESTS_LIMIT: int = 3000

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
    def __init__(self, load_incrementally, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stopped = False
        self.load_incrementally = load_incrementally
        self.step = 50
        if load_incrementally:
            self.concurrent_reqs = 50
        else:
            self.concurrent_reqs = CONCURRENT_REQUESTS_LIMIT
        self.daemon = True  # Set to avoid blocking on exit.

    def stop(self):
        self.stopped = True

    def run(self) -> None:
        while not self.stopped:
            cmd = f"hey -n {self.concurrent_reqs*2} -c {self.concurrent_reqs} {LAMBDA_FUNCTION_URL}"
            logger.info(f"running: {cmd}")
            os.system(cmd)
            time.sleep(1)
            self.concurrent_reqs = min(self.concurrent_reqs + self.step, CONCURRENT_REQUESTS_LIMIT)


def main() -> None:
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
    primary = client.primary
    if primary is None:
        # Sharded cluster
        logger.error("sharded cluster not supported yet")
        exit(1)

    event = None
    load_incrementally = True
    start = time.time()
    for _ in range(2):
        worker = Worker(load_incrementally)
        worker.start()
        try:
            initial_sd, event = listener.events.get(timeout=LOAD_TEST_TIMEOUT)
            # Allow the workload to run for a few more seconds to increase the chance it triggers an election.
            time.sleep(15)
            break
        except queue.Empty:
            logger.error(
                f"load test failed to generate a server state change after {LOAD_TEST_TIMEOUT} seconds"
            )
        finally:
            logger.info("stopping workload thread...")
            worker.stop()
            worker.join()
        load_incrementally = False
        logger.info("pausing the workload for 1 minute...")
        time.sleep(60)

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
