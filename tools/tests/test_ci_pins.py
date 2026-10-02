"""The lockfile, not workflow environment defaults, defines reconstructed inputs."""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
LOCK = json.loads((REPO / "sources.lock.json").read_text())


def test_lock_has_full_source_revisions():
    for key in ("integration", "alvr", "pyrowave", "granite", "cargo_apk"):
        assert re.fullmatch(r"[0-9a-f]{40}", LOCK[key]["commit"]), key


def test_fork_json_is_the_only_application_identity_authority(tmp_path):
    assert "fork" not in LOCK
    assert not {"protocol_version", "client_package_id", "application_version", "server_version"} & LOCK.keys()
    fork = json.loads((REPO / "fork.json").read_text())
    assert re.fullmatch(r"\d+\.\d+\.\d+-[A-Za-z0-9][A-Za-z0-9.-]*", fork["protocol_version"])
    assert fork["client_package_id"] == "io.github.ljk1291.quest3pyrowave"

    sys.path.insert(0, str(REPO / "tools/ci"))
    try:
        import source_lock
    finally:
        sys.path.pop(0)
    duplicate = dict(LOCK)
    duplicate["protocol_version"] = "stale"
    duplicate_path = tmp_path / "sources.lock.json"
    duplicate_path.write_text(json.dumps(duplicate))
    original = source_lock.LOCK
    source_lock.LOCK = duplicate_path
    try:
        with pytest.raises(SystemExit, match="fork.json is authoritative"):
            source_lock.load()
    finally:
        source_lock.LOCK = original


def test_fetch_script_reads_lock_and_applies_the_complete_alvr_stack_in_order():
    script = (REPO / "tools/ci/fetch_sources.sh").read_text()
    assert "source_lock.py" in script
    names = ("alvr-20.13.0-server-instrumentation.patch", "quest3-alvr.patch",
             "stable-baseline-alvr.patch", "fork-identity-alvr.patch")
    positions = [script.index(name) for name in names]
    assert positions == sorted(positions)


def test_workflow_loads_pins_from_the_lock_before_building():
    workflow = (REPO / ".github/workflows/ci.yml").read_text()
    assert workflow.count("source_lock.py --github-env") >= 3
    assert "ALVR_BASE:" not in workflow
    assert "PYROWAVE_BASE:" not in workflow


def test_lock_emitter_uses_exact_values():
    result = subprocess.run([sys.executable, "tools/ci/source_lock.py", "--github-env"],
                            cwd=REPO, capture_output=True, text=True, check=True)
    actual = dict(line.split("=", 1) for line in result.stdout.splitlines())
    assert actual["ALVR_BASE"] == LOCK["alvr"]["commit"]
    assert actual["PYROWAVE_BASE"] == LOCK["pyrowave"]["commit"]
    assert actual["GRANITE_COMMIT"] == LOCK["granite"]["commit"]


def test_toolchain_is_read_from_the_lock_by_posix_builds():
    script = (REPO / "tools/build_alvr_2013.sh").read_text()
    assert "source_lock.py" in script
    assert "--value rust" in script
    assert "--value android_ndk" in (REPO / "tools/build_pyrowave_android.sh").read_text()


def test_stable_windows_build_uses_the_reconstructed_locked_pyrowave_tree():
    script = (REPO / "tools/windows/build_pyrowave_pc.cmd").read_text()
    assert 'set "PW=%WS%\\research\\pyrowave"' in script
    assert "XRWIRED_PYROWAVE" not in script
