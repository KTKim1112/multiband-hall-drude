"""How the packaged build picks the address it serves on. FR-106, T1906.

The reader's window is the thing being protected here. A program that takes a
different port every run turns the window it opened last time into one that
can never work again, and the reader has no way to tell that window from a
working one. So the previous run's port is tried first, and everything about
that has to fail softly: a note that is not there, a note that is damaged, a
port something else now holds.
"""

from __future__ import annotations

import socket

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("uvicorn")

from app import desktop, resources        # noqa: E402


@pytest.fixture()
def remembered(tmp_path, monkeypatch):
    monkeypatch.setattr(resources, "state", lambda: tmp_path)
    return tmp_path


def _port_of(sock: socket.socket) -> int:
    return sock.getsockname()[1]


def test_nothing_remembered_yet_takes_a_port_from_the_system(remembered):
    assert desktop._remembered_port() is None
    sock = desktop._listening_socket()
    try:
        assert _port_of(sock) > 0
    finally:
        sock.close()


def test_the_previous_runs_port_is_used_again(remembered):
    first = desktop._listening_socket()
    port = _port_of(first)
    desktop._remember_port(port)
    first.close()

    second = desktop._listening_socket()
    try:
        assert _port_of(second) == port
    finally:
        second.close()


def test_a_port_someone_else_holds_is_given_up(remembered):
    held = desktop._listening_socket()
    port = _port_of(held)
    desktop._remember_port(port)
    try:
        # The held socket is still open: this stands for a second copy of the
        # program, or anything else that took the port in the meantime.
        second = desktop._listening_socket()
        try:
            assert _port_of(second) != port
            assert _port_of(second) > 0
        finally:
            second.close()
    finally:
        held.close()


@pytest.mark.parametrize("note", ["", "   ", "not a number", "0", "80", "70000", "-1"])
def test_a_damaged_or_unusable_note_is_ignored(remembered, note):
    (remembered / desktop.PORT_FILE).write_text(note, encoding="ascii")
    assert desktop._remembered_port() is None
    sock = desktop._listening_socket()
    try:
        assert _port_of(sock) > 0
    finally:
        sock.close()


def test_remembering_where_it_cannot_write_is_not_a_failure(tmp_path, monkeypatch):
    # A folder unpacked read only, or on a share. The program still has to run.
    monkeypatch.setattr(resources, "state", lambda: tmp_path / "file" / "under" / "a" / "file")
    (tmp_path / "file").write_text("not a directory", encoding="ascii")
    desktop._remember_port(50000)
    assert desktop._remembered_port() is None
