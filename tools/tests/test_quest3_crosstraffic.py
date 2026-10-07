"""Deterministic CPU tests: no ADB, device, socket connections or real sleeps."""
import json
import socket
import threading
from types import SimpleNamespace

import pytest

from tools.quest3 import crosstraffic as traffic


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class FakeSocket:
    def __init__(self, clock, ack=True, partial=False, write_delay=0):
        self.clock, self.ack, self.partial = clock, ack, partial
        self.write_delay = write_delay
        self.header, self.sent, self.closed = None, [], False

    def __enter__(self): return self
    def __exit__(self, *unused): self.closed = True
    def setsockopt(self, *unused): pass
    def settimeout(self, *unused): pass
    def shutdown(self, *unused): self.closed = True

    def sendall(self, data):
        if self.header is None:
            assert data[:4] == b"Q3TF"
            self.header = data
            return
        if self.partial:
            raise socket.timeout("partial payload")
        frame_id = int.from_bytes(self.header[4:8], "big")
        assert len(data) == int.from_bytes(self.header[8:], "big")
        self.sent.append((self.clock(), frame_id, len(data)))
        self.clock.sleep(self.write_delay)
        if self.ack:
            self.state.feed(b"Q3TA" + frame_id.to_bytes(4, "big"), self.clock())
        self.header = None


class FakeThread:
    """Deliver fake ACKs synchronously at payload completion, avoiding thread races."""
    def __init__(self, target, args, daemon):
        args[0].state = args[1]

    def start(self): pass
    def join(self, timeout): pass
    def is_alive(self): return False


def send(monkeypatch, *, ack=True, partial=False, write_delay=0, **kwargs):
    clock = FakeClock()
    sock = FakeSocket(clock, ack, partial, write_delay)
    monkeypatch.setattr(traffic.threading, "Thread", FakeThread)
    result = traffic.burst_sender("192.0.2.1", 45201, 1, 400, 1600,
                                  connect=lambda *a, **kw: sock, clock=clock,
                                  sleeper=clock.sleep, unix_ns=lambda: 1_000_000_000,
                                  **{"seconds": 4.4, "hz": 90, **kwargs})
    assert sock.closed
    return result, sock, clock


