"""The ljk1291 fork's overlays stay pinned and applied, and its identity patch matches fork.json.

A regenerated overlay without a new pin, a pin for a patch fetch_sources.sh never applies, or a
version bump in fork.json that the identity patch does not carry would otherwise surface only in
a CI build (or as a client and server that refuse each other).
"""
import json
import re
import unittest
from pathlib import Path

from tools.ci import source_lock

REPO = Path(__file__).resolve().parents[1]
FORK = json.loads((REPO / 'fork.json').read_text(encoding='utf-8'))


class ForkOverlayTests(unittest.TestCase):
    def test_every_overlay_is_pinned_and_applied(self):
        self.assertEqual(source_lock.problems(), [])

    def test_fork_identity_is_the_first_overlay(self):
        self.assertEqual(source_lock.applied()[0], 'patches/fork-identity-alvr.patch')

    def test_identity_patch_matches_fork_json(self):
        patch = (REPO / 'patches' / 'fork-identity-alvr.patch').read_text(encoding='utf-8')
        version, package = FORK['protocol_version'], FORK['client_package_id']
        self.assertIn(f'+version = "{version}"', patch)
        self.assertIn(f'+package = "{package}"', patch)
        self.assertIn(f'+                Custom: "{package}".to_owned(),', patch)
        # ALVR's protocol ID is "<major>-<pre-release>"; the patch's Rust test pins it.
        self.assertIn('"20-' + version.split('-', 1)[1] + '"', patch)
        # Every workspace crate in Cargo.lock moves to the fork version, none stays behind.
        self.assertEqual(patch.count(f'+version = "{version}"'), patch.count('\n-version = "20.13.0-'))

    def test_fork_json_names_a_full_upstream_commit(self):
        self.assertRegex(FORK['upstream_reference_commit'], r'^[0-9a-f]{40}$')
        self.assertRegex(FORK['stable_signing_certificate_sha256'], r'^[0-9a-f]{64}$')
        self.assertTrue(re.fullmatch(r'\d+\.\d+\.\d+-ljk1291\.\d+', FORK['protocol_version']))


if __name__ == '__main__':
    unittest.main()
