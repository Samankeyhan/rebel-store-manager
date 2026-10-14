"""tools/run_app/ports.py: the port finder, with invented busy and reserved ports (nothing real is probed)."""

import socket
import subprocess
from types import SimpleNamespace

import pytest

from tools.run_app import ports

NETSH = """
Protocol tcp Port Exclusion Ranges

Start Port    End Port
----------    --------
      1025        1124
      1125        1224
      7990        8010
     11343       11442
     50000       50059     *

* - Administered port exclusions.
"""


def test_the_netsh_table_is_parsed_including_the_administered_star_line():
    assert ports.parse_excluded_ranges(NETSH) == [(1025, 1124), (1125, 1224), (7990, 8010), (11343, 11442), (50000, 50059)]
    assert ports.parse_excluded_ranges("") == []
    assert ports.parse_excluded_ranges("The requested operation requires elevation.") == []


def test_a_port_inside_a_reserved_range_is_excluded():
    ranges = [(7990, 8010), (50000, 50059)]
    assert ports.is_excluded(8000, ranges) and ports.is_excluded(7990, ranges) and ports.is_excluded(8010, ranges)
    assert not ports.is_excluded(8011, ranges) and not ports.is_excluded(7989, ranges)


def test_excluded_ranges_reads_netsh_and_survives_its_failure():
    ok = lambda *a, **k: SimpleNamespace(returncode=0, stdout=NETSH)
    assert (7990, 8010) in ports.excluded_ranges(ok)
    failed = lambda *a, **k: SimpleNamespace(returncode=1, stdout=NETSH)
    assert ports.excluded_ranges(failed) == []

    def missing(*a, **k):
        raise FileNotFoundError("netsh")

    assert ports.excluded_ranges(missing) == []

    def hangs(*a, **k):
        raise subprocess.TimeoutExpired("netsh", 15)

    assert ports.excluded_ranges(hangs) == []


def test_the_default_port_is_taken_when_it_is_free():
    assert ports.find_port(busy=lambda port: False) == (8000, [], [])


def test_busy_ports_are_skipped_in_order():
    port, busy, reserved = ports.find_port(busy=lambda p: p in (8000, 8001))
    assert (port, busy, reserved) == (8002, [8000, 8001], [])


def test_reserved_ranges_are_skipped_without_a_bind_test():
    probed = []

    def busy(port):
        probed.append(port)
        return False

    port, skipped_busy, skipped_reserved = ports.find_port(ranges=[(7990, 8010)], busy=busy)
    assert port == 8011 and skipped_reserved == list(range(8000, 8011)) and skipped_busy == []
    assert probed == [8011]  # a reserved port is never even tried


def test_busy_and_reserved_ports_together():
    port, busy, reserved = ports.find_port(ranges=[(8001, 8002)], busy=lambda p: p in (8000, 8003))
    assert (port, busy, reserved) == (8004, [8000, 8003], [8001, 8002])


def test_a_preferred_port_other_than_the_default():
    assert ports.find_port(preferred=8300, busy=lambda p: p == 8300)[0] == 8301


def test_no_free_port_says_what_was_skipped():
    with pytest.raises(ports.NoFreePort) as exc_info:
        ports.find_port(preferred=8000, span=4, ranges=[(8002, 8003)], busy=lambda p: True)
    exc = exc_info.value
    assert (exc.first, exc.last, exc.busy, exc.reserved) == (8000, 8003, [8000, 8001], [8002, 8003])
    assert "No free port between 8000 and 8003" in str(exc) and "busy: [8000, 8001]" in str(exc) and "reserved by Windows: [8002, 8003]" in str(exc)


def test_the_real_busy_check_sees_a_listening_socket():
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    try:
        port = listener.getsockname()[1]
        assert ports.is_busy(port) is True
    finally:
        listener.close()
    assert ports.is_busy(port) is False
