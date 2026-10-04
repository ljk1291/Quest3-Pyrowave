"""CPU contracts for the opt-in TCP transport probe; no ADB or network I/O."""
from tools.quest3 import network


def test_tcp_frame_cap_matches_the_live_rate_budget():
    assert network.frame_byte_cap(1000, 90) == 1_388_888
    assert network.frame_byte_cap(700, 90) == 972_222


def test_frame_size_summary_exposes_variable_live_cell_stats():
    summary = network.summarize_frame_sizes([100, 200, 600, 900])
    assert summary == {"sample_count": 4, "p50_bytes": 400.0, "p99_bytes": 891.0, "max_bytes": 900}


def test_wifi_parser_discards_identifiers_and_derives_band_from_frequency():
    status = "SSID: private-network\nBSSID: aa:bb:cc:dd:ee:ff\nFrequency: 5745MHz\nLink speed: 2401Mbps\nChannel: 149\nChannel width: 160MHz"
    assert network.parse_wifi_status(status) == {"link_rate_mbps": 2401, "band": "5 GHz", "channel": 149, "channel_width_mhz": 160}


def test_wifi_parser_leaves_missing_fields_unknown():
    assert network.parse_wifi_status("WifiInfo unavailable") == {"link_rate_mbps": None, "band": None, "channel": None, "channel_width_mhz": None}


def test_wifi_parser_understands_android_channel_width_enum_and_frequency_only_channel():
    parsed = network.parse_wifi_status("frequency=5745MHz linkSpeedMbps=2401 channelBandwidth=3")
    assert parsed == {"link_rate_mbps": 2401, "band": "5 GHz", "channel": 149, "channel_width_mhz": 160}


class _FakeSocket:
    """In-memory TCP peer: ACKs only complete received payloads, never preloads ACKs."""
    def __init__(self, *, ack_delay=0, drop=False, partial=False, bad_ack=False):
        import threading
        self.condition = threading.Condition()
        self.acks = []
        self.sent = []
        self.header = None
        self.closed = False
        self.timeout = 1
        self.delay, self.drop, self.partial, self.bad_ack = ack_delay, drop, partial, bad_ack

    def __enter__(self): return self
    def __exit__(self, *unused): self.shutdown(); return False
    def settimeout(self, value): self.timeout = value
    def setsockopt(self, *unused): pass
    def shutdown(self, *unused):
        with self.condition:
            self.closed = True
            self.condition.notify_all()

    def sendall(self, data):
        import time
        with self.condition:
            self.sent.append(data)
            if self.header is None:
                self.header = data
                return
            if self.partial: raise TimeoutError("partial payload")
            assert len(data) == int.from_bytes(self.header[8:], 'big')
            if not self.drop:
                frame_id = int.from_bytes(self.header[4:8], 'big') + (100 if self.bad_ack else 0)
                self.acks.append((time.perf_counter()+self.delay, b'Q3TA'+frame_id.to_bytes(4, 'big')))
            self.header = None
            self.condition.notify_all()

    def recv(self, count):
        import time
        from socket import timeout
        with self.condition:
            until = time.perf_counter() + self.timeout
            while not self.closed:
                now = time.perf_counter()
                if self.acks and self.acks[0][0] <= now:
                    return self.acks.pop(0)[1]
                if now >= until: raise timeout()
                wake = min(until, self.acks[0][0]) if self.acks else until
                self.condition.wait(max(.0001, wake-now))
            return b''


def _send(sock, **kwargs):
    return network.tcp_sender('192.0.2.1', 45200, 1, .08, 50,
                              connect=lambda *a, **kw: sock, io_timeout_s=.12, **kwargs)


def test_tcp_sender_counts_completed_remote_payloads():
    sock = _FakeSocket()
    result = _send(sock)
    assert result['scheduled_frames'] == 4
    assert result['frames_acknowledged'] == result['frames_written'] > 0
    assert result['receiver_error'] is None
    assert result['partial_frames'] == 0
    assert sock.closed
    assert 'not one-way/decode/presentation' in result['delivery_semantics']


def test_late_ack_is_measured_without_aborting_at_one_frame_period():
    sock = _FakeSocket(ack_delay=.045)
    result = _send(sock)
    assert result['frames_acknowledged'] == result['frames_written'] > 1
    assert result['ack_delivery_ms_p50'] >= 45
    assert result['frames_on_time_against_period'] == 0
    assert result['frames_late_against_period'] == 4
    assert result['receiver_error'] is None
    assert result['stream_incomplete'] is False
    assert sock.timeout > result['frame_period_ms']/1000


def test_backpressure_counts_every_deadline_instead_of_hiding_skipped_frames():
    result = _send(_FakeSocket(drop=True), max_in_flight=1)
    assert result['scheduled_frames'] == 4
    assert result['frames_written'] == 1
    assert result['skipped_frame_deadlines'] == 3
    assert result['frames_late_against_period'] == 4
    assert result['unacknowledged_frames'] == 1
    assert result['censored_stall_lower_bound_ms'] >= 100
    assert result['late_frame_share_percent'] == 100


def test_partial_write_terminates_stream_without_a_second_frame_header():
    sock = _FakeSocket(partial=True)
    result = _send(sock)
    assert result['scheduled_frames'] == 4
    assert result['stream_incomplete'] is True
    assert result['receiver_error'] == 'partial_or_timed_out_write'
    assert result['partial_frames'] == 1 and result['frames_written'] == 0
    assert sum(packet.startswith(b'Q3TF') for packet in sock.sent) == 1
    assert result['frames_late_against_period'] == 4


def test_unknown_ack_invalidates_receiver_instead_of_disappearing():
    result = _send(_FakeSocket(bad_ack=True))
    assert result['receiver_error'] == 'unknown_or_duplicate_ack'
    assert result['frames_acknowledged'] == 0


def test_wifi_parser_preserves_decimal_band():
    assert network.parse_wifi_status('band: 2.4GHz')['band'] == '2.4 GHz'
