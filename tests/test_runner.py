"""Offline harness tests. Rust is checked separately by Cargo and differential CI."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

import optimizeanything as oa

case_spec = importlib.util.spec_from_file_location('leven_cases', oa.ROOT / 'targets/leven/cases.py')
cases = importlib.util.module_from_spec(case_spec)
case_spec.loader.exec_module(cases)


class HarnessTests(unittest.TestCase):
    def test_exact_comparison_rejects_wrong_value(self):
        with self.assertRaises(oa.Failure):
            oa.compare([0, 3], [0, 2])

    def test_rejects_missing_result(self):
        with self.assertRaises(oa.Failure):
            oa.compare([1, 2], [1])

    def test_output_parser(self):
        self.assertEqual(oa.verify_uint_lines(b'0\n3\n', 2), [0, 3])
        for bad in (b'', b'3\n0\n', b'-1\n', b'NaN\n', b'1.0\n', b' 1\n', b'01\n'):
            with self.subTest(bad=bad), self.assertRaises(oa.Failure):
                oa.verify_uint_lines(bad, 1)

    def test_upstream_blob_is_exact(self):
        data = (oa.ROOT / 'targets/leven/vendor/index.mjs').read_bytes()
        blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        self.assertEqual(blob, '9eaec1f5531441e4141312e038a8b1be9d4fd7e5')

    def test_utf16_units(self):
        self.assertEqual(cases.units('😀'), [0xD83D, 0xDE00])
        self.assertEqual(cases.units('\ud800'), [0xD800])
        self.assertEqual(cases.encode_pair([], []), '\t')

    def test_deterministic_workloads(self):
        a = list(cases.generate(1, 20))
        self.assertEqual(a, list(cases.generate(1, 20)))
        self.assertNotEqual(a, list(cases.generate(2, 20)))
        self.assertEqual(len(list(cases.generate(1, 5000))), 6698)

    def test_protected_file_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'oracle'
            path.write_text('original')
            snapshot = oa.fingerprint([path])
            path.write_text('changed')
            with self.assertRaises(oa.Failure):
                oa.unchanged(snapshot)

    def test_deleted_protected_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'oracle'
            path.write_text('original')
            snapshot = oa.fingerprint([path])
            path.unlink()
            with self.assertRaises(oa.Failure):
                oa.unchanged(snapshot)

    def invoke(self, script, *, timeout=2, max_bytes=1024):
        return oa.command([sys.executable, '-c', script], oa.ROOT, b'',
                          time.monotonic() + 4, timeout, max_bytes, [])

    def test_command_success(self):
        self.assertEqual(self.invoke('print(3)'), b'3\n')

    def test_nonzero_exit(self):
        with self.assertRaisesRegex(oa.Failure, 'exited 7'):
            self.invoke('raise SystemExit(7)')

    def test_timeout(self):
        with self.assertRaisesRegex(oa.Failure, 'timeout'):
            self.invoke('import time; time.sleep(2)', timeout=0.05)

    def test_output_limit(self):
        with self.assertRaisesRegex(oa.Failure, 'output limit'):
            self.invoke('print("x" * 10000)')

    def test_missing_tool(self):
        with self.assertRaises(oa.Blocked):
            oa.command(['/nonexistent/oa-tool'], oa.ROOT, b'', time.monotonic() + 2, 1, 1024, [])

    def test_credentials_not_passed(self):
        import os
        from unittest.mock import patch
        with patch.dict(os.environ, {'OA_FAKE_API_TOKEN': 'not-a-real-secret'}):
            output = self.invoke('import os; print("OA_FAKE_API_TOKEN" in os.environ)')
        self.assertEqual(output, b'False\n')

    def test_end_to_end_bad_candidate_fails(self):
        receipt, code = self.synthetic_run(candidate='print(0)')
        self.assertEqual(code, 1)
        self.assertEqual(receipt['status'], 'FAIL')
        self.assertIn('Case 0', receipt['error'])

    def test_end_to_end_good_candidate_is_only_pilot(self):
        receipt, code = self.synthetic_run(candidate='print(1)')
        self.assertEqual(code, 0, receipt)
        self.assertEqual(receipt['status'], 'PILOT_PASS')
        self.assertIsNone(receipt['cost']['actual_usd'])
        self.assertFalse(receipt['independent_verification'])

    def test_benchmark_checks_outputs_and_preserves_samples(self):
        receipt, code = self.synthetic_run(candidate='print(1)', action='bench')
        self.assertEqual(code, 0, receipt)
        self.assertEqual(len(receipt['benchmark']['samples_seconds']['candidate']), 3)
        self.assertFalse(receipt['benchmark']['production_representative'])

    def synthetic_run(self, candidate, action='check'):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidate_dir = root / 'candidate'
            candidate_dir.mkdir()
            manifest = root / 'experiment.json'
            manifest.write_text(json.dumps({
                'schema_version': 1, 'id': 'synthetic-harness-selftest',
                'source': {'kind': 'synthetic, not a rewrite result'},
                'output_contract': 'uint-lines-v1', 'integrity': {}, 'build': [],
                'candidate_dir': str(candidate_dir),
                'workload': ['{python}', '-c', 'print("\\t")'],
                'reference': ['{python}', '-c', 'print(1)'],
                'candidate': ['{python}', '-c', candidate],
            }))
            args = argparse.Namespace(manifest=manifest, candidate_dir=None, seed=1,
                                      random_cases=0, action=action, rounds=3,
                                      max_seconds=10, command_timeout=2, max_output_bytes=1024)
            return oa.run(args)


@unittest.skipUnless(shutil.which('node'), 'Node.js not installed')
class OracleTests(unittest.TestCase):
    def oracle(self, pairs):
        payload = ('\n'.join(cases.encode_pair(a, b) for a, b in pairs) + '\n').encode()
        result = subprocess.run(['node', str(oa.ROOT / 'targets/leven/oracle.mjs')],
                                input=payload, capture_output=True, check=True, timeout=10)
        return oa.verify_uint_lines(result.stdout, len(pairs))

    def test_all_upstream_cases(self):
        pairs = [(cases.units(a), cases.units(b)) for a, b, _ in cases.UPSTREAM]
        self.assertEqual(self.oracle(pairs), [n for _, _, n in cases.UPSTREAM])

    def test_surrogates_emoji_and_empty(self):
        self.assertEqual(self.oracle([([], []), ([0xD800], []),
                                      ([0xD83D, 0xDE00], []), ([0], [0])]), [0, 1, 2, 0])

    def test_invalid_protocol_rejected(self):
        for payload in (b'xyz\t\n', b'0001\n', b'0001\t0002\textra\n'):
            result = subprocess.run(['node', str(oa.ROOT / 'targets/leven/oracle.mjs')],
                                    input=payload, capture_output=True, timeout=5)
            self.assertNotEqual(result.returncode, 0)


if __name__ == '__main__':
    unittest.main()
