# dedupe

A streaming duplicate-line remover and line counter, written in Python 3
(standard library only — no dependencies).

It reads lines from files or stdin, deduplicates them, and writes the result
to stdout. Only the dedupe state (one entry per unique line) is held in
memory — the full input is never buffered — so it handles arbitrarily large
inputs.

## What it does

- Removes duplicate lines, keeping either the **first** occurrence (default)
  or the **last** (`--keep-last`, which reorders output by last occurrence).
- `--count` prefixes each unique line with `<count>\t` (TAB-separated).
- Blank lines (empty or whitespace-only) collapse to a **single empty line**
  at the position of the first blank.
- `--ignore-case` deduplicates case-insensitively and emits the first-seen
  spelling (last-seen when combined with `--keep-last`).
- Multiple files are processed in the order given, as one continuous stream —
  duplicates across files are removed together.

## Install

Requires Python 3 (no other runtime or dependencies). Clone and make the
script executable:

```sh
git clone https://github.com/igorjpimenta/dedupe.git
cd dedupe
chmod +x dedupe
```

Then run it directly (`./dedupe ...`), or put the repo directory on your
`PATH` and call it as `dedupe`.

## Usage

```
Usage: dedupe [--keep-first|--keep-last] [--count] [--ignore-case] [FILE...]
  Read lines from stdin (no args or `-`) or FILE args in order.
  Strip trailing newline only, preserve other content.
  --keep-first   emit first occurrence (default)
  --keep-last    emit once, ordered by last occurrence (input still streaming)
  --count        prefix each unique line with "<count>\t"
  --ignore-case  compare case-insensitively; emit first-seen spelling
                 (last-seen with --keep-last)
  -h, --help     show this usage on stdout, exit 0
Blanks (strip()=='') collapse to a single empty line at first blank position.
Unknown flags -> stderr, exit 2. Missing/unreadable file -> stderr, exit 1.
```

The block above is `dedupe --help` reproduced verbatim (printed on stdout,
exit `0`).

## Options

| Flag | Effect |
| --- | --- |
| `--keep-first` | Emit each distinct line once, at its first occurrence. **Default.** Emits immediately while reading. |
| `--keep-last` | Emit each distinct line once, ordered by its **last** occurrence. Input is still read line-by-line (only O(unique) state held); output is deferred until EOF. With `--ignore-case`, the **last-seen spelling** is emitted. |
| `--count` | Prefix each emitted line with `<total count>\t`. Totals are only known at EOF, so output is deferred until EOF and follows the active keep mode (first-occurrence order by default, last-occurrence order with `--keep-last`). Output stays unique — one line per key. |
| `--ignore-case` | Dedupe key is the casefolded line; output preserves the **first-seen spelling** (default / `--keep-first`) or the **last-seen spelling** (`--keep-last`). Blank lines always use the blank key. |
| `-h`, `--help` | Show usage on stdout, exit `0`. |

Notes:

- Passing both `--keep-first` and `--keep-last` is not an error — the **last
  one on the command line wins** (verified: `--keep-first --keep-last`
  behaves as `--keep-last`, and `--keep-last --keep-first` as `--keep-first`).
- No flag takes a value, so there are no missing-value cases. Any argument
  starting with `-` other than exactly `-` or a known flag is an unknown
  flag — even `--count=5` (stderr, exit `2`).

## Examples

Every example below was executed against commit `85c124a` and its output is
verbatim. Tabs are shown as `^I` (as displayed by `cat -t`) because
`--count` output is TAB-separated.

Given `fruit.txt`:

```
alpha
beta
alpha
gamma
beta
```

Default (`--keep-first`), first-occurrence order:

```
$ ./dedupe fruit.txt
alpha
beta
gamma
```

`--keep-last`, ordered by last occurrence:

```
$ ./dedupe --keep-last fruit.txt
alpha
gamma
beta
```

`--count` — `<count>\t` prefix, first-occurrence order, TAB-separated:

