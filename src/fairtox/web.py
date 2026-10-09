"""Reading from the web, for FAIRsharing, the nanopublication services and the FIP ontology: one User-Agent, and
retries with backoff when a server is busy or a connection fails."""
import http.client
import time
import urllib.error
import urllib.request

from fairtox import __version__

UA = f'fairtox/{__version__} (+https://github.com/johannehouweling/FAIR-implementation-ecosystem-for-toxicology)'
RETRY = (429, 500, 502, 503, 504)


class Unreadable(RuntimeError):
    """A source that could not be read. Commands stop on it before they build or change anything."""


def fetch(url, headers=None, data=None, method=None, timeout=120):
    """The response headers and body. HTTP 429 and 5xx answers, timeouts and failed connections are retried after 5,
    30 and 120 seconds. Any other HTTP error is raised as it is, for the caller to explain; a connection that keeps
    failing raises Unreadable."""
    request = urllib.request.Request(url, data, {**(headers or {}), 'User-Agent': UA}, method=method)
    for wait in (5, 30, 120, None):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as resp:
                return resp.headers, resp.read()
        except urllib.error.HTTPError as e:
            if e.code not in RETRY or wait is None:
                raise
        except (OSError, http.client.HTTPException) as e:
            if wait is None:
                raise Unreadable(f'{url} could not be read: {getattr(e, "reason", e)}') from None
        time.sleep(wait)


def get(url, accept, data=None):
    """The body as text, in the media type `accept`; POST when there is `data`."""
    try:
        return fetch(url, {'Accept': accept}, data)[1].decode('utf-8')
    except urllib.error.HTTPError as e:
        raise Unreadable(f'{url} answered HTTP {e.code}') from None
