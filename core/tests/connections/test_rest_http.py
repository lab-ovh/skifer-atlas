"""Frontière HTTP REST sans redirection ni restitution de secrets (plan 0036)."""

import secrets
import sys
import threading
from pathlib import Path
from urllib.parse import quote, urlencode, urlunsplit

import pytest
from fake_rest import FakeRest

from skifer_atlas.connectors import http
from skifer_atlas.repo.git import RepoError

sys.path.insert(0, str(Path(__file__).parents[1] / "compare"))
from test_rest_runner import save_dataset, setup_rest, space

__all__ = ["setup_rest", "space"]


def test_mask_unit():
    key = secrets.token_urlsafe(24) + "/+"
    credential = http.ApiKey(key, "query", "apikey", "")
    assert key not in repr(credential)
    url = urlunsplit(("https", "api.exemple.test", "/v1", urlencode({"apikey": key, "x": 1}), ""))
    assert quote(key, safe="") in url
    assert key not in http.message_of({"message": "x" * 295 + key}, key)


def test_next_url_other_host_refused():
    with FakeRest() as first, FakeRest() as other:
        key = http.ApiKey(first.key, "query", "apikey", "")
        with pytest.raises(RepoError) as caught:
            http.get(other.url + "/v1/data", key=key, origin=first.url)
        assert caught.value.code == "rest_next_url_refused" and other.requests == []


def test_redirect_not_followed():
    with FakeRest() as first, FakeRest() as other:
        first.replies = [(302, {}, {"Location": other.url + "/v1/data"})]
        reply = http.get(first.url + "/v1/data", key=http.ApiKey(first.key, "query", "apikey", ""),
                         origin=first.url)
        assert reply.status == 302 and len(first.requests) == 1 and not other.requests


def test_get_is_bounded_and_replaces_query_key():
    with FakeRest() as server:
        key = http.ApiKey(server.key, "query", "apikey", "")
        reply = http.get(server.url + "/v1/data?apikey=old", key=key, origin=server.url)
        assert reply.body == server.rows and reply.size > 0
        assert server.requests[0][1]["apikey"] == [server.key]
        with pytest.raises(RepoError) as caught:
            http.get(server.url + "/v1/data", key=key, origin=server.url, max_bytes=1)
        assert caught.value.code == "rest_response_too_large"


@pytest.mark.parametrize("status,code", [(401, "access_expired"), (402, "rest_payment_required"),
    (403, "rest_forbidden"), (500, "rest_server_error"), (400, "rest_http_error"),
    (200, "rest_error_body")])
def test_errors_map_to_codes(space, setup_rest, status, code):
    from skifer_atlas import connections
    from skifer_atlas.compare.rest_runner import RestRunner

    server, ds, compiled, plan = setup_rest
    ds["error_keys"] = ["error"]
    save_dataset(space, ds)
    server.replies = [(status, {"error": server.key}, {})]
    with pytest.raises(RepoError) as caught:
        RestRunner("exemple")(plan, compiled, threading.Event())
    assert caught.value.code == code and server.key not in str(caught.value)
    assert len(server.requests) == 1
    assert connections.status("exemple", "api-exemple")["my_access"] == (
        "expired" if status == 401 else "connected")


@pytest.mark.parametrize("headers,requests", [({}, 1), ({"Retry-After": "0"}, 2),
    ({"retry-after": "0"}, 2),
    ({"Retry-After": "61"}, 1), ({"Retry-After": "bad"}, 1)])
def test_429_retries_once(setup_rest, headers, requests):
    from skifer_atlas.compare.rest_runner import RestRunner

    server, _ds, compiled, plan = setup_rest
    server.replies = [(429, {}, headers)] * 3
    with pytest.raises(RepoError) as caught:
        RestRunner("exemple")(plan, compiled, threading.Event())
    assert caught.value.code == "rate_limited" and len(server.requests) == requests


def test_network_failure_never_includes_url_or_key():
    server = FakeRest()
    target = server.url + "/v1/data"
    key = http.ApiKey(server.key, "query", "apikey", "")
    server.close()
    with pytest.raises(RepoError) as caught:
        http.get(target, key=key, origin=server.url, timeout=0.5)
    assert caught.value.code == "host_unreachable"
    assert target not in str(caught.value) and key.value not in str(caught.value)


@pytest.mark.parametrize("exception", [
    __import__("http.client", fromlist=["InvalidURL"]).InvalidURL,
    __import__("http.client", fromlist=["IncompleteRead"]).IncompleteRead,
    __import__("http.client", fromlist=["BadStatusLine"]).BadStatusLine,
    __import__("http.client", fromlist=["LineTooLong"]).LineTooLong,
    RecursionError,
])
def test_get_sanitizes_exception_chain_and_counts_call(space, setup_rest, monkeypatch, capsys, exception):
    import traceback

    from skifer_atlas.compare.rest_runner import RestRunner
    from skifer_atlas.connectors.rest_budget import read_usage

    server, _ds, compiled, plan = setup_rest

    def fail(call, **kwargs):
        raise exception(call.full_url)

    monkeypatch.setattr(http._OPENER, "open", fail)
    with pytest.raises(RepoError) as caught:
        RestRunner("exemple")(plan, compiled, threading.Event())
    error = caught.value
    assert error.code == "host_unreachable"
    assert error.__cause__ is None and error.__context__ is None
    assert server.key not in str(error) + "".join(traceback.format_exception(error))
    output = capsys.readouterr()
    assert server.key not in output.out + output.err
    [usage] = read_usage("exemple", point_id="api-exemple")
    assert usage["calls"] == 1 and usage["errors"] == 1


def test_total_deadline_limits_slow_response():
    import time
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class Slow(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Length", "100")
            self.end_headers()
            for _ in range(100):
                try:
                    self.wfile.write(b"x")
                    self.wfile.flush()
                except OSError:
                    break
                time.sleep(0.03)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Slow)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{server.server_port}"
    start = time.monotonic()
    try:
        with pytest.raises(RepoError) as caught:
            http.get(origin + "/data", key=http.ApiKey("fake-key", "query", "apikey"),
                     origin=origin, timeout=0.2)
        assert caught.value.code == "host_unreachable"
        assert time.monotonic() - start < 1.0
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.mark.parametrize("bad", [" ", "\x01"])
def test_invalid_path_real_server_keeps_key_out_of_traceback_frames(bad):
    import traceback

    with FakeRest() as server:
        with pytest.raises(RepoError) as caught:
            http.get(server.url + "/v1/data" + bad + "page", origin=server.url,
                     key=http.ApiKey(server.key, "query", "apikey"))
        error = caught.value
        assert error.code == "host_unreachable" and str(error) == "Hôte REST injoignable."
        assert error.__cause__ is None and error.__context__ is None
        assert server.key not in "".join(traceback.format_exception(error))
        tb = error.__traceback__
        while tb:
            for value in list(tb.tb_frame.f_locals.values()):
                assert server.key not in repr(value)
                assert not isinstance(value, http.ApiKey) or value.value != server.key
            tb = tb.tb_next
        assert not server.requests