def test_schedule_boundaries_frame_counts_and_summary(monkeypatch):
    result, sock, clock = send(monkeypatch, start_delay_s=.5)
    assert [b["frames_sent"] for b in result["bursts"]] == [36, 36, 36]
    assert [b["start_unix_ns"] for b in result["bursts"]] == [1_500_000_000, 3_500_000_000, 5_500_000_000]
    assert [b["end_unix_ns"] for b in result["bursts"]] == [1_900_000_000, 3_900_000_000, 5_900_000_000]
    for i, (now, _, size) in enumerate(f for f in sock.sent if f[2] != 64):
        assert now == pytest.approx(.5 + (i // 36) * 2 + (i % 36) / 90)
        assert size == 1388
    assert clock.now == pytest.approx(4.9)
    assert result["bursts_sent"] == 3
    assert result["frames_sent"] == result["frames_acked"] == 108
    assert result["frames_skipped"] == result["partial_frames"] == 0
    assert result["keepalive_frames_sent"] == result["keepalive_frames_acked"] == 13
    assert result["keepalive_frames_skipped"] == result["keepalive_partial_frames"] == 0
    assert result["on_seconds"] == pytest.approx(1.2)
    assert result["achieved_on_mbps"] == pytest.approx(.99936)
    assert result["acked_payload_on_mbps"] == result["achieved_on_mbps"]
    assert result["ack_ms_p50"] == result["ack_ms_p99"] == result["ack_ms_max"] == 0
    assert result["pattern"] == {"mbps": 1, "on_ms": 400, "off_ms": 1600,
                                 "seconds": 4.4, "hz": 90, "start_delay_s": .5}
    json.dumps(result, allow_nan=False)


def test_truncated_final_burst(monkeypatch):
    result, sock, _ = send(monkeypatch, seconds=2.15, hz=10)
    assert [b["frames_sent"] for b in result["bursts"]] == [4, 2]
    assert result["bursts"][-1]["end_unix_ns"] == 3_150_000_000
    assert [t for t, _, size in sock.sent if size != 64] == pytest.approx([0, .1, .2, .3, 2, 2.1])


def test_inflight_cap_persists_across_off_windows(monkeypatch):
    result, sock, _ = send(monkeypatch, ack=False)
    assert len(sock.sent) == result["frames_sent"] == 3
    assert len(sock.state.pending) == 3
    assert result["frames_skipped"] == 105
    assert result["frames_acked"] == 0
    assert result["ack_ms_p50"] is None
    assert result["keepalive_frames_sent"] == 0
    assert result["keepalive_frames_skipped"] == 12


def test_keepalives_cover_delay_off_windows_and_final_off_window(monkeypatch):
    result, sock, _ = send(monkeypatch, start_delay_s=1.5, seconds=3)
    keepalive_times = [t for t, _, size in sock.sent if size == 64]
    assert keepalive_times == pytest.approx([
        .25, .5, .75, 1, 1.25, 2.15, 2.4, 2.65, 2.9, 3.15, 3.4, 4.15, 4.4])
    assert result["keepalive_frames_sent"] == result["keepalive_frames_acked"] == 13
    assert result["frames_sent"] == result["frames_acked"] == 72
    assert all(b - a < 1 for a, b in zip([0] + [t for t, _, _ in sock.sent],
                                        [t for t, _, _ in sock.sent] + [4.5]))
    assert [frame_id for _, frame_id, _ in sock.sent] == list(range(85))


def test_keepalives_share_inflight_cap_with_bursts(monkeypatch):
    result, sock, _ = send(monkeypatch, ack=False, start_delay_s=1.5, seconds=.4)
    assert result["keepalive_frames_sent"] == 3
    assert result["keepalive_frames_skipped"] == 2
    assert result["frames_sent"] == 0
    assert result["frames_skipped"] == 36
    assert len(sock.state.pending) == 3


def test_keepalive_acks_do_not_affect_burst_turnaround(monkeypatch):
    original = FakeSocket.sendall

    def delayed_keepalive_ack(self, data):
        original(self, data)
        if len(data) == 64:
            self.state.frames[self.sent[-1][1]]["ack"] += .5

    monkeypatch.setattr(FakeSocket, "sendall", delayed_keepalive_ack)
    result, _, _ = send(monkeypatch, start_delay_s=.5)
    assert result["keepalive_frames_acked"] == 13
    assert result["ack_ms_p50"] == result["ack_ms_p99"] == result["ack_ms_max"] == 0


def test_partial_keepalive_write_ends_stream_and_is_counted_separately(monkeypatch):
    result, sock, _ = send(monkeypatch, partial=True, start_delay_s=.5)
    assert result["keepalive_partial_frames"] == 1
    assert result["partial_frames"] == result["frames_sent"] == 0
    assert result["receiver_error"] == "partial_or_timed_out_write"
    assert len(sock.state.frames) == 1
    assert result["bursts"] == []


def test_partial_write_ends_stream(monkeypatch):
    result, sock, _ = send(monkeypatch, partial=True)
    assert result["partial_frames"] == 1
    assert result["frames_sent"] == 0
    assert result["receiver_error"] == "partial_or_timed_out_write"
    assert len(sock.state.frames) == 1


@pytest.mark.parametrize("bounds", [{"on_ms": 0}, {"off_ms": -1}, {"seconds": 0},
                                   {"start_delay_s": -1}, {"seconds": float("nan")}])
def test_invalid_bounds_do_not_connect(bounds):
    args = {"on_ms": 400, "off_ms": 1600, "seconds": 4, **bounds}

    def connect(*args, **kwargs):
        pytest.fail("invalid bounds attempted a connection")

    with pytest.raises(ValueError):
        traffic.burst_sender("192.0.2.1", 45201, 1, connect=connect, **args)


def test_missed_slots_are_skipped_without_writing_off_window(monkeypatch):
    result, sock, _ = send(monkeypatch, seconds=.4, hz=10, write_delay=.25)
    assert [t for t, _, _ in sock.sent] == pytest.approx([0, .25])
    assert result["frames_skipped"] == 2


def test_fragmented_and_coalesced_acks_and_turnaround():
    state = traffic._Acks()
    state.frames = {0: {"start": 1, "ack": None}, 1: {"start": 2, "ack": None}}
    state.pending = {0, 1}
    data = b"Q3TA\0\0\0\0Q3TA\0\0\0\1"
    state.feed(data[:3], 3)
    assert state.pending == {0, 1}
    state.feed(data[3:], 4)
    assert not state.pending
    assert [f["ack"] - f["start"] for f in state.frames.values()] == [3, 2]
    assert state.error is None
    state.feed(data[:8], 5)
    assert state.error == "unknown_or_duplicate_ack"


@pytest.mark.parametrize("ack,error", [(b"BAD!\0\0\0\0", "invalid_receiver_ack"),
                                      (b"Q3TA\0\0\0\1", "unknown_or_duplicate_ack")])
def test_rejects_invalid_acks(ack, error):
    state = traffic._Acks()
    state.feed(ack, 1)
    assert state.error == error


def test_ctrl_c_closes_socket_and_keeps_partial_summary(monkeypatch):
    clock = FakeClock()
    sock = FakeSocket(clock)
    monkeypatch.setattr(traffic.threading, "Thread", FakeThread)

    def sleep(seconds):
        if seconds > 0: raise KeyboardInterrupt

    result = traffic.burst_sender("192.0.2.1", 45201, 1, 400, 1600, 5,
                                  connect=lambda *a, **kw: sock, clock=clock,
                                  sleeper=sleep, unix_ns=lambda: 0)
    assert sock.closed and result["interrupted"]
    assert result["frames_sent"] == 1
    assert result["bursts"][0]["end_unix_ns"] == 0


def test_run_collects_receiver_json_without_adb(monkeypatch):
    calls = []

    class Process:
        returncode = 0
        def communicate(self, timeout): return '{"frames_received": 2}', ""
        def poll(self): return 0

    monkeypatch.setattr(traffic.subprocess, "Popen", lambda command, **kw: calls.append(command) or Process())
    monkeypatch.setattr(traffic.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(traffic, "wifi_readback", lambda *args: {"link_rate_mbps": 2401})
    monkeypatch.setattr(traffic, "burst_sender", lambda *args: {"frames_sent": 2})
    args = SimpleNamespace(adb="fake-adb", serial="fake", receiver="/fake/receiver", port=45201,
                           ip="192.0.2.1", mbps=1, on_ms=400, off_ms=1600, seconds=4.4,
                           hz=90, start_delay_s=.5)
    result = traffic.run(args)
    assert calls == [["fake-adb", "-s", "fake", "shell", "/fake/receiver", "45201", "14.9"]]
    assert result["receiver"] == {"frames_received": 2}
    assert result["receiver_returncode"] == 0
    assert result["wifi_before"] == result["wifi_after"] == {"link_rate_mbps": 2401}


def test_ack_reader_drains_chunks_and_reports_eof():
    state = traffic._Acks()
    state.frames[0] = {"start": 0, "ack": None}
    state.pending.add(0)
    chunks = iter([socket.timeout(), b"Q3", b"TA\0\0\0\0", b""])

    class ReaderSocket:
        def recv(self, size):
            chunk = next(chunks)
            if isinstance(chunk, Exception): raise chunk
            return chunk

    traffic._read_acks(ReaderSocket(), state, threading.Event(), lambda: .025)
    assert state.frames[0]["ack"] == .025
    assert not state.pending
    assert state.error == "receiver_closed"


def test_run_terminates_receiver_on_wait_timeout(monkeypatch):
    calls = []

    class Process:
        returncode = None
        def communicate(self, timeout):
            calls.append(timeout)
            if timeout == 10:
                raise traffic.subprocess.TimeoutExpired("fake-adb", timeout)
            self.returncode = -1
            return "", ""
        def poll(self): return self.returncode
        def terminate(self): calls.append("terminate")

    monkeypatch.setattr(traffic.subprocess, "Popen", lambda *args, **kw: Process())
    monkeypatch.setattr(traffic.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(traffic, "wifi_readback", lambda *args: {})
    monkeypatch.setattr(traffic, "burst_sender", lambda *args: {"interrupted": True})
    args = SimpleNamespace(adb="fake", serial="fake", receiver="fake", port=45201,
                           ip="192.0.2.1", mbps=1, on_ms=400, off_ms=1600, seconds=4,
                           hz=90, start_delay_s=0)
    result = traffic.run(args)
    assert calls == [10, "terminate", 5]
    assert result["receiver"] is None and result["interrupted"]
