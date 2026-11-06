"""new-case: agr-mcp permission profiles (mcp-review §3.8, #1024 branch U).

| profile    | tools                                                                                      | who |
|------------|--------------------------------------------------------------------------------------------|-----|
| `observer` | read: context and checks                                                                   | review, Antigravity |
| `operator` | + previews (stage tools, agr_op_preview, 0.9 previews) + agent markup in AGENT_* (D108)    | swarm, default dock |
| `modeller` | + apply (agr_op_apply, 0.8 apply-capable tools); D108 apply still needs the dock button    | Artem's dock |
| `dev`      | + agr_exec_unsafe (arbitrary MAXScript; never in the dock, never in the bridge)            | debugging only |

`tools/list` shows only the profile's tools and a call of any other tool is refused as an unknown tool (the server
audits it). The profile comes from AGR_MCP_PROFILE (default `operator`). `agr_exec_unsafe` exists only in `dev`:
AGR_MCP_UNSAFE=1 alone no longer adds it (defect: the stdio server exposed it to any client with that variable).
"""
from __future__ import annotations

import contextlib
import os

PROFILES = ("observer", "operator", "modeller", "dev")
DEFAULT = "operator"
CLASSES = {"observer": ("read",), "operator": ("read", "preview", "markup"),
           "modeller": ("read", "preview", "markup", "apply"),
           "dev": ("read", "preview", "markup", "apply", "unsafe")}
MARKUP = ("agr_agent_op_preview", "agr_agent_op_apply")
DOCK_PROFILES = ("observer", "operator", "modeller")


def profile_of(env=None, value=None) -> str:
    env = os.environ if env is None else env
    p = value or env.get("AGR_MCP_PROFILE") or DEFAULT
    if p not in PROFILES:
        raise ValueError("unknown AGR_MCP_PROFILE {!r}; one of {}".format(p, ", ".join(PROFILES)))
    return p


def tool_class(spec) -> str:
    """read | preview | markup | apply | unsafe of one catalogue Spec."""
    from .. import tools
    name = spec.name
    if name == "agr_exec_unsafe":
        return "unsafe"
    if name in MARKUP:
        return "markup"
    if name == "agr_op_apply" or not spec.read_only:
        return "apply"
    stage = set(tools.v2_names()) - {"agr_check_run", "agr_op_preview", "agr_op_apply"}
    if name == "agr_op_preview" or name in stage or name in {n for n, *_ in tools.EDITS_090}:
        return "preview"
    return "read"


def allowed(spec, profile: str) -> bool:
    return tool_class(spec) in CLASSES[profile_of(value=profile)]


def filter_catalog(catalog: dict, profile: str) -> dict:
    return {n: s for n, s in catalog.items() if allowed(s, profile)}


@contextlib.contextmanager
def profiled_catalog(profile: str):
    """While building a server: tools.catalog returns only the profile's tools (server.build_server reads
    tools.catalog at call time). A small PR to server.py (a `profile` argument) can replace this later."""
    from .. import tools
    original = tools.catalog

    def catalog(*args, **kw):
        if profile_of(value=profile) != "dev":
            kw["unsafe"] = False
            if args:
                args = (False,) + tuple(args[1:])
        return filter_catalog(original(*args, **kw), profile)
    tools.catalog = catalog
    try:
        yield
    finally:
        tools.catalog = original


def build_server(profile: str, **kw):
    """server.build_server with the profile applied (dev also turns AGR_MCP_UNSAFE on for its own catalogue)."""
    from .. import server
    profile = profile_of(value=profile)
    env = {"AGR_MCP_UNSAFE": "1"} if profile == "dev" else {}
    with profiled_catalog(profile):
        return server.build_server(env=env, **kw)
