"""new-case: coordinator-owned part writers and advisory output boundaries (#1450).

One coordinator publishes snapshots atomically; a lock refuses overlapping updates.
This is a routing guard, not a shell sandbox or an execution/launch transaction.
"""
import argparse
import json
import os
from pathlib import Path
import re
import tempfile

TOKEN = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]*\Z')
STATUSES = {'active', 'completed', 'failed'}
FILE_TOOLS = {'Write', 'Edit', 'NotebookEdit', 'write_to_file', 'replace_file_content'}
SHELL_TOOLS = {'Bash', 'PowerShell', 'run_command', 'shell', 'exec_command', 'local_shell'}


def absolute_root(value):
    if not isinstance(value, str) or not value.strip() or '\x00' in value:
        raise ValueError('output root must be an absolute non-drive-root path')
    root = Path(value)
    if not root.is_absolute():
        raise ValueError('output root must be absolute')
    root = root.resolve()
    if root == Path(root.anchor):
        raise ValueError('output root cannot be a drive/filesystem root')
    return root


def token(value, name):
    if not isinstance(value, str) or not TOKEN.fullmatch(value):
        raise ValueError(f'invalid {name}: {value!r}')
    return value


def validate(data, root):
    if not isinstance(data, dict) or set(data) != {'output_root', 'writers'}:
        raise ValueError('registry requires output_root and writers')
    if absolute_root(data['output_root']) != root:
        raise ValueError('registry output_root differs from the bound build root')
    rows = data['writers']
    if not isinstance(rows, list) or not rows:
        raise ValueError('registry writers must be a nonempty list')
    parts, agents = set(), set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'part', 'agent_id', 'kind', 'status'}:
            raise ValueError('partial/unsupported writer entry')
        part, agent = token(row['part'], 'part'), token(row['agent_id'], 'agent id')
        if row['kind'] not in ('workflow', 'background') or row['status'] not in STATUSES:
            raise ValueError(f'unsupported kind/status for {part}')
        if part in parts or agent in agents:
            raise ValueError(f'duplicate part or agent: {part}/{agent}')
        parts.add(part)
        agents.add(agent)
    return rows


def load(root):
    return validate(json.loads((root / '_swarm/writers.json').read_text(encoding='utf-8')), root)


def check_message(args, root_value):
    """Return a denial reason, or None for the current active background owner."""
    try:
        if not isinstance(args, dict):
            raise ValueError('message input must be an object')
        root = absolute_root(root_value)
        rows = load(root)  # fresh read for EVERY SendMessage; no cached ownership
        recipient = args.get('recipient', args.get('to'))
        token(recipient, 'recipient')
        headers = []
        for field in ('message', 'content'):
            text = args.get(field, '')
            if not isinstance(text, str):
                raise ValueError(f'{field} must be a string')
            found = re.findall(r'^Part: ([A-Za-z0-9][A-Za-z0-9_.-]*)\s*$', text, re.MULTILINE)
            if len(found) > 1:
                raise ValueError('ambiguous/conflicting Part header')
            headers.extend(found)
        part = args.get('part') or (headers[0] if headers else None)
        token(part, 'part')
        if any(header != part for header in headers):
            raise ValueError('ambiguous/conflicting Part header')
        if 'recipient' in args and 'to' in args and args['recipient'] != args['to']:
            raise ValueError('conflicting recipient/to')
        owner = next((r for r in rows if r['agent_id'] == recipient), None)
        if owner is None:
            raise ValueError(f'unregistered recipient {recipient}')
        if owner['kind'] != 'background':
            raise ValueError(f'workflow recipient {recipient}: do not SendMessage; use workflow results')
        if owner['part'] != part or owner['status'] != 'active':
            raise ValueError(f'{recipient} is not the active background owner of {part}')
    except (OSError, ValueError, TypeError, RuntimeError) as exc:
        return f'swarm: SendMessage refused: {exc}'
    return None


def write_warning(tool, args, root_value, cwd):
    """Conservative lexical shell advisory; file targets use resolved containment."""
    if tool in FILE_TOOLS:
        targets = [args.get('file_path') or args.get('notebook_path') or args.get('TargetFile')]
    elif tool in SHELL_TOOLS:
        command = args.get('command', args.get('CommandLine', ''))
        if not isinstance(command, str) or not re.search(
                r'>|\b(mkdir|copy|cp|out-file|set-content|write\w*|save\w*|export\w*)\b|open\s*\(',
                command, re.IGNORECASE):
            return None
        targets = re.findall(r'[A-Za-z]:[/\\][^\s\"\'<>|;,()]*|(?<![\w:])/(?:[^\s\"\'<>|;,()]+)', command)
        if not targets:
            return 'swarm warning: shell write destination unresolved; use the absolute output root'
    else:
        return None
    try:
        root = absolute_root(root_value)
        for target in targets:
            if not isinstance(target, str) or not target:
                raise ValueError('missing write destination')
            path = Path(target)
            if not path.is_absolute():
                path = Path(cwd or os.getcwd()) / path
            path.resolve().relative_to(root)
    except (OSError, ValueError, TypeError, RuntimeError) as exc:
        return f'swarm warning: write outside job build root (or invalid root): {targets!r}; {exc}'
    return None


def register(root_value, part, agent_id, kind, status):
    root = absolute_root(root_value)
    row = {'part': token(part, 'part'), 'agent_id': token(agent_id, 'agent id'),
           'kind': kind, 'status': status}
    validate({'output_root': str(root), 'writers': [row]}, root)
    folder = root / '_swarm'
    folder.mkdir(parents=True, exist_ok=True)
    # Reject junction/symlink redirection out of the declared build root.
    folder.resolve().relative_to(root)
    lock = folder / 'writers.lock'
    lock.open('x', encoding='utf-8').close()
    tmp = None
    try:
        path = folder / 'writers.json'
        rows = load(root) if path.exists() else []
        previous = next((r for r in rows if r['part'] == part), None)
        if previous and previous['status'] == 'active' and (
                previous['agent_id'] != agent_id or previous['kind'] != kind):
            raise ValueError(f'part {part} already has an active writer')
        rows = [r for r in rows if r['part'] != part] + [row]
        data = {'output_root': str(root), 'writers': rows}
        validate(data, root)
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=folder,
                                         prefix='writers-', suffix='.partial', delete=False) as stream:
            tmp = Path(stream.name)
            json.dump(data, stream, indent=2)
            stream.write('\n')
        os.replace(tmp, path)
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)
        # Release only the lock we created (never a pre-existing foreign lock).
        lock.unlink()
    return (f'Part: {part}\nOutput root: {root}\n'
            f'Environment: AGR_SWARM_BUILD_ROOT={root}; AGR_SWARM_AGENT_ID={agent_id}\n'
            'Write only under this output root. Do not create drive-root scratch folders.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['register'])
    parser.add_argument('--root', required=True)
    parser.add_argument('--part', required=True)
    parser.add_argument('--agent-id', required=True)
    parser.add_argument('--kind', required=True, choices=['workflow', 'background'])
    parser.add_argument('--status', default='active', choices=sorted(STATUSES))
    args = parser.parse_args()
    try:
        print(register(args.root, args.part, args.agent_id, args.kind, args.status))
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(2, f'swarm: {exc}\n')


if __name__ == '__main__':
    main()
