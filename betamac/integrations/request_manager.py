from time import sleep, time

from ..config import Config


class RequestManager:
    def __init__(self):
        self.next_valid_request_time: float = 0

    # returns False if wait time is too long and skipping search is preferable,
    # unless force=True, in which case will always wait.
    # returns True if waited
    # waits until next valid request time, or throws if wait time is too long
    def wait_until_valid_request_time_or_throw(
        self,
        max_wait_time: float = Config.REQUEST_TIMEOUT_S,
    ) -> bool:
        wait_time = self.next_valid_request_time - time()

        if wait_time > max_wait_time:
            raise RequestWaitTooLongError(wait_time, max_wait_time)

        if wait_time > 0:
            print(f"Hit wait time, waiting {wait_time}")
            sleep(wait_time)

        self.next_valid_request_time = time() + Config.REQUEST_DELAY_S
        return True

    def add_delay_to_next_request(self, delay_time_sec: int):
        self.next_valid_request_time = time() + delay_time_sec


class RequestWaitTooLongError(Exception):
    """Raised when a 429 response asks us to wait longer than we're willing to."""

    def __init__(self, retry_after: float, max_wait: float):
        self.retry_after = retry_after
        self.max_wait = max_wait
        msg = f"Requested wait: {retry_after:.1f}s wait (limit {max_wait:.1f}s)"
        super().__init__(msg)


jev_request_manager = RequestManager()

analysis_model_request_manager = RequestManager()