```
$ ./dedupe --count fruit.txt | cat -t
2^Ialpha
2^Ibeta
1^Igamma
```

`--count --keep-last` — counts as totals, last-occurrence order:

```
$ ./dedupe --count --keep-last fruit.txt | cat -t
2^Ialpha
1^Igamma
2^Ibeta
```

**Blank rule.** Given `blank.txt` containing `a`, an empty line, a
whitespace-only line (`  `), `b`, and a trailing empty line — all blank
lines fold into one empty line at the first blank position:

```
a

b
```

With `--count`, the blank key's count covers all blank lines:

```
$ ./dedupe --count blank.txt | cat -t
1^Ia
3^I
1^Ib
```

**Ignore-case.** Given `case.txt` containing `Apple`, `apple`, `APPLE`,
`banana` — dedupe key is casefolded, first spelling emitted:

```
$ ./dedupe --ignore-case case.txt
Apple
banana
```

With `--keep-last`, the last-seen spelling is emitted:

```
$ ./dedupe --ignore-case --keep-last case.txt
APPLE
banana
```

**stdin, files, and `-`.** No args reads stdin; `-` means stdin; multiple
files concatenate in order as one stream:

```
$ printf 'x\nx\ny\n' | ./dedupe
x
y
$ printf 'x\nx\n' | ./dedupe -
x
```

**Error handling.** A missing/unreadable file reports on stderr and exits
`1`, but the other inputs are still processed:

```
$ ./dedupe good1.txt /tmp/nope.txt good2.txt
dedupe: cannot read '/tmp/nope.txt': [Errno 2] No such file or directory: '/tmp/nope.txt'
p
q
r
s
$ echo $?
1
```

An unknown flag prints usage hint on stderr and exits `2`:

```
$ ./dedupe --bogus
dedupe: unknown option: --bogus
dedupe: try 'dedupe --help'
$ echo $?
2
```

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Success, including `-h`/`--help` (usage on stdout). |
| `1` | Missing or unreadable input file (message on stderr). All other inputs are still processed; exit is `1` if **any** file failed. |
| `2` | Unknown flag (message on stderr). |

## Streaming

Input is consumed line-by-line (`for line in stream` over `sys.stdin` or
`open(path)`); only the dedupe map — one entry per unique line — is kept in
memory. The full input is never buffered. Two modes defer output until EOF
by design:

- `--keep-last` (last-occurrence order is only known at EOF)
- `--count` (totals are only known at EOF)

Default `--keep-first` emits as it reads. Note that when stdout is a pipe
(not a TTY), Python block-buffers output, so lines may arrive in batches;
that is standard CPython behavior, not extra buffering by `dedupe`.

## Tests

There is no automated test suite in the repo yet. The verification used
while writing this README (and reproducible by you) is copy-paste per
behavior:

```sh
git clone https://github.com/igorjpimenta/dedupe.git && cd dedupe && chmod +x dedupe
printf 'alpha\nbeta\nalpha\ngamma\nbeta\n' > fruit.txt

./dedupe fruit.txt                  # expect: alpha beta gamma
./dedupe --keep-last fruit.txt      # expect: alpha gamma beta
./dedupe --count fruit.txt | cat -t # expect: 2<TAB>alpha 2<TAB>beta 1<TAB>gamma

printf 'a\n\n  \nb\n\n' > blank.txt
./dedupe blank.txt                  # expect: a / (one empty line) / b

printf 'Apple\napple\nAPPLE\nbanana\n' > case.txt
./dedupe --ignore-case case.txt             # expect: Apple banana
./dedupe --ignore-case --keep-last case.txt # expect: APPLE banana

./dedupe /tmp/definitely-missing    # expect: stderr message, exit 1
./dedupe --bogus                    # expect: stderr message, exit 2
./dedupe --help                     # expect: usage on stdout, exit 0
```

## License

MIT — see [LICENSE](LICENSE).
