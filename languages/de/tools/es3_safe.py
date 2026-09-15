"""Patch ES3 value tokens without reserializing untouched type metadata."""
import csv
import io
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from uuid import uuid4


def require_game_closed():
    """拒绝在 wcp.exe 运行时改写存档类文件。"""
    exe = shutil.which('tasklist')
    if exe is None:
        candidate = Path(os.environ.get('SystemRoot', r'C:\Windows')) \
            / 'System32' / 'tasklist.exe'
        exe = str(candidate) if candidate.exists() else 'tasklist'
    try:
        result = subprocess.run(
            [exe, '/FI', 'IMAGENAME eq wcp.exe', '/FO', 'CSV', '/NH'],
            capture_output=True, text=True, errors='replace')
    except OSError as error:
        raise RuntimeError(
            'Cannot establish whether wcp.exe is closed') from error
    if result.returncode != 0:
        raise RuntimeError(
            'Cannot establish whether wcp.exe is closed')
    if not result.stdout.strip():
        raise RuntimeError('Cannot establish whether wcp.exe is closed')
    for row in csv.reader(io.StringIO(result.stdout)):
        if len(row) >= 2 and row[0].strip().lower() == 'wcp.exe':
            raise RuntimeError('wcp.exe is running; close the game first')


def members(text):
    """Return exact value spans; reject ambiguous duplicate keys at this level."""
    decoder = json.JSONDecoder()
    json.loads(text)  # Validate the entire document before considering edits.
    pos = len(text) - len(text.lstrip())
    if text[pos] != '{':
        raise ValueError('ES3 record must be an object')
    pos += 1
    out = {}
    while True:
        while text[pos].isspace():
            pos += 1
        if text[pos] == '}':
            return out
        key, pos = decoder.raw_decode(text, pos)
        while text[pos].isspace():
            pos += 1
        if text[pos] != ':' or key in out:
            raise ValueError('Invalid or duplicate ES3 key')
        pos += 1
        while text[pos].isspace():
            pos += 1
        start = pos
        _, pos = decoder.raw_decode(text, pos)
        out[key] = (start, pos)
        while text[pos].isspace():
            pos += 1
        if text[pos] == ',':
            pos += 1


def replace_member(text, key, value_text):
    spans = members(text)
    if key in spans:
        start, end = spans[key]
        return text[:start] + value_text + text[end:]
    end = text.rfind('}')
    entry = json.dumps(key, ensure_ascii=False) + ': ' + value_text
    return text[:end] + (',' if spans else '') + '\n' + entry + text[end:]


def patch_values(text, updates):
    for key, (value, type_name) in updates.items():
        spans = members(text)
        encoded = json.dumps(value, ensure_ascii=False)
        if key in spans:
            start, end = spans[key]
            wrapped = text[start:end]
            fields = members(wrapped)
            if '__type' not in fields or 'value' not in fields:
                raise ValueError('Missing ES3 type/value wrapper: ' + key)
            wrapped = replace_member(wrapped, 'value', encoded)
        else:
            wrapped = json.dumps({'__type': type_name, 'value': value},
                                 ensure_ascii=False)
        text = replace_member(text, key, wrapped)
    members(text)
    return text


def write_values(path, updates, dry_run=False):
    path = Path(path)
    original = path.read_bytes() if path.exists() else None
    text = original.decode('utf-8-sig') if original is not None else '{}'
    result = patch_values(text, updates)
    if dry_run:
        return result
    require_game_closed()
    if (path.read_bytes() if path.exists() else None) != original:
        raise RuntimeError('ES3 changed during preparation; refusing overwrite')
    if original is not None:
        backup = path.with_name(path.name + '.bak_' + uuid4().hex)
        shutil.copy2(path, backup)
    fd, tmp = tempfile.mkstemp(prefix=path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(result.encode('utf-8-sig' if original and original.startswith(b'\xef\xbb\xbf') else 'utf-8'))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        Path(tmp).unlink(missing_ok=True)
    return result
