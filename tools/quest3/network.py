"""Opt-in UDP and frame-paced TCP transport probes.

TCP delivery is measured only when ``tcpframerecv`` ACKs a fully-read frame. Local
``sendall()`` completion is intentionally not reported as remote delivery. The ACK
turnaround includes the return path and receiver scheduling; it is not one-way
latency, decode time, display time, or an ALVR transport replacement.
"""
import argparse
import ipaddress
import json
import re
import socket
import subprocess
import threading
import time
from pathlib import Path

from .bench import adb_run, snapshot

PORT = 45200
TCP_HEADER_MAGIC = b"Q3TF"
TCP_ACK_MAGIC = b"Q3TA"
TCP_MAX_FRAME_BYTES = 8 << 20


def percentile(values, fraction):
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    index = (len(ordered) - 1) * fraction
    low = int(index)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (index - low)


def frame_byte_cap(mbps, hz):
    """The live fixed-rate byte budget per video frame, never a goodput claim."""
    if not isinstance(mbps, int) or mbps < 1 or not isinstance(hz, int) or not 1 <= hz <= 240:
        raise ValueError("Mbps must be a positive integer and Hz must be in [1, 240]")
    cap = mbps * 1_000_000 // 8 // hz
    if cap > TCP_MAX_FRAME_BYTES:
        raise ValueError("frame byte cap exceeds the TCP probe safety limit")
    return cap


def summarize_frame_sizes(byte_counts):
    values = [int(value) for value in byte_counts if isinstance(value, (int, float)) and value >= 0]
    return {"sample_count": len(values), "p50_bytes": percentile(values, .50),
            "p99_bytes": percentile(values, .99), "max_bytes": max(values) if values else None}


def parse_wifi_status(text):
    """Extract non-identifying link fields from read-only Android Wi-Fi output."""
    result = {"link_rate_mbps": None, "band": None, "channel": None, "channel_width_mhz": None}
    if not text:
        return result
    # dumpsys also contains historical scans. Never use those as the current link.
    marker = re.search(r"(?:mWifiInfo|WifiInfo)\s*[:=]", text, flags=re.IGNORECASE)
    if marker:
        text = text[marker.start():marker.start() + 1600]
    elif "scanresult" in text.lower():
        return result
    patterns = {
        "link_rate_mbps": r"(?:link\s*speed|linkSpeedMbps)\s*[:=]\s*(\d+)\s*(?:Mbps|Mb/s)?",
        "channel": r"(?:channel(?:\s*number)?)\s*[:=]\s*(\d+)",
        "channel_width_mhz": r"(?:channel\s*width|channelWidth)\s*[:=]\s*(\d+)\s*MHz",
        "channel_width_enum": r"(?:channelBandwidth|channel\s*bandwidth)\s*[:=]\s*([0-5])\b",
        "band": r"(?:band|wifi\s*standard\s*band)\s*[:=]\s*([256])\s*(?:GHz|ghz)",
        "frequency": r"(?:frequency|freq)\s*[:=]\s*(\d+)\s*MHz",
    }
    found = {name: re.search(pattern, text, flags=re.IGNORECASE) for name, pattern in patterns.items()}
    for key in ("link_rate_mbps", "channel", "channel_width_mhz"):
        if found[key]:
            result[key] = int(found[key].group(1))
    if found["band"]:
        result["band"] = found["band"].group(1) + " GHz"
    elif found["frequency"]:
        frequency = int(found["frequency"].group(1))
        if 2400 <= frequency < 2500:
            result["band"] = "2.4 GHz"
            result["channel"] = 14 if frequency == 2484 else (frequency - 2407) // 5
        elif 4900 <= frequency < 5900:
            result["band"] = "5 GHz"
            result["channel"] = (frequency - 5000) // 5
        elif 5925 <= frequency < 7125:
            result["band"] = "6 GHz"
            result["channel"] = (frequency - 5950) // 5
    if result["channel_width_mhz"] is None and found["channel_width_enum"]:
        # Android WifiInfo.ScanResult channel-width constants: 0/1/2/3/4/5 are
        # 20/40/80/160/80+80/320 MHz. Keep 80+80 explicit rather than pretending
        # it is a contiguous 160 MHz channel.
        result["channel_width_mhz"] = {0: 20, 1: 40, 2: 80, 3: 160, 4: "80+80", 5: 320}[int(found["channel_width_enum"].group(1))]
    return result


def _serial_args(serial):
    return ("-s", serial) if serial else ()


def wifi_readback(adb, serial):
    """Read Wi-Fi state without retaining identifying Android command output."""
    commands = (("cmd_wifi_status", ("shell", "cmd", "wifi", "status")),
                ("dumpsys_wifi", ("shell", "dumpsys", "wifi")))
    parsed, command_status = [], {}
    for name, command in commands:
        try:
            output = adb_run(adb, *_serial_args(serial), *command)
            command_status[name] = "ok"
            parsed.append(parse_wifi_status(output))
        except (RuntimeError, subprocess.TimeoutExpired):
            command_status[name] = "error"
    result = {"link_rate_mbps": None, "band": None, "channel": None, "channel_width_mhz": None,
              "command_status": command_status}
    for fields in parsed:
        for key in ("link_rate_mbps", "band", "channel", "channel_width_mhz"):
            if result[key] is None and fields[key] is not None:
                result[key] = fields[key]
    return result


