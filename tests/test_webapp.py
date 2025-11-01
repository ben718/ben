from __future__ import annotations

from types import SimpleNamespace
from typing import Callable, Iterable, List, Tuple
from wsgiref.util import setup_testing_defaults

import pytest

import webapp as webapp_module
from webapp import GIT_PLACEHOLDER, NOT_FOUND_TEMPLATE, create_app


def _invoke_app(path: str, git_info_provider: Callable[[], str] | None = None) -> SimpleNamespace:
    app = create_app(git_info_provider)
    environ: dict = {}
    setup_testing_defaults(environ)
    environ["PATH_INFO"] = path

    status_holder: List[str] = []
    headers_holder: List[List[Tuple[str, str]]] = []

    def start_response(status: str, headers: List[Tuple[str, str]]) -> None:
        status_holder.append(status)
        headers_holder.append(headers)

    body_iterable: Iterable[bytes] = app(environ, start_response)
    body_bytes = b"".join(body_iterable)

    return SimpleNamespace(
        status=status_holder[0],
        headers=headers_holder[0],
        body=body_bytes,
    )


@pytest.mark.parametrize("path", ["/", "", "/index.html"])
def test_homepage_paths_return_success(path: str) -> None:
    git_snippet = "Version Git de test"

    response = _invoke_app(path, git_info_provider=lambda: git_snippet)

    assert response.status == "200 OK"
    html = response.body.decode("utf-8")
    assert "OmadaBOM – configurez un réseau précis" in html
    assert "data-step=\"1\"" in html
    assert "id=\"hardwareList\"" in html
    assert git_snippet in html
    assert GIT_PLACEHOLDER not in html
    assert ("Content-Type", "text/html; charset=utf-8") in response.headers


def test_unknown_path_returns_not_found() -> None:
    response = _invoke_app("/does-not-exist")
    assert response.status == "404 Not Found"
    assert response.body.decode("utf-8") == NOT_FOUND_TEMPLATE


def test_homepage_invokes_git_provider_once() -> None:
    calls: list[None] = []

    def provider() -> str:
        calls.append(None)
        return "Git info"

    _invoke_app("/", git_info_provider=provider)
    assert len(calls) == 1


def test_not_found_does_not_call_git_provider() -> None:
    calls: list[None] = []

    def provider() -> str:
        calls.append(None)
        return "Git info"

    _invoke_app("/missing", git_info_provider=provider)
    assert not calls


def test_render_git_metadata_html_handles_missing_repo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(webapp_module, "_get_git_metadata", lambda: None)
    result = webapp_module._render_git_metadata_html()
    assert "indisponible" in result


def test_render_git_metadata_html_formats_branch_and_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(webapp_module, "_get_git_metadata", lambda: ("main", "abcdef123456"))
    result = webapp_module._render_git_metadata_html()
    assert "main" in result
    assert "abcdef1" in result


def test_render_homepage_replaces_placeholder() -> None:
    html = webapp_module._render_homepage("Contenu Git")
    assert "Contenu Git" in html
    assert GIT_PLACEHOLDER not in html
