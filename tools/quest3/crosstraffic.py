"""Opt-in on/off TCP airtime competition; ACK turnaround is not one-way latency.

tcpframerecv has a 1 s per-recv idle limit. Off-windows and the start delay use
64-byte protocol keep-alives every 250 ms, subject to the shared in-flight cap.
Keep-alives and their ACKs are counted separately and excluded from burst stats.
"""
import argparse
import ipaddress
import json
import math
import socket
import subprocess
import threading
import time
from pathlib import Path

from .network import (TCP_ACK_MAGIC, TCP_HEADER_MAGIC, _serial_args,
                      frame_byte_cap, percentile, wifi_readback)


class _Acks:
    def __init__(self):
        self.lock = threading.Lock()
        self.frames, self.pending, self.buffer = {}, set(), b""
        self.error = None

    def feed(self, chunk, now):
        with self.lock:
            self.buffer += chunk
            while len(self.buffer) >= 8:
                ack, self.buffer = self.buffer[:8], self.buffer[8:]
                frame_id = int.from_bytes(ack[4:], "big")
                if ack[:4] != TCP_ACK_MAGIC:
                    self.error = "invalid_receiver_ack"
                    return
                if frame_id not in self.pending:
                    self.error = "unknown_or_duplicate_ack"
                    return
                self.frames[frame_id]["ack"] = now
                self.pending.remove(frame_id)


def _read_acks(sock, state, stopped, clock):
    while not stopped.is_set():
        try:
            chunk = sock.recv(4096)
        except socket.timeout:
            continue
        except OSError:
            if not stopped.is_set(): state.error = "receiver_socket_error"
            return
        if not chunk:
            if not stopped.is_set(): state.error = "receiver_closed"
            return
        state.feed(chunk, clock())
        if state.error: return


def burst_sender(ip, port, mbps, on_ms, off_ms, seconds, hz=90, start_delay_s=0,
                 connect=socket.create_connection, clock=time.perf_counter,
                 sleeper=time.sleep, unix_ns=time.time_ns):
    payload_bytes = frame_byte_cap(mbps, hz)
    if (not all(math.isfinite(v) for v in (on_ms, off_ms, seconds, start_delay_s))
            or on_ms <= 0 or off_ms < 0 or seconds <= 0 or start_delay_s < 0):
        raise ValueError("positive on-ms/seconds and nonnegative off-ms/start-delay-s required")
    on, cycle, period = on_ms / 1000, (on_ms + off_ms) / 1000, 1 / hz
    payload, state, stopped = bytes(payload_bytes), _Acks(), threading.Event()
    bursts, skipped, interrupted, frame_id = [], 0, False, 0
    keepalive_skipped = 0
    with connect((str(ip), port), timeout=10) as sock:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.settimeout(1)
        worker = threading.Thread(target=_read_acks, args=(sock, state, stopped, clock), daemon=True)
        worker.start()
        origin, epoch_ns = clock(), unix_ns()
        start = origin + start_delay_s
        end = start + seconds
        burst = None

        def write(data, keepalive=False):
            nonlocal frame_id
            with state.lock:
                if len(state.pending) >= 3: return False
                state.frames[frame_id] = {"start": clock(), "ack": None,
                                          "written": False, "keepalive": keepalive}
                state.pending.add(frame_id)
            header = TCP_HEADER_MAGIC + frame_id.to_bytes(4, "big") + len(data).to_bytes(4, "big")
            try:
                sock.sendall(header); sock.sendall(data)
            except OSError:
                # A partial frame makes all subsequent headers ambiguous.
                state.error = "partial_or_timed_out_write"
                return False
            state.frames[frame_id]["written"] = True
            frame_id += 1
            return True

        def idle_until(deadline):
            nonlocal keepalive_skipped
            tick = clock() + .25
            while tick < deadline and not state.error:
                sleeper(max(0, tick - clock()))
                if state.error: return
                if clock() >= deadline or clock() >= tick + .25 or not write(bytes(64), keepalive=True):
                    if state.error: return
                    keepalive_skipped += 1
                tick += .25
            if not state.error: sleeper(max(0, deadline - clock()))

        try:
            index = 0
            while start + index * cycle < end and not state.error:
                begin = start + index * cycle
                finish = min(begin + on, end)
                idle_until(begin)
                if state.error: break
                burst = {"start_unix_ns": epoch_ns + round((begin - origin) * 1e9),
                         "end_unix_ns": epoch_ns + round((finish - origin) * 1e9),
                         "frames_sent": 0, "frames_skipped": 0}
                bursts.append(burst)
                slot = 0
                slots = math.ceil((finish - begin) * hz - 1e-9)
                while slot < slots:
                    deadline = begin + slot * period
                    sleeper(max(0, deadline - clock()))
                    now = clock()
                    if state.error: break
                    if now >= finish or now > deadline + period or not write(payload):
                        if state.error: break
                        skipped += 1
                        burst["frames_skipped"] += 1
                    else:
                        burst["frames_sent"] += 1
                    slot += 1
                if state.error: break
                sleeper(max(0, finish - clock()))
                print(f"burst {index + 1}: sent={burst['frames_sent']} skipped={burst['frames_skipped']}", flush=True)
                burst = None
                index += 1
            if not state.error:
                idle_until(end)
            drain_end = clock() + 1
            while state.pending and not state.error and clock() < drain_end:
                sleeper(min(.001, max(0, drain_end - clock())))
        except KeyboardInterrupt:
            interrupted = True
        finally:
            if burst is not None:
                burst["end_unix_ns"] = min(burst["end_unix_ns"], epoch_ns + round((clock() - origin) * 1e9))
                print(f"burst {len(bursts)}: sent={burst['frames_sent']} skipped={burst['frames_skipped']}", flush=True)
            stopped.set()
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            worker.join(timeout=1.5)
            if worker.is_alive(): state.error = "receiver_thread_not_stopped"
    frames = [f for f in state.frames.values() if not f["keepalive"]]
    keepalives = [f for f in state.frames.values() if f["keepalive"]]
    ack_ms = [(f["ack"] - f["start"]) * 1000 for f in frames if f["ack"] is not None]
    sent = sum(f["written"] for f in frames)
    on_seconds = sum((b["end_unix_ns"] - b["start_unix_ns"]) / 1e9 for b in bursts)
    return {"schema_version": 1, "type": "tcp_cross_traffic", "pattern": {
                "mbps": mbps, "on_ms": on_ms, "off_ms": off_ms, "seconds": seconds,
                "hz": hz, "start_delay_s": start_delay_s},
            "frame_bytes": payload_bytes, "bursts_sent": sum(b["frames_sent"] > 0 for b in bursts),
            "bursts": bursts, "frames_sent": sent, "frames_acked": len(ack_ms),
            "frames_skipped": skipped, "partial_frames": len(frames) - sent,
            "keepalive_frames_sent": sum(f["written"] for f in keepalives),
            "keepalive_frames_acked": sum(f["ack"] is not None for f in keepalives),
            "keepalive_frames_skipped": keepalive_skipped,
            "keepalive_partial_frames": sum(not f["written"] for f in keepalives),
            "on_seconds": on_seconds,
            "achieved_on_mbps": sent * payload_bytes * 8 / on_seconds / 1e6 if on_seconds else None,
            "acked_payload_on_mbps": len(ack_ms) * payload_bytes * 8 / on_seconds / 1e6 if on_seconds else None,
            "ack_ms_p50": percentile(ack_ms, .50), "ack_ms_p99": percentile(ack_ms, .99),
            "ack_ms_max": max(ack_ms) if ack_ms else None,
            "receiver_error": state.error, "interrupted": interrupted,
            "rate_semantics": "burst payload normalized to on-windows; achieved counts complete local writes, acked counts receiver ACKs (possibly arriving off-window); excludes keep-alives"}