def _recv_exact(sock, size):
    chunks = []
    remaining = size
    while remaining:
        chunk = sock.recv(remaining)
        if not chunk:
            raise RuntimeError("TCP frame receiver closed before its ACK")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def tcp_sender(ip, port, mbps, seconds, hz, connect=socket.create_connection, clock=time.perf_counter,
               sleeper=time.sleep, max_in_flight=3):
    """Write one capped frame at each deadline and wait for its receiver ACK.

    Waiting prevents local socket buffering from masquerading as remote delivery.
    A late ACK skips missed deadlines rather than creating a catch-up burst.
    """
    payload_bytes = frame_byte_cap(mbps, hz)
    period = 1.0 / hz
    payload = bytes(payload_bytes)
    if max_in_flight < 1:
        raise ValueError("max_in_flight must be positive")
    ack_times_ms, schedule_lag_ms, acked, pending_ids = [], [], {}, set()
    lock, stopped = threading.Lock(), threading.Event()
    scheduled = max(0, int(seconds * hz))
    with connect((str(ip), port), timeout=10) as sock:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.settimeout(10)
        # Connection setup is intentionally outside the measured interval.
        def reader():
            pending = b""
            while not stopped.is_set():
                try:
                    chunk = sock.recv(4096)
                except socket.timeout:
                    continue
                if not chunk:
                    return
                pending += chunk
                while len(pending) >= 8:
                    ack, pending = pending[:8], pending[8:]
                    if ack[:4] != TCP_ACK_MAGIC:
                        stopped.set(); return
                    with lock:
                        item = acked.get(int.from_bytes(ack[4:], "big"))
                        if item is not None and item["ack"] is None:
                            item["ack"] = clock()
                            pending_ids.discard(int.from_bytes(ack[4:], "big"))
        worker = threading.Thread(target=reader, daemon=True)
        worker.start()
        start = clock()
        for frame_id in range(scheduled):
            deadline = start + frame_id * period
            now = clock()
            if now < deadline:
                sleeper(deadline - now)
            write_start = clock()
            schedule_lag_ms.append(max(0.0, write_start - deadline) * 1000.0)
            with lock:
                inflight = len(pending_ids)
            if write_start > deadline + period or inflight >= max_in_flight:
                continue
            header = TCP_HEADER_MAGIC + frame_id.to_bytes(4, "big") + payload_bytes.to_bytes(4, "big")
            with lock:
                acked[frame_id] = {"start": write_start, "deadline": deadline + period, "ack": None}
                pending_ids.add(frame_id)
            try:
                sock.sendall(header); sock.sendall(payload)
            except OSError:
                break
        drain_deadline = clock() + period
        while clock() < drain_deadline:
            with lock:
                if not pending_ids: break
            sleeper(min(.001, max(0, drain_deadline - clock())))
        stopped.set(); worker.join(timeout=.2)
    with lock:
        completed = list(acked.values())
    for item in completed:
        if item["ack"] is not None:
            ack_times_ms.append((item["ack"] - item["start"]) * 1000.0)
    on_time = sum(item["ack"] is not None and item["ack"] <= item["deadline"] for item in completed)
    written = len(completed)
    acknowledged = sum(item["ack"] is not None for item in completed)
    late = scheduled - on_time
    elapsed = max(clock() - start, 0.0)
    return {"target_mbps": mbps, "seconds": elapsed, "hz": hz, "frame_period_ms": period * 1000.0,
            "frame_byte_cap": payload_bytes, "scheduled_frames": scheduled, "frames_written": written, "frames_acknowledged": acknowledged,
            "skipped_frame_deadlines": scheduled - written, "ack_delivery_ms_p50": percentile(ack_times_ms, .50),
            "ack_delivery_ms_p99": percentile(ack_times_ms, .99),
            "ack_delivery_ms_p99_9": percentile(ack_times_ms, .999),
            "longest_ack_delivery_stall_ms": max(ack_times_ms) if ack_times_ms else None,
            "schedule_lag_ms_p99": percentile(schedule_lag_ms, .99),
            "frames_on_time_against_period": on_time, "frames_late_against_period": late,
            "late_frame_share_percent": 100.0 * late / scheduled if scheduled else None,
            "acknowledged_payload_mbps": (acknowledged * payload_bytes * 8 / elapsed / 1e6) if elapsed else None,
            "delivery_semantics": "sender write start to ACK after the receiver fully read the frame; includes return path and receiver scheduling, not one-way/decode/presentation"}


