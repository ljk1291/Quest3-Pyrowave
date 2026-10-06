"""Add frame-loss and opt-in output-queue variants to a session25 harness.

No action occurs on import. Use the same adapter for snapshot/cell/capture/restore
so the added Android properties are included in the harness's restoration set.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
from pathlib import Path

CELLS = ('loss-control500', 'loss-runtime500', 'loss-wait500', 'loss-nopace500',
         'queue2-500', 'queue2-wait-500', 'queue3-500')
PROPERTY_DEFAULTS = {
    'debug.q3pw.frame_loss': '0',
    'debug.q3pw.stats_source_ts': '0',
    'debug.q3pw.output_queue': '1',
    'debug.q3pw.output_queue_max_age_us': '22223',
}
PROPERTIES = tuple(PROPERTY_DEFAULTS)


def install(harness):
    original = harness.profile
    harness.ORDER = (*harness.ORDER, *CELLS)
    harness.MANAGED_PROPERTIES = tuple(dict.fromkeys((*harness.MANAGED_PROPERTIES, *PROPERTIES)))

    def profile(name):
        spec = original('crop-nopace' if name == 'loss-nopace500' else
                        'crop-500' if name in CELLS else name)
        spec['properties'].update(PROPERTY_DEFAULTS)
        if name in CELLS:
            spec['cell'] = name
            spec['seconds'] = 20
            spec['properties']['debug.q3pw.frame_loss'] = '1'
            spec['properties']['debug.q3pw.stats_source_ts'] = '1'
            spec['properties']['debug.q3pw.loop_probe'] = '1'
            spec['properties']['debug.q3pw.decode_workers'] = '1'
            spec['properties']['debug.q3pw.decode_handoff'] = '0'
            if name == 'loss-runtime500':
                spec['properties']['debug.q3pw.runtime_display_time'] = '1'
            elif name == 'loss-wait500':
                spec['properties']['debug.q3pw.frame_wait_us'] = '1000'
            elif name == 'loss-nopace500':
                # Retain the entire 360-entry pose history's potential keys.
                spec['settings']['session_settings.connection.statistics_history_size'] = 1024
            elif name in ('queue2-500', 'queue2-wait-500'):
                spec['properties']['debug.q3pw.output_queue'] = '2'
                if name == 'queue2-wait-500':
                    spec['properties']['debug.q3pw.frame_wait_us'] = '1000'
            elif name == 'queue3-500':
                # Default age bound (22,223 us) would drop the third entry; allow three periods.
                spec['properties']['debug.q3pw.output_queue'] = '3'
                spec['properties']['debug.q3pw.output_queue_max_age_us'] = '33334'
        return spec

    harness.profile = profile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session25', type=Path, required=True)
    args, remaining = parser.parse_known_args()
    spec = importlib.util.spec_from_file_location('session25_frame_loss', args.session25.resolve())
    if spec is None or spec.loader is None:
        parser.error('Cannot load session25 harness')
    harness = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(harness)
    install(harness)
    # Child-process inheritance only; no persistent user/system environment edit.
    old = os.environ.get('ALVR_FRAME_LOSS')
    os.environ['ALVR_FRAME_LOSS'] = '1'
    try:
        return harness.main(remaining)
    finally:
        if old is None:
            os.environ.pop('ALVR_FRAME_LOSS', None)
        else:
            os.environ['ALVR_FRAME_LOSS'] = old


if __name__ == '__main__':
    raise SystemExit(main())
