"""Offline accounting and timing around 90 Hz target-timestamp gaps.

Targets are tracking keys, not source-image identities. Telemetry deltas use
matching first/last snapshots; GPU sample counts include a different window.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from statistics import median

STAGES = ('decoder_s', 'decoder_queue_s', 'vsync_queue_s', 'network_s',
          'total_pipeline_latency_s')
COUNTERS = ('complete', 'skipped', 'superseded', 'dropped', 'decode_failures',
            'completed_eye_copies', 'pending_eye_copy_deferrals')


def analyze(capture: Path, hz: float = 90) -> dict:
    rows, telemetry = [], []
    with (capture / 'events.jsonl').open(encoding='utf-8-sig') as stream:
        for line in stream:
            if not line.strip():
                continue
            record = json.loads(line)
            event = record.get('event', {}).get('event_type', {})
            if event.get('id') == 'GraphStatistics':
                rows.append((record['capture_elapsed_s'], event['data']))
            elif event.get('id') == 'HeadsetTelemetry' and event['data'].get('pyrowave'):
                telemetry.append((record['capture_elapsed_s'], event['data']['pyrowave']))
    gaps = [round((b['target_timestamp_ns'] - a['target_timestamp_ns']) * hz / 1e9)
            for (_, a), (_, b) in zip(rows, rows[1:])]
    groups = {'all': range(len(rows)),
              'before_x2': [i for i, gap in enumerate(gaps) if gap == 2],
              'after_x2': [i + 1 for i, gap in enumerate(gaps) if gap == 2]}
    timing = {name: {'n': len(indices), **{
        key: round(median(rows[i][1][key] * 1000 for i in indices), 3)
        for key in STAGES}} for name, indices in groups.items() if indices}
    pairs = [(rows[i][1], rows[i + 1][1]) for i, gap in enumerate(gaps) if gap == 2]
    per_second = Counter(int(t) for t, _ in rows)
    deltas, span = {}, None
    if len(telemetry) >= 2:
        span = telemetry[-1][0] - telemetry[0][0]
        for key in COUNTERS:
            if any(b[key] < a[key] for (_, a), (_, b) in zip(telemetry, telemetry[1:])):
                raise ValueError(f'{capture.name}: {key} reset; split capture at stream restart')
            deltas[key] = telemetry[-1][1][key] - telemetry[0][1][key]
    return {
        'capture': capture.name, 'graph_frames': len(rows),
        'gap_multiples': dict(sorted(Counter(gaps).items())),
        'graph_per_complete_second': [per_second[t] for t in range(
            int(rows[0][0]) + 1, int(rows[-1][0]))] if rows else [],
        'median_ms': timing, 'telemetry_span_s': span, 'counter_deltas': deltas,
        'paired_after_minus_before_ms': {
            key: round(median((b[key] - a[key]) * 1000 for a, b in pairs), 3)
            for key in STAGES
        } if pairs else {},
        'decoded_minus_superseded_minus_copied': (
            deltas['complete'] - deltas['superseded'] - deltas['completed_eye_copies']
        ) if deltas else None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('captures', type=Path, nargs='+')
    args = parser.parse_args()
    print(json.dumps([analyze(path) for path in args.captures], indent=2))


if __name__ == '__main__':
    main()
