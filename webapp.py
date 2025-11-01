"""Convenience wrapper to expose the WSGI app as ``python -m webapp``.

This file simply re-exports the implementation that lives in
``src/webapp.py`` so that users can launch the demo site without having to
manipulate ``PYTHONPATH`` manually.
"""
from __future__ import annotations

from src.webapp import (
    HTML_TEMPLATE,
    NOT_FOUND_TEMPLATE,
    GIT_PLACEHOLDER,
    StartResponse,
    WSGIApplication,
    _get_git_metadata,
    _render_git_metadata_html,
    _render_homepage,
    create_app,
    main,
    serve,
)

__all__ = [
    "HTML_TEMPLATE",
    "NOT_FOUND_TEMPLATE",
    "GIT_PLACEHOLDER",
    "StartResponse",
    "WSGIApplication",
    "_get_git_metadata",
    "_render_git_metadata_html",
    "_render_homepage",
    "create_app",
    "main",
    "serve",
]


if __name__ == "__main__":  # pragma: no cover - entrypoint helper
    main()
