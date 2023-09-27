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
CONCURRENT_REQUESTS: int = 1000


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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stopped = False
        self.daemon = True  # Set to avoid blocking on exit.

    def stop(self):
        self.stopped = True

    def run(self) -> None:
        while not self.stopped:
            cmd = f"hey -n {CONCURRENT_REQUESTS*2} -c {CONCURRENT_REQUESTS} {LAMBDA_FUNCTION_URL}"
            logger.info(f"running: {cmd}")
            os.system(cmd)
            time.sleep(1)


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
    start = time.time()
    while event is None:
        worker = Worker()
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
