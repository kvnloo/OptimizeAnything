#!/usr/bin/env python3
"""Small, dependency-free experiment runner. Execute only trusted manifests/code.

This is a reproducibility harness, NOT a security sandbox or an autonomous agent.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import signal
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent


class Failure(RuntimeError):
    """A check, command, or resource gate failed."""


class Blocked(Failure):
    """A prerequisite is unavailable; not a pass or a candidate failure."""


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fingerprint(paths: list[Path]) -> dict[str, str]:
    return {str(path): digest(path) for path in paths}


def unchanged(before: dict[str, str]) -> None:
    for name, expected in before.items():
        path = Path(name)
        if not path.is_file() or digest(path) != expected:
            raise Failure(f'Protected input changed: {name}')


def verify_uint_lines(output: bytes, count: int) -> list[int]:
    lines = output.splitlines()
    if len(lines) != count or any(not re.fullmatch(rb'0|[1-9][0-9]{0,9}', x) for x in lines):
        raise Failure(f'Expected {count} unsigned-integer result lines, got invalid output')
    return [int(line) for line in lines]


def compare(expected: list[int], actual: list[int]) -> None:
    if len(expected) != len(actual):
        raise Failure('Result count mismatch')
    for index, (want, got) in enumerate(zip(expected, actual)):
        if want != got:
            raise Failure(f'Case {index}: expected {want}, got {got}')


def command(argv: list[str], cwd: Path, stdin: bytes, deadline: float,
            timeout: float, max_bytes: int, logs: list[dict]) -> bytes:
    """No shell; kill the POSIX process group on timeout or excessive output."""
    if not argv or not all(isinstance(a, str) and a for a in argv):
        raise Failure('Commands must be nonempty argument arrays')
    if time.monotonic() >= deadline:
        raise Failure('Experiment wall-time budget exhausted')
    started = time.monotonic()
    end = min(deadline, started + timeout)
    # Avoid passing cloud/API credentials to subprocesses. Filesystem access is
    # still unrestricted: use an OS sandbox for untrusted candidate code.
    allowed = ('PATH', 'HOME', 'LANG', 'LC_ALL', 'TMPDIR', 'CARGO_HOME', 'RUSTUP_HOME',
               'SYSTEMROOT', 'USERPROFILE', 'PATHEXT')
    env = {key: os.environ[key] for key in allowed if key in os.environ}
    record = {'argv': argv, 'wall_seconds': None, 'exit_code': None}
    logs.append(record)
    with tempfile.TemporaryFile() as inp, tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        inp.write(stdin)
        inp.seek(0)
        try:
            proc = subprocess.Popen(argv, cwd=cwd, stdin=inp, stdout=out, stderr=err,
                                    env=env, start_new_session=(os.name == 'posix'))
        except FileNotFoundError as exc:
            raise Blocked(f'Missing executable: {argv[0]}') from exc
        except OSError as exc:
            raise Failure(f'Cannot execute {argv[0]}: {exc}') from exc

        def stop() -> None:
            try:
                if os.name == 'posix':
                    os.killpg(proc.pid, signal.SIGKILL)
                else:
                    proc.kill()
            except ProcessLookupError:
                pass

        problems: list[str] = []
        finished = threading.Event()

        def supervise() -> None:
            while not finished.wait(0.01):
                if time.monotonic() >= end:
                    problems.append('Command timeout / experiment wall-time budget')
                elif os.fstat(out.fileno()).st_size + os.fstat(err.fileno()).st_size > max_bytes:
                    problems.append('Command output limit exceeded')
                if problems:
                    stop()
                    return

        watcher = threading.Thread(target=supervise, daemon=True)
        watcher.start()
        try:
            proc.wait()  # Blocking wait: measured time is not quantized by polling.
            record['wall_seconds'] = time.monotonic() - started
        finally:
            finished.set()
            watcher.join()
            stop()  # Reap descendants even if the direct child exited first.
            proc.wait()
            record['exit_code'] = proc.returncode
        problem = problems[0] if problems else None
        size = os.fstat(out.fileno()).st_size + os.fstat(err.fileno()).st_size
        err.seek(0)
        record['stderr_tail'] = err.read(min(size, max_bytes))[-4000:].decode('utf-8', 'replace')
        if problem or size > max_bytes:
            raise Failure(problem or 'Command output limit exceeded')
        if proc.returncode != 0:
            raise Failure(f'Command exited {proc.returncode}: {argv[0]}: {record["stderr_tail"]}')
        out.seek(0)
        output = out.read()
        record['stdout_sha256'] = hashlib.sha256(output).hexdigest()
        return output


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, indent=2, ensure_ascii=True)
            stream.write('\n')
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def run(args: argparse.Namespace) -> tuple[dict, int]:
    started = time.monotonic()
    receipt = {
        'schema_version': 1, 'status': 'FAIL', 'mode': args.action,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'seed': args.seed, 'independent_verification': False,
        'environment': {'platform': platform.platform(), 'machine': platform.machine(),
                        'python': platform.python_version(), 'cpu_count': os.cpu_count()},
        'commands': [], 'cost': {'actual_usd': None, 'api_equivalent_usd': None,
                                'note': 'No model dispatched by this harness; authoring cost unknown.'},
        'metrics': {'peak_rss_bytes': None, 'energy_joules': None},
    }
    protected = None
    try:
        manifest = args.manifest.resolve()
        spec = json.loads(manifest.read_text())
        if spec['schema_version'] != 1 or spec['output_contract'] != 'uint-lines-v1':
            raise Failure('Unsupported manifest or output contract')
        candidate = (args.candidate_dir or ROOT / spec['candidate_dir']).resolve()
        receipt['target'] = spec['id']
        receipt['source'] = spec['source']
        receipt['manifest_sha256'] = digest(manifest)
        paths = [ROOT / name for name in spec['integrity']]
        paths += [manifest, Path(__file__).resolve()]
        for name, expected in spec['integrity'].items():
            if digest(ROOT / name) != expected:
                raise Failure(f'Integrity mismatch: {name}')
        protected = fingerprint(paths)
        receipt['verifier_hashes'] = {os.path.relpath(k, ROOT): v for k, v in protected.items()}
        if not candidate.is_dir():
            raise Blocked(f'Candidate directory missing: {candidate}')
        candidate_files = sorted(p for p in candidate.rglob('*')
                                 if p.is_file() and not {'target', '.git'}.intersection(p.relative_to(candidate).parts))
        candidate_before = fingerprint(candidate_files)
        receipt['candidate_files'] = {str(p.relative_to(candidate)): digest(p) for p in candidate_files}
        deadline = started + args.max_seconds
        substitutions = {'root': str(ROOT), 'candidate': str(candidate), 'python': sys.executable,
                         'seed': str(args.seed), 'random_cases': str(args.random_cases), 'suite': 'check'}

        def execute(template: list[str], data: bytes = b'') -> bytes:
            if not isinstance(template, list):
                raise Failure('Command must be an argument array, never a shell string')
            argv = [item.format_map(substitutions) for item in template]
            try:
                return command(argv, ROOT, data, deadline, args.command_timeout,
                               args.max_output_bytes, receipt['commands'])
            finally:
                unchanged(protected)

        receipt['toolchains'] = {name: execute(argv).decode('utf-8', 'replace').strip()
                                 for name, argv in spec.get('versions', {}).items()}
        for build in spec['build']:
            execute(build)
        unchanged(candidate_before)
        # Freeze all candidate input files before measuring. Build artifacts are
        # not a hermetic binary attestation; final grading needs a trusted checkout.
        payload = execute(spec['workload'])
        count = len(payload.splitlines())
        if count == 0:
            raise Failure('Empty workload')
        expected = verify_uint_lines(execute(spec['reference'], payload), count)
        wrong = expected.copy()
        wrong[0] += 1
        try:
            compare(expected, wrong)
        except Failure:
            receipt['negative_control_rejected'] = True
        else:
            raise Failure('Grader accepted the deliberately wrong result')
        actual = verify_uint_lines(execute(spec['candidate'], payload), count)
        compare(expected, actual)
        receipt['check'] = {'cases': count, 'mismatches': 0,
                            'workload_sha256': hashlib.sha256(payload).hexdigest()}
        if args.action == 'bench':
            substitutions['suite'] = 'bench'
            workload = execute(spec['workload'])
            size = len(workload.splitlines())
            if size == 0:
                raise Failure('Empty benchmark workload')
            oracle = verify_uint_lines(execute(spec['reference'], workload), size)
            # One warmup per implementation. Every timed batch must also match.
            compare(oracle, verify_uint_lines(execute(spec['candidate'], workload), size))
            samples: dict[str, list[float]] = {'reference': [], 'candidate': []}
            for iteration in range(args.rounds):
                order = ('reference', 'candidate') if iteration % 2 == 0 else ('candidate', 'reference')
                for name in order:
                    result = execute(spec[name], workload)
                    compare(oracle, verify_uint_lines(result, size))
                    samples[name].append(receipt['commands'][-1]['wall_seconds'])
            receipt['benchmark'] = {
                'scope': 'process-startup + adapter + batch computation; NOT an in-process speedup',
                'cases': size, 'workload_sha256': hashlib.sha256(workload).hexdigest(),
                'rounds': args.rounds, 'samples_seconds': samples,
                'median_seconds': {k: statistics.median(v) for k, v in samples.items()},
                'reference_over_candidate': statistics.median(samples['reference']) / statistics.median(samples['candidate']),
                'production_representative': False,
            }
        unchanged(candidate_before)
        receipt['status'] = 'PILOT_PASS'
        receipt['limitations'] = [
            'Public development corpus, not an independently graded one-shot result.',
            'Process supervisor is not an OS security sandbox or hard memory limiter.',
            'No application integration, output-quality plugin, or optimization search yet.',
        ]
        code = 0
    except Blocked as exc:
        receipt.update(status='BLOCKED', error=str(exc))
        code = 2
    except (Failure, OSError, ValueError, KeyError, TypeError) as exc:
        receipt.update(status='FAIL', error=str(exc))
        code = 1
    finally:
        if protected is not None:
            try:
                unchanged(protected)
            except Failure as exc:
                receipt.update(status='FAIL', error=str(exc))
                code = 1
        receipt['wall_seconds'] = time.monotonic() - started
    return receipt, code


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('check', 'bench'))
    parser.add_argument('manifest', type=Path, nargs='?', default=ROOT / 'targets/leven/experiment.json')
    parser.add_argument('--candidate-dir', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--seed', type=int, default=20261012)
    parser.add_argument('--random-cases', type=int, default=5000)
    parser.add_argument('--rounds', type=int, default=7)
    parser.add_argument('--max-seconds', type=float, default=180)
    parser.add_argument('--command-timeout', type=float, default=60)
    parser.add_argument('--max-output-bytes', type=int, default=8_000_000)
    args = parser.parse_args()
    if not 0 <= args.random_cases <= 100_000 or not 3 <= args.rounds <= 100:
        parser.error('random-cases: 0..100000; rounds: 3..100')
    if not all(math.isfinite(x) and x > 0 for x in (args.max_seconds, args.command_timeout)) or args.max_output_bytes < 1024:
        parser.error('Budgets must be positive and finite; output limit must be >= 1024')
    # Receipts must not overwrite sources, fixtures, manifests, or candidate files.
    output = (args.output or ROOT / 'runs' / f'run-{time.time_ns()}.json').resolve()
    if output.exists():
        try:
            previous = json.loads(output.read_text())
            if not isinstance(previous, dict) or previous.get('status') not in ('PILOT_PASS', 'FAIL', 'BLOCKED'):
                raise ValueError('Not a receipt')
        except (OSError, ValueError):
            parser.error('Refusing to overwrite a file that is not an experiment receipt')
    if output == args.manifest.resolve() or (ROOT in output.parents and ROOT / 'runs' not in output.parents):
        parser.error('Write receipts under runs/ or outside the repository')
    receipt, code = run(args)
    atomic_json(output, receipt)
    print(f'{receipt["status"]}: {receipt.get("error", str(receipt.get("check", {}).get("cases", 0)) + " cases matched")}')
    print(f'Receipt: {output}')
    return code


if __name__ == '__main__':
    raise SystemExit(main())
