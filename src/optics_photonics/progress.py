"""Optional saved program progress, scoped to one calculation and its attempts.

Programs receive CHECKPOINT from the worker. The state is JSON; model and array
files remain ordinary files. A save commits references only after the program
has finished writing them. Files referenced by saved progress must not be
changed in place afterwards.
"""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time


def identity(value):
    """A private compatibility key; no configuration values go into the snapshot."""
    text = json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _write(path, record):
    text = json.dumps(record, ensure_ascii=False, allow_nan=False, separators=(',', ':')) + '\n'
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix='.' + path.stem + '-', suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


class Checkpoint:
    """Save JSON state and read immutable artifacts from this or prior attempts."""

    def __init__(self, output, compatible, previous=(), *, kind='program'):
        if kind not in ('program', 'optimization', 'points'):
            raise ValueError('Checkpoint kind is program, optimization or points')
        self.output = Path(output).resolve()
        self.previous = tuple(Path(folder).resolve() for folder in previous)
        self.compatible, self.kind = compatible, kind
        self.file = self.output / 'checkpoints' / (kind + '.json')
        self.files, self.restored_from = {}, None

    def _artifact(self, value, base):
        target = (base / value).resolve()
        if not any(target.is_relative_to(root) for root in (self.output, *self.previous)):
            raise ValueError('Saved progress refers to a file outside this calculation')
        if not target.exists():
            raise ValueError('Saved progress file is missing: ' + str(target))
        return target

    def load(self, default=None):
        """Read the newest saved state, or default if this program never saved one.

        Different source, inputs or a bound environment cannot reuse the state.
        A damaged snapshot is reported; older progress is not silently replayed.
        """
        for folder in (self.output, *self.previous):
            path = folder / 'checkpoints' / (self.kind + '.json')
            if not path.exists():
                continue
            try:
                record = json.loads(path.read_text(encoding='utf-8'))
                if (not isinstance(record, dict) or record.get('format') != 1
                        or 'state' not in record or not isinstance(record.get('files'), dict)):
                    raise ValueError('invalid snapshot format')
                if record.get('compatible') != self.compatible:
                    raise ValueError('source, inputs or environment changed; submit a new calculation '
                                     'or explicitly migrate its saved state')
                self.files = {name: self._artifact(value, folder) for name, value in record['files'].items()}
            except (OSError, ValueError, TypeError) as error:
                raise ValueError(f'Cannot continue from {path}: {error}') from error
            self.restored_from = path
            return record['state']
        return default

    def save(self, state, *, files=None):
        """Atomically commit state and named, already-written files or folders.

        Relative paths start at OUTPUT_DIR. Previously restored files may be
        referenced directly; there is no implicit copy of a large model.
        """
        if files is not None and (not isinstance(files, dict)
                                 or any(not isinstance(name, str) or not name for name in files)):
            raise ValueError('Checkpoint files maps names to paths')
        artifacts = {name: self._artifact(value, self.output) for name, value in (files or {}).items()}
        record = {'format': 1, 'kind': self.kind, 'compatible': self.compatible, 'saved': time.time(),
                  'state': state, 'files': {name: os.path.relpath(value, self.output) for name, value in artifacts.items()}}
        _write(self.file, record)
        # Status reads do not parse a program's potentially large saved state.
        brief = {'path': 'checkpoints/' + self.file.name, 'saved': record['saved'],
                 'files': len(artifacts), 'kind': self.kind}
        _write(self.file.with_suffix('.status.json'), brief)
        self.files = artifacts
        return brief


def summary(output):
    """Compact available progress; the state itself is read with ordinary file APIs."""
    folder = Path(output)
    found = []
    for kind in ('program', 'optimization', 'points'):
        path = folder / 'checkpoints' / (kind + '.status.json')
        if not path.exists():
            continue
        try:
            record = json.loads(path.read_text(encoding='utf-8'))
            found.append({'path': 'checkpoints/' + kind + '.json', 'saved': record['saved'],
                          'files': record['files'], 'kind': kind})
        except (OSError, ValueError, KeyError, TypeError):
            found.append({'path': str(path.relative_to(folder)), 'kind': kind, 'error': 'Saved progress cannot be read'})
    return found
