"""The pure format rules: exact routes, allowed methods, no unexpected query, JSON bodies only."""

import pytest

from keyserver.request_rules import (
    ALLOWED_ROUTES, JSON_TYPE, MAX_BODY_BYTES, QUERY_PARAMETERS, Rejection, check_format,
)


def verdict(method: str = "GET", path: str = "/check", query: bytes = b"", content_type: str | None = None,
            has_body: bool = False) -> Rejection | None:
    return check_format(method, path, query, content_type, has_body)


def test_limits_and_routes_are_the_expected_ones() -> None:
    assert MAX_BODY_BYTES == 1_048_576
    assert JSON_TYPE == "application/json"
    assert ALLOWED_ROUTES["/check"] == frozenset({"GET"})


def test_allowed_route_and_method_passes() -> None:
    assert verdict() is None


def test_unknown_path_is_404() -> None:
    rejection = verdict(path="/inconnu")
    assert rejection is not None and (rejection.status, rejection.allow) == (404, None)


def test_wrong_method_is_405_with_the_allow_value() -> None:
    rejection = verdict(method="DELETE")
    assert rejection is not None and (rejection.status, rejection.allow) == (405, "GET")


@pytest.mark.parametrize("path", ["/check/", "//check", "/CHECK", "/check%2F", "/check/..", "/check%00", "", "check", "/check "])
def test_path_variants_are_all_rejected(path: str) -> None:
    rejection = verdict(path=path)
    assert rejection is not None and rejection.status == 404


def test_unexpected_query_string_is_400() -> None:
    rejection = verdict(query=b"x=1")
    assert rejection is not None and rejection.status == 400


@pytest.mark.parametrize("content_type", [None, "", "text/plain", "application/xml", "application/jsonp", "multipart/form-data"])
def test_body_without_a_json_content_type_is_415(content_type: str | None) -> None:
    rejection = verdict("POST", "/admin/revoke", content_type=content_type, has_body=True)
    assert rejection is not None and rejection.status == 415


@pytest.mark.parametrize("content_type", ["application/json", "application/json; charset=utf-8",
                                          "Application/JSON", "application/json;charset=UTF-8"])
def test_json_content_type_with_utf8_charset_is_accepted_and_case_is_ignored(content_type: str) -> None:
    assert verdict("POST", "/admin/revoke", content_type=content_type, has_body=True) is None


def test_other_charsets_and_parameters_are_refused() -> None:
    for content_type in ("application/json; charset=latin-1", "application/json; boundary=x", "application/json; a=b; c=d"):
        rejection = verdict("POST", "/admin/revoke", content_type=content_type, has_body=True)
        assert rejection is not None and rejection.status == 415


def test_content_type_is_ignored_when_there_is_no_body() -> None:
    assert verdict(content_type="text/plain", has_body=False) is None


def test_allowed_routes_and_query_parameters_are_the_planned_ones() -> None:
    assert ALLOWED_ROUTES["/readings"] == frozenset({"GET", "POST"})
    assert ALLOWED_ROUTES["/readings/latest"] == frozenset({"GET"})
    assert ALLOWED_ROUTES["/admin/revoke"] == frozenset({"POST"})
    assert QUERY_PARAMETERS == {("/readings", "GET"): frozenset({"since", "limit"}),
                                ("/readings/latest", "GET"): frozenset({"after", "limit"})}


def test_declared_get_routes_accept_their_own_parameters() -> None:
    assert verdict(path="/readings", query=b"since=0&limit=2000") is None
    assert verdict(path="/readings", query=b"limit=5&since=1") is None
    assert verdict(path="/readings/latest", query=b"after=12&limit=100") is None
    assert verdict(path="/readings", query=b"since=999999999999") is None


@pytest.mark.parametrize("query", [
    b"since=1&since=2", b"foo=1", b"since=abc", b"since=1.5", b"since=-1", b"since=1234567890123", b"since=%31",
    b"since=1&limit=2&x=3", b"since=", b"since", b"=1", b"since=1&", b"&since=1", b"SINCE=1", b"since=1;limit=2",
    b"since=+1", b"since=1 ", b"after=1",
])
def test_unknown_repeated_non_integer_long_or_encoded_parameters_are_refused(query: bytes) -> None:
    rejection = verdict(path="/readings", query=query)
    assert rejection is not None
    assert (rejection.status, rejection.detail) == (400, "unexpected_query")


def test_query_on_check_and_on_post_routes_is_still_refused() -> None:
    assert verdict(path="/check", query=b"since=1") is not None
    for path in ("/readings", "/admin/revoke"):
        rejection = verdict(method="POST", path=path, query=b"since=1", content_type="application/json", has_body=True)
        assert rejection is not None and rejection.status == 400


def test_get_with_a_body_is_refused() -> None:
    rejection = verdict(path="/readings", query=b"since=0&limit=1", content_type="application/json", has_body=True)
    assert rejection is not None
    assert (rejection.status, rejection.detail) == (400, "unexpected_body")


def test_readings_route_answers_405_with_both_methods_listed() -> None:
    rejection = verdict(method="DELETE", path="/readings")
    assert rejection is not None
    assert (rejection.status, rejection.allow) == (405, "GET, POST")
