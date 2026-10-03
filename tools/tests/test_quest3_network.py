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
    def __init__(self, ack):
        self.ack = ack
        self.sent = []
        self.timeout = None

    def __enter__(self):
        return self

    def __exit__(self, *unused):
        return False

    def settimeout(self, value):
        self.timeout = value

    def setsockopt(self, *unused):
        pass

    def sendall(self, data):
        self.sent.append(data)

    def recv(self, count):
        out, self.ack = self.ack[:count], self.ack[count:]
        return out


class _Tick:
    def __init__(self):
        self.value = 0.0

    def __call__(self):
        self.value += .001
        return self.value


def test_tcp_sender_counts_receiver_ack_not_local_write_completion():
    sock = _FakeSocket(b"Q3TA" + (0).to_bytes(4, "big"))
    ticks = _Tick()
    result = network.tcp_sender("192.0.2.1", 45200, 1, .02, 90,
                                connect=lambda *unused, **kwargs: sock,
                                clock=ticks, sleeper=lambda _seconds: None)
    assert result["scheduled_frames"] == 1
    assert result["frames_written"] == 1
    assert result["frames_acknowledged"] <= result["frames_written"]
    assert result["late_frame_share_percent"] >= 0.0
    assert len(sock.sent) == 2 and sock.sent[0][:4] == b"Q3TF"
    assert "not one-way/decode/presentation" in result["delivery_semantics"]


def test_tcp_sender_marks_unacknowledged_scheduled_frame_late():
    sock = _FakeSocket(b"Q3TA" + (4).to_bytes(4, "big"))
    ticks = _Tick()
    result = network.tcp_sender("192.0.2.1", 45200, 1, .02, 90,
                                connect=lambda *unused, **kwargs: sock,
                                clock=ticks, sleeper=lambda _seconds: None)
    assert result["scheduled_frames"] == 1
    assert result["frames_on_time_against_period"] == 0
    assert result["late_frame_share_percent"] == 100.0


def test_backpressure_counts_every_deadline_instead_of_hiding_skipped_frames():
    sock = _FakeSocket(b"")
    result = network.tcp_sender("192.0.2.1", 45200, 1, .04, 90,
                                connect=lambda *unused, **kwargs: sock,
                                clock=_Tick(), sleeper=lambda _seconds: None,
                                max_in_flight=1)
    assert result["scheduled_frames"] == 3
    assert result["frames_written"] == 1
    assert result["skipped_frame_deadlines"] == 2
    assert result["frames_late_against_period"] == 3
    assert result["late_frame_share_percent"] == 100.0
