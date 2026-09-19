from __future__ import annotations

import importlib.util
import time
from pathlib import Path
from urllib.error import URLError

import pytest

ROOT = Path(__file__).resolve().parents[1]
STATS = ROOT / "plugins/lukedaduke.ticker/bin/market_stats.py"


def load():
    spec = importlib.util.spec_from_file_location("market_stats", STATS)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _payload(price: float, prev: float) -> dict:
    return {"chart": {"result": [{"meta": {"regularMarketPrice": price, "chartPreviousClose": prev}}]}}


def test_maps_price_and_change() -> None:
    mod = load()

    def fetch(sym: str, **_kw) -> dict:
        if sym == "NVDA":
            return _payload(100.0, 80.0)
        return _payload(10.0, 10.0)

    data = mod.collect(fetch=fetch)
    assert data["ok"] is True
    nvda = next(x for x in data["items"] if x["symbol"] == "NVDA")
    assert nvda["price"] == "$100.00"
    assert nvda["change"] == "+25.00%"
    assert nvda["positive"] is True


def test_empty_watchlist_ok_true_when_quotes_succeed() -> None:
    mod = load()
    data = mod.collect(fetch=lambda _sym, **_kw: _payload(1.0, 1.0))
    assert data["ok"] is True
    assert isinstance(data["items"], list)
    assert len(data["items"]) > 0


def test_network_failure_returns_error() -> None:
    mod = load()

    def fetch(_sym: str, **_kw) -> dict:
        raise URLError("offline")

    data = mod.collect(fetch=fetch)
    assert data["ok"] is False
    assert data["error"]
    assert data["items"]
    assert all(row["price"] == "--" for row in data["items"])


def test_missing_price_is_unavailable_not_fake_zero() -> None:
    """`regularMarketPrice or 0` used to render a missing quote as a fake
    $0.00 / -100% — an absent price must take the failure path instead."""
    mod = load()

    def fetch(sym: str, **_kw) -> dict:
        if sym == "NVDA":
            # Chart succeeds but the price field is absent.
            return {"chart": {"result": [{"meta": {"chartPreviousClose": 80.0}}]}}
        return _payload(10.0, 10.0)

    data = mod.collect(fetch=fetch)
    nvda = next(x for x in data["items"] if x["symbol"] == "NVDA")
    assert nvda["ok"] is False
    assert nvda["price"] == "--"
    assert nvda["change"] == "--"
    assert nvda["error"]
    # The other rows are unaffected, so the payload stays ok overall.
    assert data["ok"] is True


def test_null_price_is_unavailable() -> None:
    mod = load()

    def fetch(_sym: str, **_kw) -> dict:
        return {"chart": {"result": [{"meta": {
            "regularMarketPrice": None, "chartPreviousClose": 80.0}}]}}

    data = mod.collect(fetch=fetch)
    assert data["ok"] is False
    assert all(row["ok"] is False for row in data["items"])
    assert all(row["price"] == "--" for row in data["items"])


def test_parse_chart_raises_on_missing_price() -> None:
    mod = load()
    with pytest.raises(ValueError, match="no quote"):
        mod.parse_chart("NVDA", {"chart": {"result": [{"meta": {}}]}})


def test_job_deadline_row_marks_unavailable() -> None:
    mod = load()
    item = mod.TICKERS[0]
    row = mod.quote_item(item, fetch=lambda *a, **k: _payload(1.0, 1.0),
                         deadline=time.monotonic() - 1)
    assert row["ok"] is False
    assert row["error"] == "job deadline reached"
    assert row["price"] == "--"


def test_clean_text_strips_controls_and_caps() -> None:
    mod = load()
    out = mod.clean_text("a\x00\x1fb\x7f" + "x" * 300)
    assert all(ord(c) >= 0x20 and ord(c) < 0x7f or c == " " for c in out)
    assert len(out) <= mod.MAX_ERR


def test_https_redirect_refusal() -> None:
    mod = load()
    handler = mod.HTTPSOnlyRedirectHandler()
    with pytest.raises(URLError):
        handler.redirect_request(None, None, 302, "Found", {},
                                 "http://evil.example/x")
    # An https destination is delegated to the base handler (returns a
    # Request or None — either way no refusal error).
    try:
        handler.redirect_request(None, None, 302, "Found", {},
                                 "https://example.com/x")
    except URLError as exc:
        pytest.fail(f"https redirect refused: {exc}")
    except AttributeError:
        # Base handler needs a real req; a None req may trip it — that is
        # fine, the gate already passed by not raising URLError.
        pass


# --- fetch_yahoo_chart gates (fake opener, no network) ----------------------

class _Headers:
    def __init__(self, d):
        self._d = d

    def get(self, key, default=None):
        return self._d.get(key, default)


class _Resp:
    def __init__(self, headers, body):
        self.headers = _Headers(headers)
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False

    def read(self, _n=-1):
        return self._body


def _opener(headers, body):
    class _O:
        def open(self, _req, timeout=None):
            return _Resp(headers, body)
    return _O()


def test_fetch_requires_json_content_type(monkeypatch) -> None:
    mod = load()
    monkeypatch.setattr(mod, "FETCH_OPENER",
                        _opener({"Content-Type": "text/html"}, b"<html></html>"))
    with pytest.raises(ValueError, match="unexpected response type"):
        mod.fetch_yahoo_chart("NVDA")


def test_fetch_rejects_absent_content_type(monkeypatch) -> None:
    """An absent Content-Type must not slip a non-JSON body to json.loads."""
    mod = load()
    monkeypatch.setattr(mod, "FETCH_OPENER", _opener({}, b"<html></html>"))
    with pytest.raises(ValueError, match="unexpected response type absent"):
        mod.fetch_yahoo_chart("NVDA")


def test_fetch_accepts_json_and_enforces_byte_cap(monkeypatch) -> None:
    mod = load()
    body = b'{"chart": {"result": [{"meta": {"regularMarketPrice": 5}}]}}'
    monkeypatch.setattr(mod, "FETCH_OPENER",
                        _opener({"Content-Type": "application/json; charset=utf-8"}, body))
    assert mod.fetch_yahoo_chart("NVDA")["chart"]["result"][0]["meta"]["regularMarketPrice"] == 5

    monkeypatch.setattr(mod, "FETCH_OPENER",
                        _opener({"Content-Type": "application/json"},
                                b"x" * (mod.MAX_RESPONSE_BYTES + 2)))
    with pytest.raises(ValueError, match="byte budget"):
        mod.fetch_yahoo_chart("NVDA")


def test_fetch_url_is_literal_https() -> None:
    # The fetch URL is a hardcoded https f-string — the runtime scheme
    # check is a belt-and-suspenders guard; assert both exist in source.
    src = STATS.read_text()
    assert 'f"https://query1.finance.yahoo.com' in src
    assert 'refused non-HTTPS URL' in src
