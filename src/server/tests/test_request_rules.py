"""The pure format rules: exact routes, allowed methods, no unexpected query, JSON bodies only."""

import pytest

from keyserver.request_rules import ALLOWED_ROUTES, JSON_TYPE, MAX_BODY_BYTES, Rejection, check_format


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
    rejection = verdict(content_type=content_type, has_body=True)
    assert rejection is not None and rejection.status == 415


@pytest.mark.parametrize("content_type", ["application/json", "application/json; charset=utf-8",
                                          "Application/JSON", "application/json;charset=UTF-8"])
def test_json_content_type_with_utf8_charset_is_accepted_and_case_is_ignored(content_type: str) -> None:
    assert verdict(content_type=content_type, has_body=True) is None


def test_other_charsets_and_parameters_are_refused() -> None:
    for content_type in ("application/json; charset=latin-1", "application/json; boundary=x", "application/json; a=b; c=d"):
        rejection = verdict(content_type=content_type, has_body=True)
        assert rejection is not None and rejection.status == 415


def test_content_type_is_ignored_when_there_is_no_body() -> None:
    assert verdict(content_type="text/plain", has_body=False) is None
