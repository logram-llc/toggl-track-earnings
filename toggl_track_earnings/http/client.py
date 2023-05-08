from backoff import expo as EXPO
from backoff import on_exception as backoff_on_exception
from backoff import on_predicate as backoff_on_predicate
from ratelimit import RateLimitException, limits
from requests import RequestException, Session


def _give_up_on_server_errors(e: Exception) -> bool:
    if isinstance(e, RequestException):
        return e.response is not None and 400 <= e.response.status_code < 500

    return True


class HttpClient:
    def __init__(self, user_agent: str, timeout: int = 10):
        self.session = Session()
        self.default_timeout = timeout

        self.session.headers.update({"User-Agent": user_agent})

    @backoff_on_exception(
        EXPO,
        RequestException,
        max_tries=6,
        # Giveup on server errors
        giveup=_give_up_on_server_errors,
    )
    @backoff_on_exception(
        EXPO,
        RateLimitException,
        max_tries=24,
    )
    @backoff_on_predicate(EXPO, lambda rval: rval is None, max_tries=8)
    @limits(calls=1, period=1)
    def get(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
        timeout: int | None = None,
    ):
        return self.session.get(
            url=url, headers=headers, params=params, timeout=timeout or self.default_timeout
        )
