"""Tests for the OCPF API client against mocked responses."""

from __future__ import annotations

import httpx
import pytest
import respx

from ocpf_cli import api


@respx.mock
def test_get_json_success():
    respx.get(api.BASE_URL + "districts").mock(
        return_value=httpx.Response(200, json=[{"code": 1}])
    )
    result = api.get_json("districts")
    assert result == [{"code": 1}]


@respx.mock
def test_get_json_success_tolerates_leading_slash():
    respx.get(api.BASE_URL + "districts").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    assert api.get_json("/districts") == {"ok": True}


@respx.mock
def test_get_json_passes_params():
    route = respx.get(api.BASE_URL + "search").mock(
        return_value=httpx.Response(200, json={})
    )
    api.get_json("search", params={"q": "x"})
    assert route.calls.last.request.url.params["q"] == "x"


@respx.mock
def test_http_error_maps_to_ocpf_error():
    respx.get(api.BASE_URL + "missing").mock(
        return_value=httpx.Response(404)
    )
    with pytest.raises(api.OcpfApiError) as exc:
        api.get_json("missing")
    assert exc.value.status_code == 404
    assert exc.value.path == "missing"


@respx.mock
def test_server_error_maps_to_ocpf_error():
    respx.get(api.BASE_URL + "boom").mock(
        return_value=httpx.Response(500)
    )
    with pytest.raises(api.OcpfApiError) as exc:
        api.get_json("boom")
    assert exc.value.status_code == 500


@respx.mock
def test_timeout_maps_to_ocpf_error():
    respx.get(api.BASE_URL + "slow").mock(
        side_effect=httpx.TimeoutException("timed out")
    )
    with pytest.raises(api.OcpfApiError) as exc:
        api.get_json("slow")
    assert exc.value.status_code is None
    assert "timed out" in str(exc.value).lower()


@respx.mock
def test_network_error_maps_to_ocpf_error():
    respx.get(api.BASE_URL + "down").mock(
        side_effect=httpx.ConnectError("connection refused")
    )
    with pytest.raises(api.OcpfApiError):
        api.get_json("down")


@respx.mock
def test_non_json_body_maps_to_ocpf_error():
    respx.get(api.BASE_URL + "html").mock(
        return_value=httpx.Response(200, text="<html>nope</html>")
    )
    with pytest.raises(api.OcpfApiError):
        api.get_json("html")
