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
LOAD_TEST_TIMEOUT: int = 60 * 10


class ServerStateChangeListener(ServerLogger):
    def __init__(self):
        self.initial_primary = None
        self.events = queue.Queue()

    def opened(self, event: "ServerOpeningEvent") -> None:
        super().opened(event)

    def description_changed(self, event: "ServerDescriptionChangedEvent") -> None:
        super().description_changed(event)
        # Replica set primary changed.
        # TODO: use topologyVersion?
        if (
            self.initial_primary is not None
            and event.new_description.is_writable
            and event.server_address != self.initial_primary
        ):
            self.events.put(event)

    def closed(self, event: "ServerClosedEvent") -> None:
        super().closed(event)


class Worker(threading.Thread):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stopped = False

    def stop(self):
        self.stopped = True

    def run(self) -> None:
        while not self.stopped:
            cmd = f"hey -n 3000 -c 1000 {LAMBDA_FUNCTION_URL}"
            logger.info(f"running: {cmd}")
            os.system(cmd)


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
    listener.initial_primary = primary

    start = time.time()
    worker = Worker()
    worker.start()
    try:
        event: ServerDescriptionChangedEvent = listener.events.get(timeout=LOAD_TEST_TIMEOUT)
    except queue.Empty:
        logger.error(
            f"load test failed to generate a server state change after {LOAD_TEST_TIMEOUT} seconds"
        )
        return
    finally:
        worker.stop()
        worker.join()

    duration = time.time() - start
    end_td = client.topology_description
    logger.info(f"load test caused a server state change after {duration} seconds: {event}")
    logger.info(
        f"starting topology description:\n{start_td}\nending topology description:\n{end_td}"
    )


if __name__ == "__main__":
    main()
