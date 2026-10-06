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
             "stable-baseline-alvr.patch", "fork-identity-alvr.patch", "wo8-foveation.patch",
             "wo8-light-centre-phase.patch")
    positions = [script.index(name) for name in names]
    assert positions == sorted(positions)


def test_fetch_script_applies_rdo_density_after_the_pyrowave_overlays():
    script = (REPO / "tools/ci/fetch_sources.sh").read_text()
    names = ("pyrowave-cdf53-haar-experiments2-3.patch", "quest3-pyrowave.patch",
             "pyrowave-rdo-density.patch", "pyrowave-rdo-live-readback.patch",
             "pyrowave-rdo-session-setting.patch")
    positions = [script.index(f'apply_patch "$dest/pyrowave" "$repo/patches/{name}"') for name in names]
    assert positions == sorted(positions)
    assert (REPO / "patches/pyrowave-rdo-density.patch").is_file()
    import hashlib
    expected = LOCK["patches"]["pyrowave_rdo_density"]
    assert expected["path"] == "patches/pyrowave-rdo-density.patch"
    assert expected["sha256"] == hashlib.sha256((REPO / expected["path"]).read_bytes()).hexdigest()


def test_live_rdo_readback_patches_are_pinned_and_applied_after_their_stacks():
    import hashlib
    script = (REPO / "tools/ci/fetch_sources.sh").read_text()
    for key, path in (
        ("pyrowave_rdo_live_readback", "patches/pyrowave-rdo-live-readback.patch"),
        ("pyrowave_rdo_session_setting", "patches/pyrowave-rdo-session-setting.patch"),
        ("alvr_pyrowave_rdo_live_readback", "patches/alvr-pyrowave-rdo-live-readback.patch"),
        ("alvr_pyrowave_rdo_session_setting", "patches/alvr-pyrowave-rdo-session-setting.patch"),
    ):
        expected = LOCK["patches"][key]
        assert expected["path"] == path
        assert expected["sha256"] == hashlib.sha256((REPO / path).read_bytes()).hexdigest()
    assert (script.index('apply_patch "$dest/pyrowave" "$repo/patches/pyrowave-rdo-density.patch"')
            < script.index('apply_patch "$dest/pyrowave" "$repo/patches/pyrowave-rdo-live-readback.patch"'))
    assert (script.index('apply_patch "$dest/pyrowave" "$repo/patches/pyrowave-rdo-live-readback.patch"')
            < script.index('apply_patch "$dest/pyrowave" "$repo/patches/pyrowave-rdo-session-setting.patch"'))
    assert (script.index('apply_patch "$dest/ALVR-20.13.0" "$repo/patches/wo8-light-centre-phase.patch"')
            < script.index('apply_patch "$dest/ALVR-20.13.0" "$repo/patches/alvr-pyrowave-rdo-live-readback.patch"'))
    assert (script.index('apply_patch "$dest/ALVR-20.13.0" "$repo/patches/alvr-pyrowave-rdo-live-readback.patch"')
            < script.index('apply_patch "$dest/ALVR-20.13.0" "$repo/patches/alvr-pyrowave-rdo-session-setting.patch"'))


def test_foveation_linkage_fix_is_pinned_and_checked_in_cpu_ci():
    import hashlib

    expected = LOCK['patches']['foveation_shader_linkage']
    assert expected['path'] == 'patches/foveation-shader-linkage.patch'
    assert expected['sha256'] == hashlib.sha256((REPO / expected['path']).read_bytes()).hexdigest()
    script = (REPO / 'tools/ci/fetch_sources.sh').read_text()
    assert script.index('direct-eye-foveation.patch') < script.index('foveation-shader-linkage.patch')
    assert script.index('--value foveation_shader_linkage_patch_sha256') < script.index(
        'apply_patch "$dest/ALVR-20.13.0" "$repo/patches/foveation-shader-linkage.patch"')
    workflow = (REPO / '.github/workflows/ci.yml').read_text()
    assert 'python3 tools/ci/check_foveation_linkage.py' in workflow
    warp = (REPO / 'tools/windows/check_quality_shaders.cmd').read_text()
    assert 'QuadVertexShader.cso' in warp


def test_light_phase_patch_is_pinned_and_verified_before_application():
    import hashlib
    expected = LOCK["patches"]["wo8_light_centre_phase"]
    assert expected["path"] == "patches/wo8-light-centre-phase.patch"
    patch = REPO / expected["path"]
    assert patch.is_file()
    assert expected["sha256"] == hashlib.sha256(patch.read_bytes()).hexdigest()
    script = (REPO / "tools/ci/fetch_sources.sh").read_text()
    assert script.index("wo8-foveation.patch") < script.index("wo8-light-centre-phase.patch")
    assert "--value wo8_light_centre_phase_patch_sha256" in script


def test_source_lock_rejects_malformed_light_phase_pin(tmp_path):
    sys.path.insert(0, str(REPO / "tools/ci"))
    try:
        import source_lock
    finally:
        sys.path.pop(0)
    duplicate = json.loads(json.dumps(LOCK))
    duplicate["patches"]["wo8_light_centre_phase"]["sha256"] = "not-a-sha"
    duplicate_path = tmp_path / "sources.lock.json"
    duplicate_path.write_text(json.dumps(duplicate), encoding="utf-8")
    original = source_lock.LOCK
    source_lock.LOCK = duplicate_path
    try:
        with pytest.raises(SystemExit, match="wo8_light_centre_phase"):
            source_lock.load()
    finally:
        source_lock.LOCK = original


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
    assert actual["WO8_LIGHT_CENTRE_PHASE_PATCH_SHA256"] == LOCK["patches"]["wo8_light_centre_phase"]["sha256"]


def test_toolchain_is_read_from_the_lock_by_posix_builds():
    script = (REPO / "tools/build_alvr_2013.sh").read_text()
    assert "source_lock.py" in script
    assert "--value rust" in script
    assert "--value android_ndk" in (REPO / "tools/build_pyrowave_android.sh").read_text()


def test_stable_windows_build_uses_the_reconstructed_locked_pyrowave_tree():
    script = (REPO / "tools/windows/build_pyrowave_pc.cmd").read_text()
    assert 'set "PW=%WS%\\research\\pyrowave"' in script
    assert "XRWIRED_PYROWAVE" not in script
    assert "pyrowave-rdo-density-test" in script
