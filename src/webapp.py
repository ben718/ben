"""A tiny WSGI application that serves a functional HTML page.

The goal of this module is to keep the application completely
dependency-free so that it can run in minimal environments while still
providing a pleasant, working landing page for the project.
"""
from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
from subprocess import CalledProcessError, run
from typing import Callable, Iterable, List, Tuple
from wsgiref.simple_server import make_server

StartResponse = Callable[[str, List[Tuple[str, str]]], None]
WSGIApplication = Callable[[dict, StartResponse], Iterable[bytes]]

PROJECT_ROOT = Path(__file__).resolve().parents[1]

GIT_PLACEHOLDER = "{{GIT_METADATA}}"

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang=\"fr\">
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>Site fonctionnel</title>
    <style>
      :root {
        color-scheme: light dark;
        --background: #f3f4f6;
        --foreground: #111827;
        --accent: #2563eb;
        --accent-contrast: #ffffff;
        --card: #ffffffcc;
      }

      @media (prefers-color-scheme: dark) {
        :root {
          --background: #111827;
          --foreground: #f9fafb;
          --card: #1f2937cc;
        }
      }

      body {
        margin: 0;
        font-family: "Segoe UI", Roboto, system-ui, -apple-system, sans-serif;
        background: linear-gradient(160deg, var(--background), #dbeafe);
        min-height: 100vh;
        display: flex;
        align-items: center;
        justify-content: center;
        color: var(--foreground);
      }

      main {
        background: var(--card);
        border-radius: 24px;
        padding: 3rem;
        max-width: 680px;
        box-shadow: 0 25px 50px -12px rgba(37, 99, 235, 0.25);
        backdrop-filter: blur(12px);
      }

      h1 {
        font-size: clamp(2rem, 5vw, 3rem);
        margin-top: 0;
      }

      p {
        line-height: 1.6;
        margin-bottom: 1.5rem;
      }

      a.button {
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        background: var(--accent);
        color: var(--accent-contrast);
        padding: 0.9rem 1.8rem;
        border-radius: 999px;
        font-weight: 600;
        text-decoration: none;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
        box-shadow: 0 10px 25px -12px rgba(37, 99, 235, 0.5);
      }

      a.button:hover {
        transform: translateY(-2px);
        box-shadow: 0 16px 32px -12px rgba(37, 99, 235, 0.6);
      }

      ul.features {
        list-style: none;
        padding: 0;
        margin: 2rem 0;
        display: grid;
        gap: 1rem;
      }

      ul.features li {
        background: rgba(37, 99, 235, 0.08);
        border-radius: 16px;
        padding: 1rem 1.25rem;
      }

      footer {
        font-size: 0.9rem;
        opacity: 0.7;
        margin-top: 2rem;
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
      }

      footer .git-info {
        font-family: "Fira Code", "Source Code Pro", monospace;
        font-size: 0.85rem;
        opacity: 0.9;
      }
    </style>
  </head>
  <body>
    <main>
      <h1>Bienvenue sur votre site fonctionnel ✨</h1>
      <p>
        Cette page est servie par une petite application WSGI écrite en pur
        Python. Elle ne dépend d'aucune bibliothèque externe et peut être
        lancée immédiatement avec la commande <code>python -m webapp</code>.
      </p>
      <ul class=\"features\">
        <li>✅ Interface moderne et responsive fonctionnant sans dépendances.</li>
        <li>⚡ Démarrage instantané grâce au serveur WSGI intégré.</li>
        <li>🛠️ Code simple à étendre pour répondre à vos besoins.</li>
      </ul>
      <a class=\"button\" href=\"https://www.python.org\">Explorer Python</a>
      <footer>
        Besoin de personnaliser le site ? Modifiez simplement
        <code>HTML_TEMPLATE</code> dans <code>webapp.py</code>.
        <span class=\"git-info\">{git_placeholder}</span>
      </footer>
    </main>
  </body>
</html>
""".replace("{git_placeholder}", GIT_PLACEHOLDER)

NOT_FOUND_TEMPLATE = """<!DOCTYPE html>
<html lang=\"fr\">
  <head>
    <meta charset=\"utf-8\" />
    <title>Page introuvable</title>
  </head>
  <body>
    <h1>404 - Page introuvable</h1>
    <p>La ressource demandée n'existe pas.</p>
  </body>
</html>
"""


def _response(status: str, body: str, start_response: StartResponse) -> Iterable[bytes]:
    payload = body.encode("utf-8")
    headers = [
        ("Content-Type", "text/html; charset=utf-8"),
        ("Content-Length", str(len(payload))),
    ]
    start_response(status, headers)
    yield payload


def _run_git_command(args: list[str]) -> str:
    """Execute a Git command rooted at the project directory."""

    result = run(
        ["git", *args],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
        check=True,
    )
    return result.stdout.strip()


def _get_git_metadata() -> tuple[str, str] | None:
    """Return the active branch name and commit hash if available."""

    try:
        branch = _run_git_command(["rev-parse", "--abbrev-ref", "HEAD"])
        commit = _run_git_command(["rev-parse", "HEAD"])
    except (CalledProcessError, FileNotFoundError, PermissionError):
        return None

    if not branch or not commit:
        return None

    return branch, commit


def _render_git_metadata_html() -> str:
    """Generate the HTML snippet describing the current Git state."""

    metadata = _get_git_metadata()
    if metadata is None:
        return "Version Git indisponible (dépôt non initialisé)."

    branch, commit = metadata
    short_commit = commit[:7]
    return f"Version Git : <code>{branch}</code> @ <code>{short_commit}</code>"


def _render_homepage(git_html: str) -> str:
    """Insert the Git metadata into the homepage template."""

    return HTML_TEMPLATE.replace(GIT_PLACEHOLDER, git_html)


def create_app(
    git_info_provider: Callable[[], str] | None = None,
) -> WSGIApplication:
    """Return the WSGI application used by the project."""

    provider = git_info_provider or _render_git_metadata_html

    def application(environ: dict, start_response: StartResponse) -> Iterable[bytes]:
        path = environ.get("PATH_INFO", "/") or "/"
        if path in {"", "/", "/index.html"}:
            git_html = provider()
            body = _render_homepage(git_html)
            return _response("200 OK", body, start_response)

        return _response("404 Not Found", NOT_FOUND_TEMPLATE, start_response)

    return application


def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Launch the development server."""

    with make_server(host, port, create_app()) as httpd:
        print(f"Serving on http://{host}:{port} – press Ctrl+C to quit")
        httpd.serve_forever()


def _parse_args(argv: list[str] | None = None) -> tuple[str, int]:
    parser = ArgumentParser(description="Launch the demonstration web server")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind")
    parser.add_argument("--port", default=8000, type=int, help="Port to listen on")
    args = parser.parse_args(argv)
    return args.host, args.port


def main(argv: list[str] | None = None) -> None:
    host, port = _parse_args(argv)
    serve(host, port)


if __name__ == "__main__":  # pragma: no cover - manual execution helper
    main()
