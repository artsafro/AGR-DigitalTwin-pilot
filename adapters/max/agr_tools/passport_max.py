"""new-case: AGR Tools 1.0 (#1024) project passport (K1), 3ds Max side. Stub of branch 0; owned by branch F (improve/issue-1024-passport).

runtime.edits_100 calls `<function>(ctx, mode, nodes, preview)` for `project_passport` (project.passport);
while the function is absent the dispatcher reports `status: not_implemented` (issue #1024).
ctx: agr (runtime globals), core (passport_core), edit (edit_core), emax (edit_max), options (dict of the preview),
host (host_max.MaxHost: ObjRef, user props, one undo record).
Import pymxs inside functions so this file loads under plain pytest.

project.passport (plan mode `file`): preview says what apply does and changes nothing:
* `create` - no passport yet: apply makes the NEW folder `<root>/jobs/<ID>/` with passport.json, PASSPORT.md and
  journal.jsonl (exclusive create; an existing passport is opened, never overwritten);
* `open` - the scene's `agr_passport` link or `<root>/jobs/<ID>/passport.json` exists: apply refreshes parts (roles
  read back from the scene), the journal copy and its tail; the previous passport goes to `history/` first and the
  write happens only while the file still has the sha the preview read (else StalePreview).
Both link the scene: custom file property `agr_passport` = {"path", "sha256"}. A broken passport (schema) or a
broken link is an error, never a new passport over it. Options: root (folder holding jobs/; default the scene
folder), project_id (default from the scene file name), title, address.
Report objects: the nodes (selection or all) with role findings role_missing / role_unknown / role_conflict.
"""
import os

OPTION_KEYS = ('root', 'project_id', 'title', 'address')


def _rt():
    from pymxs import runtime
    return runtime


# ---- scene file property agr_passport ------------------------------------------------------------------------
def read_link():
    """Text of the custom file property agr_passport, or None."""
    rt = _rt()
    idx = int(rt.fileProperties.findProperty(rt.name('custom'), 'agr_passport'))
    if idx <= 0:
        return None
    return str(rt.fileProperties.getPropertyValue(rt.name('custom'), idx))


def write_link(text):
    rt = _rt()
    rt.fileProperties.addProperty(rt.name('custom'), 'agr_passport', str(text))


def linked_passport(core=None):
    """(passport, path, sha) of the scene's passport, or None; for the stage rail (ui_model.stage_rail)."""
    core = core or _core()
    link = core.parse_link(read_link())
    if link is None:
        return None
    passport, sha = core.read(link['path'])
    return passport, link['path'], sha