def run_udp(adb, serial, ip, sender, receiver, mbps, seconds, hz):
    before = snapshot(adb, serial)
    proc = subprocess.Popen([adb, *_serial_args(serial), "shell", receiver, str(PORT), str(seconds + 3),
                             "--deadline-us", str(round(1e6 / hz))], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True)
    try:
        time.sleep(.5)
        sending = subprocess.run([str(sender), str(ip), str(PORT), str(mbps), str(seconds), str(hz)],
                                 capture_output=True, text=True, timeout=seconds + 20)
        if sending.returncode:
            raise RuntimeError("Native sender failed: " + sending.stderr + sending.stdout)
        received, error = proc.communicate(timeout=10)
        if proc.returncode:
            raise RuntimeError("Android receiver failed: " + error)
        sent, rx = json.loads(sending.stdout), json.loads(received)
    finally:
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=5)
    loss = max(0, sent["sent_packets"] - rx["received"])
    return {"schema_version": 1, "type": "network_only_udp", "sender": sent, "receiver": rx,
            "loss_percent": 100 * loss / sent["sent_packets"] if sent["sent_packets"] else None,
            "delivered_mbps_normalized_to_sender_window": rx["bytes"] * 8 / sent["seconds"] / 1e6,
            "frames_on_time_percent_of_sent": 100 * rx.get("frames_complete_on_time", 0) / sent["frames_sent"] if sent["frames_sent"] else None,
            "state_before": before, "state_after": snapshot(adb, serial), "one_way_latency_ms": None,
            "method": "1400-byte frame bursts. Sender and receiver clocks are unsynchronized; deadline is relative to first received packet. Normalized Mbps integrates received bytes over sender duration."}


def run_tcp(adb, serial, ip, receiver, mbps, seconds, hz):
    wifi_before = wifi_readback(adb, serial)
    proc = subprocess.Popen([adb, *_serial_args(serial), "shell", receiver, str(PORT), str(seconds + 8)], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True)
    try:
        time.sleep(.5)
        sender = tcp_sender(ip, PORT, mbps, seconds, hz)
        received, error = proc.communicate(timeout=10)
        if proc.returncode:
            raise RuntimeError("Android TCP receiver failed: " + error)
        rx = json.loads(received)
    finally:
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=5)
    if sender["frames_acknowledged"] != rx.get("acks_sent"):
        raise RuntimeError("sender and receiver ACK counts do not match")
    return {"schema_version": 2, "type": "network_only_tcp_frame_paced", "sender": sender, "receiver": rx,
            "wifi_before": wifi_before, "wifi_after": wifi_readback(adb, serial),
            "frame_size_bytes": summarize_frame_sizes([sender["frame_byte_cap"]] * sender["frames_written"]),
            "one_way_latency_ms": None,
            "method": "One capped synthetic TCP frame per scheduled period, with a receiver ACK after complete read. ACK turnaround is a delivery bound, not one-way/decode/presentation latency."}


# Compatibility for callers of the original UDP-only helper.
run = run_udp


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb", default="adb")
    parser.add_argument("--serial", required=True, help="pinned Quest ADB serial; refuses default-device selection")
    parser.add_argument("--ip", required=True, type=ipaddress.IPv4Address)
    parser.add_argument("--transport", choices=("udp", "tcp"), default="udp")
    parser.add_argument("--sender", default=str(Path(__file__).with_name("network_sender.exe")))
    parser.add_argument("--receiver", default="/data/local/tmp/q3pw/udprecv-android")
    parser.add_argument("--tcp-receiver", default="/data/local/tmp/q3pw/tcpframerecv-android")
    parser.add_argument("--rates", type=int, nargs="+", default=[600, 800, 1000, 1500, 2000])
    parser.add_argument("--seconds", type=int, default=10)
    parser.add_argument("--hz", type=int, default=90)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    if not 1 <= args.seconds <= 900 or not 1 <= args.hz <= 240 or any(rate < 1 or rate > 2000 for rate in args.rates):
        parser.error("Invalid test bounds")
    if args.transport == "tcp":
        for rate in args.rates:
            try:
                frame_byte_cap(rate, args.hz)
            except ValueError as error:
                parser.error(str(error))
    root = Path(args.out)
    root.mkdir(parents=True, exist_ok=False)
    rows = []
    for rate in args.rates:
        row = (run_udp(args.adb, args.serial, args.ip, args.sender, args.receiver, rate, args.seconds, args.hz)
               if args.transport == "udp" else run_tcp(args.adb, args.serial, args.ip, args.tcp_receiver, rate, args.seconds, args.hz))
        rows.append(row)
        (root / f"{args.transport}-{rate}.json").write_text(json.dumps(row, indent=2) + "\n", encoding="utf-8")
        if args.transport == "udp":
            display = {key: row[key] for key in ("loss_percent", "delivered_mbps_normalized_to_sender_window", "frames_on_time_percent_of_sent")}
        else:
            display = {key: row["sender"][key] for key in ("ack_delivery_ms_p99", "late_frame_share_percent", "longest_ack_delivery_stall_ms")}
        print(json.dumps(display), flush=True)
        time.sleep(2)
    (root / "summary.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
