"""The owner's eight-hour approval applies only to the recorded once window."""
import copy
import json
from datetime import datetime, timezone

import pytest
from tools.quest3 import unattended as u


def approved_arm():
    entry = u.json_read(u.ROOT / 'presets' / 'unattended-owner-exceptions.json')['once_windows'][0]
    return {key: copy.deepcopy(entry[key]) for key in (
        'mode', 'timezone', 'not_before_local', 'not_after_local', 'expires_local', 'allow')
    } | {'schema': 1, 'headset_serial': 'fixture-only', 'max_window_hours': 6}


def test_exact_owner_exception_is_recorded_and_does_not_mutate_arm():
    arm = approved_arm()
    before = json.dumps(arm, sort_keys=True)
    result = u.arm_window(arm, datetime(2026, 10, 3, 0, 0, tzinfo=timezone.utc))
    assert result['duration_authorization']['hours'] == 8
    assert result['duration_authorization']['exception_id']
    assert result['deadline'] == datetime(2026, 10, 3, 6, 44, 31, tzinfo=timezone.utc)
    assert json.dumps(arm, sort_keys=True) == before
    assert u.MAX_HOURS == 6


@pytest.mark.parametrize('change', [
    {'allow': ['chart_cells']},
    {'allow': ['frame_bank_pc', 'install_matching_pair']},
    {'not_after_local': '2026-10-03T09:44:31'},
    {'expires_local': '2026-10-04T08:44:31'},
    {'not_before_local': '2026-10-04T00:44:31', 'not_after_local': '2026-10-04T08:44:31',
     'expires_local': '2026-10-04T08:44:31'},
    {'max_window_hours': 8},
])
def test_exception_cannot_authorize_other_actions_or_intervals(change):
    arm = approved_arm() | change
    with pytest.raises(u.Refusal): u.validate_arm_definition(arm)


def test_ordinary_six_hour_once_window_remains_valid():
    arm = approved_arm() | {'not_after_local': '2026-10-03T06:44:31'}
    u.validate_arm_definition(arm)
    assert u.effective_window_limit(arm)['exception_id'] is None


def test_nightly_window_does_not_inherit_once_exception():
    arm = approved_arm() | {'mode': 'nightly', 'start_local': '00:00', 'end_local': '08:00'}
    with pytest.raises(u.Refusal): u.validate_arm_definition(arm)