def _core():
    import importlib.util
    here = os.path.dirname(os.path.abspath(__file__))
    spec = importlib.util.spec_from_file_location('agr_tools_passport_core', os.path.join(here, 'passport_core.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _journal(ctx):
    return ctx.agr._load_core('journal_core.py', 'agr_tools_journal_core')


# ---- scene read ---------------------------------------------------------------------------------------------
def _nodes(nodes):
    rt = _rt()
    if nodes:
        return [n for n in nodes if rt.isValidNode(n)]
    return [n for n in rt.objects if not str(n.name).startswith(('_base_', '_label_', '_cam_'))]


def role_items(ctx, nodes):
    """[{'ref', 'name', 'prop', 'layer'}] of the nodes (ObjRef by handle; roles are read, never set here)."""
    out = []
    refs = ctx.host.refs(nodes)
    for n, ref in zip(nodes, refs):
        layer = n.layer.name if n.layer is not None else ''
        out.append({'ref': ref, 'name': str(n.name), 'prop': ctx.host.get_prop(ref, 'agr_role'),
                    'layer': str(layer)})
    return out


def default_root():
    """Folder holding jobs/ for an unsaved scene («завести проект» on an empty scene): AGR_PROJECTS_ROOT, else
    %LOCALAPPDATA%\\AGRTools\\projects."""
    return os.environ.get('AGR_PROJECTS_ROOT') or os.path.join(
        os.environ.get('LOCALAPPDATA') or os.path.expanduser('~'), 'AGRTools', 'projects')


def _target(ctx, core, opts, doc, link):
    """(action, passport path, project id, root) from the link or the options; ValueError when nothing names it."""
    if link is not None:
        path = os.path.normpath(link['path'])
        return 'open', path, os.path.basename(os.path.dirname(path)), os.path.dirname(os.path.dirname(
            os.path.dirname(path)))
    saved = bool(doc) and doc != 'untitled'
    pid = opts.get('project_id') or (core.project_id_from(doc) if saved else None)
    if not pid:
        raise ValueError('project.passport: no project id; save the scene or give options.project_id')
    root = opts.get('root') or (os.path.dirname(doc) if saved else default_root())
    path = os.path.join(core.project_dir(root, pid), core.PASSPORT_FILE)
    return ('open' if os.path.isfile(path) else 'create'), path, pid, root


def _state(ctx, core, nodes, raw):
    """Everything apply depends on: the document, the link, the passport file sha, roles; and the plan parts.
    `raw`: the options of the preview (apply takes none; they come back from the preview plan)."""
    opts = dict(raw or {})
    unknown = sorted(set(opts) - set(OPTION_KEYS))
    if unknown:
        raise ValueError('project.passport: unknown option(s) {}; known {}'.format(unknown, list(OPTION_KEYS)))
    doc = ctx.host.doc()
    link_text = read_link()
    link = core.parse_link(link_text)
    action, path, pid, root = _target(ctx, core, opts, doc, link)
    core.check_project_id(pid)
    sha = None
    current = None
    if action == 'open':
        current, sha = core.read(path)  # a broken passport is an error here, before any write
        if current['project_id'] != pid:
            raise core.PassportError('passport {} names project {!r}, its folder {!r}'.format(
                path, current['project_id'], pid))
    items = role_items(ctx, nodes)
    parts, problems = core.parts_from_roles(items)
    jc = _journal(ctx)
    journal_lines = len(jc.read_lines(jc.journal_path(doc))[0])
    state = {'doc': doc, 'link': link_text, 'action': action, 'path': path, 'sha': sha,
             'items': [{'handle': it['ref']['handle'], 'name': it['name'], 'prop': it['prop'],
                        'layer': it['layer']} for it in items],
             'options': opts}
    return state, {'items': items, 'parts': parts, 'problems': problems, 'current': current, 'pid': pid,
                   'root': root, 'journal_lines': journal_lines, 'link': link}


def _report(ctx, core, mode, state, facts, done, skipped, extra):
    edit = ctx.edit
    objects = []
    for it in facts['items']:
        prob = facts['problems'].get(it['name'])
        objects.append(edit.entry(it['ref']['handle'], it['name'],
                                  [edit.finding(prob[0], (), prob[1])] if prob else []))
    ambiguous = []
    link = facts['link']
    if link is not None and state['sha'] is not None and link['sha256'] != state['sha']:
        ambiguous.append({'item': state['path'], 'reason': 'passport changed outside this scene since the link '
                          '(sha {} -> {}); apply re-links it'.format(link['sha256'][:12], state['sha'][:12])})
    cur = facts['current']
    plan_extra = {'action': state['action'], 'project_id': facts['pid'], 'passport': state['path'],
                  'parts': facts['parts'],
                  'stages': core.stage_table(cur) if cur else [{'id': s, 'status': 'todo', 'seconds': None}
                                                               for s in core.STAGE_IDS],
                  'journal_lines': facts['journal_lines']}
    plan_extra.update(extra or {})
    return edit.report('project.passport', mode, objects, done=done, skipped_=skipped,
                       ambiguous=ambiguous if mode == 'preview' else [],
                       state_hash=edit.fingerprint(state) if mode == 'preview' else None, extra=plan_extra)


def project_passport(ctx, mode, nodes, preview):
    core = ctx.core
    nodes = _nodes(nodes)
    if mode == 'preview':
        state, facts = _state(ctx, core, nodes, ctx.options)
        root = os.path.dirname(state['path'])
        if state['action'] == 'create':
            done = [state['path'], os.path.join(root, core.MARKDOWN_FILE), os.path.join(root, core.JOURNAL_FILE),
                    'scene property agr_passport']
        else:
            done = [state['path'] + ' (parts, journal tail)', os.path.join(root, core.JOURNAL_FILE),
                    os.path.join(root, core.MARKDOWN_FILE), 'scene property agr_passport']
        return _report(ctx, core, 'preview', state, facts, done, [], {'options_raw': state['options']})
    # apply: the scene and the passport file must be as the preview saw them
    state, facts = _state(ctx, core, nodes, preview['plan'].get('options_raw'))
    ctx.edit.require_current(preview, state)
    pid = facts['pid']
    folder = os.path.dirname(state['path'])
    jc = _journal(ctx)
    done, skipped = [], []
    if state['action'] == 'create':
        if os.path.exists(folder) and os.listdir(folder):
            raise FileExistsError('project.passport: {} exists and is not empty; refusing to create a passport '
                                  'in it'.format(folder))
        os.makedirs(folder, exist_ok=True)
        passport = core.new_passport(pid, source_path=state['doc'], scene=state['doc'],
                                     title=state['options'].get('title'), address=state['options'].get('address'))
    else:
        passport = facts['current']
        history = os.path.join(folder, core.HISTORY_DIR)
        os.makedirs(history, exist_ok=True)
        with open(state['path'], 'rb') as f:
            old = f.read()
        if core.sha256(old) != state['sha']:
            raise ctx.edit.StalePreview('passport changed since the preview; run preview again')
        keep = ctx.edit.new_path(os.path.join(history, 'passport_v001.json'), version=True)
        ctx.edit.write_new(keep, old)
        done.append(keep)
    passport = core.with_parts(passport, facts['parts'])
    copied = jc.copy_to(state['doc'], os.path.join(folder, core.JOURNAL_FILE))
    passport = core.touched(core.with_journal(passport, copied['lines'], copied['tail']))
    data = core.dumps(passport)
    md = core.markdown(passport).encode('utf-8')
    if state['action'] == 'create':
        ctx.edit.write_new(state['path'], data)
        ctx.edit.write_new(os.path.join(folder, core.MARKDOWN_FILE), md)
    else:
        for target, blob in ((state['path'], data), (os.path.join(folder, core.MARKDOWN_FILE), md)):
            tmp = target + '.partial'
            with open(tmp, 'wb') as f:
                f.write(blob)
            os.replace(tmp, target)
    done += [state['path'], os.path.join(folder, core.MARKDOWN_FILE), copied['path']]
    sha = core.sha256(data)
    write_link(core.link_value(state['path'], sha))
    done.append('scene property agr_passport')
    return _report(ctx, core, 'apply', state, facts, done, skipped, {'sha256': sha,
                                                                      'journal_added': copied['added']})


# ---- shared save for source.intake (branch F) ---------------------------------------------------------------
def update_linked(ctx, mutate):
    """Apply `mutate(passport) -> passport` to the scene's linked passport (history copy, sha check, re-link).
    Returns (path, sha) or None when the scene has no passport (the caller lists it as skipped)."""
    core = _core()
    link = core.parse_link(read_link())
    if link is None:
        return None
    path = os.path.normpath(link['path'])
    passport, sha = core.read(path)
    folder = os.path.dirname(path)
    history = os.path.join(folder, core.HISTORY_DIR)
    os.makedirs(history, exist_ok=True)
    with open(path, 'rb') as f:
        old = f.read()
    if core.sha256(old) != sha:
        raise ctx.edit.StalePreview('passport changed during the save')
    ctx.edit.write_new(ctx.edit.new_path(os.path.join(history, 'passport_v001.json'), version=True), old)
    passport = core.touched(mutate(passport))
    data = core.dumps(passport)
    for target, blob in ((path, data), (os.path.join(folder, core.MARKDOWN_FILE),
                                       core.markdown(passport).encode('utf-8'))):
        tmp = target + '.partial'
        with open(tmp, 'wb') as f:
            f.write(blob)
        os.replace(tmp, target)
    new_sha = core.sha256(data)
    write_link(core.link_value(path, new_sha))
    return path, new_sha
