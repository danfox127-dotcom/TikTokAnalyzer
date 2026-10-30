"""The library in Postgres, set up once however many requests arrive together."""

import os
import threading

import psycopg
import pytest

from favorites import pg

pytestmark = pytest.mark.skipif(
    not os.environ.get("FAVES_TEST_DATABASE_URL"),
    reason="about the Postgres library; set FAVES_TEST_DATABASE_URL to run")


def connect_together(n: int) -> list[str]:
    """``n`` connections opened at the same moment; the errors, if any."""
    errors, start = [], threading.Barrier(n)

    def one():
        start.wait()
        try:
            pg.connect().close()
        except Exception as exc:  # what a picture request saw on a fresh server
            errors.append(str(exc).splitlines()[0])

    threads = [threading.Thread(target=one) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    return errors


def test_a_page_of_pictures_at_once_sets_the_library_up_once():
    # A fresh server: every picture on the page asks for a connection at once.
    assert connect_together(8) == []


def test_servers_starting_together_take_turns():
    # Another server is part-way through setting up: this one waits its turn.
    holder = psycopg.connect(pg.url())
    holder.execute("SELECT pg_advisory_xact_lock(%s)", (pg._SETUP_LOCK,))
    done = []
    waiting = threading.Thread(target=lambda: done.append(pg.connect().close()))
    waiting.start()
    waiting.join(timeout=1.5)
    assert waiting.is_alive(), "set up without waiting for the other server"
    holder.rollback()  # the other server finishes
    waiting.join(timeout=30)
    holder.close()
    assert not waiting.is_alive() and done == [None]
