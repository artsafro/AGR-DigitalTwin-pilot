"""new-case: correlate native background Agent output reads with wall-clock deadlines.

Pure transcript grader; no filesystem writes or model calls. See evals/subagent-timebox/task.md.
"""
import math
import re
from datetime import datetime

DEFAULT_MINUTES = 30
BOX = re.compile(r'time[ -]?box\s*:\s*(\S+)\s*(min(?:utes?)?)\b', re.I)


def subagent_timebox(evidence):
    """Fail on any unattended interval >= the brief's time box; incomplete evidence never passes."""
    from twinqa.evals.graders import _blocks, _row, _sessions, _text

    sessions, problems = _sessions(evidence['transcript'])
    if not sessions:
        problems.append('no transcript evidence')
    violations = []
    for path, records in sessions:
        active, calls, seen, overdue = {}, {}, set(), set()
        previous = None
        for n, rec in enumerate(records):
            if rec.get('isSidechain') or rec.get('type') not in ('user', 'assistant'):
                continue
            identity = rec.get('uuid') or repr(rec)
            if identity in seen:
                continue
            seen.add(identity)
            try:
                now = datetime.fromisoformat(rec['timestamp'].replace('Z', '+00:00'))
                if now.utcoffset() is None:
                    raise ValueError('timezone missing')
                now = now.timestamp()
                if not math.isfinite(now) or (previous is not None and now < previous):
                    raise ValueError('nonmonotonic timestamp')
            except (KeyError, TypeError, ValueError, OverflowError, AttributeError):
                problems.append(f'{path}:{n}: missing/invalid/nonmonotonic timestamp')
                continue
            previous = now
            # Check BEFORE processing this event: a late read cannot erase an earlier lapse.
            for key, state in active.items():
                if now - state['last'] >= state['seconds'] and key not in overdue:
                    overdue.add(key)
                    violations.append({'file': str(path), 'record': n, 'tool_use_id': key,
                                       'unattended_seconds': now - state['last'],
                                       'timebox_seconds': state['seconds']})
            for b in _blocks(rec):
                if rec['type'] == 'assistant' and b.get('type') == 'tool_use':
                    key, name, args = b.get('id'), b.get('name'), b.get('input', {})
                    if not isinstance(key, str) or not isinstance(args, dict):
                        problems.append(f'{path}:{n}: malformed tool call')
                        continue
                    calls[key] = (name, args)
                    if name in ('Agent', 'Task') and args.get('run_in_background') in (True, 'true'):
                        prompt = args.get('prompt', '')
                        match = BOX.search(prompt) if isinstance(prompt, str) else None
                        try:
                            minutes = float(match[1]) if match else DEFAULT_MINUTES
                            if not math.isfinite(minutes) or not math.isfinite(minutes * 60) or minutes <= 0:
                                raise ValueError('invalid time box')
                            if isinstance(prompt, str) and re.search(r'time[ -]?box', prompt, re.I) and not match:
                                raise ValueError('unsupported time box')
                        except ValueError:
                            problems.append(f'{path}:{n}: invalid time box')
                            minutes = DEFAULT_MINUTES
                        active.setdefault(key, {'last': now, 'seconds': minutes * 60,
                                                'agent': None, 'output': None})
                elif rec['type'] == 'user' and b.get('type') == 'tool_result':
                    key, text = b.get('tool_use_id'), _text(b.get('content'))
                    native = rec.get('toolUseResult') or {}
                    if b.get('is_error') is True or (isinstance(native, dict) and (
                            native.get('success') is False or native.get('retrieval_status') in ('timeout', 'error'))):
                        continue
                    if key in active:
                        state = active[key]
                        native = rec.get('toolUseResult') or {}
                        if not isinstance(native, dict):
                            native = {}
                        agent = re.search(r'agentId:\s*(\S+)', text)
                        output = re.search(r'output_file:\s*([^\r\n]+)', text)
                        state['agent'] = native.get('agentId') or (agent[1] if agent else None)
                        state['output'] = native.get('outputFile') or (output[1].strip() if output else None)
                    name, args = calls.get(key, (None, {}))
                    for launch, state in list(active.items()):
                        checked = (name == 'TaskOutput' and state['agent'] is not None
                                   and args.get('task_id') == state['agent']) or (
                                       name == 'Read' and state['output'] is not None
                                       and args.get('file_path') == state['output'])
                        if checked and text.strip():
                            state['last'] = now
                            native = rec.get('toolUseResult') or {}
                            if isinstance(native, dict) and native.get('status') in ('completed', 'failed', 'stopped'):
                                del active[launch]
            # Only genuine main-session user notifications, not quoted assistant prose.
            content = (rec.get('message') or {}).get('content')
            if rec['type'] == 'user' and isinstance(content, str) and content.lstrip().startswith('<task-notification>'):
                agent = re.search(r'<task-id>([^<]+)</task-id>', content)
                status = re.search(r'<status>([^<]+)</status>', content)
                if agent and status and status[1] in ('completed', 'failed', 'stopped'):
                    for key, state in list(active.items()):
                        if state['agent'] == agent[1]:
                            del active[key]
        if active:
            problems.append(f'{path}: unfinished background agents: {", ".join(active)}')
    return _row('background subagent time-box lapses', violations, problems)
