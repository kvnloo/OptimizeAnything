"""Reproducible UTF-16 workloads. No third-party packages or network access."""
from __future__ import annotations

import argparse
import itertools
import random

# Adapted from Sindre Sorhus's MIT-licensed leven v4.0.0 test.js.
UPSTREAM = [
    ('a', 'b', 1), ('ab', 'ac', 1), ('ac', 'bc', 1), ('abc', 'axc', 1),
    ('kitten', 'sitting', 3), ('xabxcdxxefxgx', '1ab2cd34ef5g6', 6),
    ('cat', 'cow', 2), ('xabxcdxxefxgx', 'abcdefg', 6),
    ('javawasneat', 'scalaisgreat', 7), ('example', 'samples', 3),
    ('sturgeon', 'urgently', 6), ('levenshtein', 'frankenstein', 6),
    ('distance', 'difference', 5),
    ('因為我是中國人所以我會說中文', '因為我是英國人所以我會說英文', 2),
]


def units(text: str) -> list[int]:
    data = text.encode('utf-16-le', errors='surrogatepass')
    return [int.from_bytes(data[i:i + 2], 'little') for i in range(0, len(data), 2)]


def encode_pair(a: list[int], b: list[int]) -> str:
    return ','.join(f'{u:04x}' for u in a) + '\t' + ','.join(f'{u:04x}' for u in b)


def generate(seed: int, count: int, suite: str = 'check'):
    rng = random.Random(seed)
    if suite == 'bench':
        # Batch workload, not a single-function microbenchmark.
        for length in (32, 128, 512):
            for _ in range(12):
                a = [rng.randrange(97, 123) for _ in range(length)]
                b = [rng.randrange(97, 123) for _ in range(length)]
                yield a, b
                yield a, a[:-1] + [0xD800]
        return
    for a, b, _ in UPSTREAM:
        yield units(a), units(b)
    edge = [[], [0], [0xD800], [0xDC00], [0xFFFF], units('😀'), units('é'), units('é')]
    yield from itertools.product(edge, repeat=2)
    words = [list(w) for n in range(4) for w in itertools.product((0, 97, 0xD800), repeat=n)]
    yield from itertools.product(words, repeat=2)
    for length in (1, 64, 512, 4096):
        a = [97] * length
        yield a, a
        yield a, []
        yield [], a
        yield a, a[:-1] + [98]
    for _ in range(count):
        alphabet = (0, 97, 98, 0xFFFF, 0xD800, 0xDC00, rng.randrange(65536))
        a = [rng.choice(alphabet) for _ in range(rng.randrange(65))]
        b = [rng.choice(alphabet) for _ in range(rng.randrange(65))]
        yield a, b
    # Stateful oracle array reuse: long -> short -> empty -> long.
    yield [97] * 256, [98] * 256
    yield [97], [98]
    yield [], []
    yield [97] * 256, [98] * 256


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--seed', type=int, required=True)
    parser.add_argument('--random-cases', type=int, default=5000)
    parser.add_argument('--suite', choices=('check', 'bench'), default='check')
    args = parser.parse_args()
    if not 0 <= args.random_cases <= 100_000:
        parser.error('random-cases must be between 0 and 100000')
    for left, right in generate(args.seed, args.random_cases, args.suite):
        print(encode_pair(left, right))
