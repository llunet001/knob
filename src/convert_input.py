"""
convert_input.py

Utility to convert many common input forms (text, hex, base64, binary files)
into a bytes object or a binary file that can be passed to `aont-script.py`.

Usage (CLI):
  python convert_input.py --infile input.bin --out out.bin --mode auto

Modes: auto, text, utf8, hex, base64, binary

The script also exposes a function `normalize_to_bytes(data, mode='auto')` which
accepts bytes, str, or Path and returns bytes.
"""

from __future__ import annotations
import argparse
import base64
import re
from pathlib import Path
from typing import Union

HEX_RE = re.compile(r"^[0-9a-fA-F]+$")
B64_RE = re.compile(r'^[A-Za-z0-9+/=\s]+$')


def is_likely_text(data: bytes) -> bool:
    # Heuristic: treat as text if many bytes are in the printable ASCII range
    if not data:
        return True
    printable = sum(1 for b in data if 32 <= b <= 126 or b in (9, 10, 13))
    return (printable / len(data)) > 0.9


def try_base64_decode(s: str) -> Union[bytes, None]:
    try:
        # strip whitespace
        ss = ''.join(s.split())
        # base64 requires length % 4 == 0 unless padded; allow decode attempts
        return base64.b64decode(ss, validate=True)
    except Exception:
        return None


def normalize_to_bytes(data: Union[bytes, str, Path], mode: str = 'auto') -> bytes:
    """
    Convert input (bytes, text, path) into raw bytes.

    mode: auto|text|utf8|hex|base64|binary
    """
    if isinstance(data, bytes):
        return data

    # If a Path-like string or Path, read file
    if isinstance(data, (str, Path)) and Path(data).exists():
        raw = Path(data).read_bytes()
        # If explicit mode says binary, return as-is
        if mode == 'binary':
            return raw
        # If file is mostly binary, just return raw
        if not is_likely_text(raw) and mode == 'auto':
            return raw
        # otherwise decode content as text for further detection
        try:
            s = raw.decode('utf-8')
        except Exception:
            # fallback: treat as binary
            if mode == 'auto':
                return raw
            else:
                raise
    else:
        # it's a plain string (not a file path)
        s = str(data)

    # At this point we have a string `s` and a mode.
    s_stripped = s.strip()

    if mode in ('auto', 'text', 'utf8'):
        # If explicitly text, just encode
        if mode in ('text', 'utf8'):
            return s_stripped.encode('utf-8')

        # auto-detect hex
        if HEX_RE.fullmatch(s_stripped) and len(s_stripped) % 2 == 0:
            try:
                return bytes.fromhex(s_stripped)
            except Exception:
                pass

        # auto-detect base64
        if B64_RE.fullmatch(s_stripped):
            b = try_base64_decode(s_stripped)
            if b is not None:
                return b

        # default: encode as UTF-8 text
        return s_stripped.encode('utf-8')

    if mode == 'hex':
        return bytes.fromhex(s_stripped)
    if mode == 'base64':
        b = try_base64_decode(s_stripped)
        if b is None:
            raise ValueError('Input is not valid base64')
        return b
    if mode == 'binary':
        # if it's a string and not a file, assume the user provided escape sequences
        return s.encode('utf-8')

    raise ValueError(f'Unknown mode: {mode}')


def _cli():
    p = argparse.ArgumentParser(description='Convert input into binary bytes usable by AONT script')
    p.add_argument('--infile', '-i', help='Input file path or inline string. If path exists it is read.', required=True)
    p.add_argument('--out', '-o', help='Output file (binary). If omitted prints a short summary and base64 to stdout.')
    p.add_argument('--mode', '-m', help='Mode: auto,text,utf8,hex,base64,binary', default='auto')
    args = p.parse_args()

    src = args.infile
    mode = args.mode

    # If infile is of the form @filename, treat as file regardless
    if src.startswith('@'):
        src = src[1:]

    try:
        result = normalize_to_bytes(Path(src) if Path(src).exists() else src, mode=mode)
    except Exception as e:
        print('Error converting input:', e)
        raise

    if args.out:
        outp = Path(args.out)
        outp.write_bytes(result)
        print(f'Wrote {len(result)} bytes to {outp}')
    else:
        print(f'Converted to {len(result)} bytes; base64 below:')
        print(base64.b64encode(result).decode('ascii'))


if __name__ == '__main__':
    # Quick self-test when invoked directly
    print('Running quick self-test of convert_input.normalize_to_bytes')
    samples = {
        'utf8_text': 'Secret data to protect using AONT',
        'utf8_text_with_unicode': 'Tést ✓ — Привет',
        'hex': '48656c6c6f20776f726c64',  # 'Hello world'
        'base64': base64.b64encode(b'Some binary \x00\x01').decode('ascii'),
    }

    for name, s in samples.items():
        b = normalize_to_bytes(s, mode='auto')
        print(f'{name}: {len(b)} bytes, repr(start)=', repr(b[:40]))

    # Also test reading a small temporary binary
    tmp = Path(__file__).parent / 'tmp_test.bin'
    tmp.write_bytes(b'\x00\x01\x02hello')
    b2 = normalize_to_bytes(tmp, mode='auto')
    print('file(tmp_test.bin):', len(b2), 'bytes, is bytes:', isinstance(b2, bytes))
    tmp.unlink()

    print('\nSelf-test complete. Use --help for CLI usage.')