def run(args):
    wifi = wifi_readback(args.adb, args.serial)
    duration = args.seconds + args.start_delay_s + 10
    proc = subprocess.Popen([args.adb, *_serial_args(args.serial), "shell", args.receiver,
                             str(args.port), str(duration)], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True)
    try:
        time.sleep(.5)
        result = burst_sender(args.ip, args.port, args.mbps, args.on_ms, args.off_ms,
                              args.seconds, args.hz, args.start_delay_s)
        try:
            received, error = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            proc.terminate()
            received, error = proc.communicate(timeout=5)
        try:
            result["receiver"] = json.loads(received)
        except json.JSONDecodeError:
            result["receiver"] = None
        result["receiver_returncode"] = proc.returncode
        result["receiver_stderr"] = error
        result["wifi_before"] = wifi
        result["wifi_after"] = wifi_readback(args.adb, args.serial)
        return result
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb", default="adb")
    parser.add_argument("--serial", required=True)
    parser.add_argument("--ip", required=True, type=ipaddress.IPv4Address)
    parser.add_argument("--port", type=int, default=45201)
    parser.add_argument("--receiver", default="/data/local/tmp/q3pw/tcpframerecv-android")
    for name, kind in (("mbps", int), ("on-ms", float), ("off-ms", float), ("seconds", float)):
        parser.add_argument("--" + name, type=kind, required=True)
    parser.add_argument("--hz", type=int, default=90)
    parser.add_argument("--start-delay-s", type=float, default=0)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    try:
        frame_byte_cap(args.mbps, args.hz)
        if (not all(math.isfinite(v) for v in (args.on_ms, args.off_ms, args.seconds, args.start_delay_s))
                or not 1 <= args.port <= 65535 or args.port == 45200
                or args.on_ms <= 0 or args.off_ms < 0 or not 0 < args.seconds <= 900
                or not 0 <= args.start_delay_s <= 900
                or args.seconds + args.start_delay_s > 900):
            raise ValueError("Invalid test bounds (port 45200 is reserved for network.py)")
    except ValueError as error:
        parser.error(str(error))
    result = run(args)
    Path(args.out).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
