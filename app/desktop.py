"""Entry point of the packaged build. FR-106.

Serves the application on the loopback interface, on a port the operating
system chooses, and opens a browser once the server answers. Nothing imports
this: the packaged build and `uvicorn app.main:app` run the same `app` object
and differ only in how they are started.
"""

from __future__ import annotations

import socket
import sys
import threading
import time
import webbrowser

import uvicorn

from . import resources
from .main import app

HOST = "127.0.0.1"
BROWSER_TIMEOUT_S = 30.0
PORT_FILE = "port"


def _remembered_port() -> int | None:
    """The port of the previous run, or nothing if there is no usable note."""
    try:
        text = (resources.state() / PORT_FILE).read_text(encoding="ascii").strip()
    except OSError:
        return None
    try:
        port = int(text)
    except ValueError:
        return None
    return port if 1024 <= port <= 65535 else None


def _remember_port(port: int) -> None:
    """Best effort. Not being able to remember is not a failure to run."""
    try:
        directory = resources.state()
        directory.mkdir(parents=True, exist_ok=True)
        (directory / PORT_FILE).write_text(str(port), encoding="ascii")
    except OSError:
        pass


def _listening_socket() -> socket.socket:
    """Bound and listening, handed to uvicorn whole. FR-106.

    The previous run's port first: a reader who left that window open comes
    back to it, and a program that moves every time turns its own old window
    into a dead one. A port the system chooses when that one is taken -- by
    another copy of this program, or by anything else -- or not yet known. A
    fixed port would be a guess about a machine nobody has seen. Passing the
    bound socket rather than its number closes the window in which something
    else could take the port. Loopback only: the page holds unpublished
    measurements and is for one person.
    """
    for port in (_remembered_port(), 0):
        if port is None:
            continue
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind((HOST, port))
            sock.listen()
        except OSError:
            sock.close()
            continue
        return sock
    raise OSError("no port free on the loopback interface")


def _open_browser_when_ready(server: uvicorn.Server, url: str) -> None:
    """Not before the server answers: a connection error reads as a broken program."""
    deadline = time.monotonic() + BROWSER_TIMEOUT_S
    while time.monotonic() < deadline:
        if server.started:
            webbrowser.open(url)
            return
        time.sleep(0.1)


def main() -> int:
    sock = _listening_socket()
    port = sock.getsockname()[1]
    url = f"http://{HOST}:{port}/"
    _remember_port(port)

    server = uvicorn.Server(uvicorn.Config(app, log_level="warning"))
    threading.Thread(target=_open_browser_when_ready, args=(server, url), daemon=True).start()

    # flush: when launched from a shortcut stdout is not a terminal and Python
    # buffers it, and this is all there is on screen until the browser opens.
    print("Multiband Hall analysis", flush=True)
    print(f"  {url}", flush=True)
    print("  Closing this window stops the program.", flush=True)
    print(flush=True)

    try:
        server.run(sockets=[sock])
    except KeyboardInterrupt:
        pass
    finally:
        sock.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
