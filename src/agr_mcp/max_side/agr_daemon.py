"""new-case: agr-mcp daemon - ONE MCP server per 3ds Max instance over local Streamable HTTP (#1024 branch U).

mcp-review §3.9 / orchestrator §6 п.3: the dock, a CLI and a swarm share one Max through one daemon instead of a
stdio server per client with a file lock. The daemon:
* talks to Max only through the AGR listener (agr_listener.py, our pipe; 3dsmax-mcp is not used): the whole v1/v2
  catalogue via `Host.transport` (bridge call as data), the D108 tools via ops_d108;
* holds one lease per Max (agr_client.Leases): one call at a time, kept past a client timeout until Max is idle;
* applies the profile (agr_profiles.py) to tools/list and calls;
* serves 127.0.0.1 only: /mcp (Streamable HTTP, bearer token, DNS-rebinding protection), /agr/health,
  /agr/pending (previews waiting for the button) and /agr/apply (the dock's «Применить», after it confirmed the id
  inside Max - the daemon cannot confirm by itself);
* registers itself as daemon-<max pid>.json; a second daemon for the same Max refuses to start (`busy`).

Run: `uv run python -m agr_mcp.max_side.agr_daemon --max-pid <pid> [--profile modeller] [--port 0]`.
"""
from __future__ import annotations

import argparse
import contextlib
import hmac
import json
import os
import secrets
import sys
import time

from . import agr_client, agr_profiles, agr_registry

VERSION = "1.0.0-u1"


def build(profile: str | None = None, pin=None, env=None, token: str | None = None, host=None, store=None):
    """(starlette app, info) of a daemon; no socket is bound here (tests drive the app in-process)."""
    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
    from mcp.server.transport_security import TransportSecuritySettings
    from starlette.applications import Starlette
    from starlette.requests import Request
    from starlette.responses import JSONResponse
    from starlette.routing import Route

    from .. import ops_d108
    profile = agr_profiles.profile_of(env, profile)
    host = host or agr_client.Host(pin=pin, env=env, allow_exec=profile == "dev")
    store = store or ops_d108.Store()
    ops_d108.configure(host=host, store=store)
    server = agr_profiles.build_server(profile, max_transport=host.transport)
    token = token or secrets.token_hex(24)
    security = TransportSecuritySettings(enable_dns_rebinding_protection=True,
                                         allowed_hosts=["127.0.0.1:*", "localhost:*"],
                                         allowed_origins=["http://127.0.0.1:*", "http://localhost:*"])
    manager = StreamableHTTPSessionManager(app=server, json_response=False, stateless=False,
                                           security_settings=security)
    info = {"profile": profile, "token": token, "version": VERSION, "started": time.time()}

    def authorized(scope_headers) -> bool:
        got = dict(scope_headers).get(b"authorization", b"").decode("latin-1")
        return hmac.compare_digest(got, "Bearer " + token)

    async def mcp_app(scope, receive, send):
        if scope["type"] == "http" and not authorized(scope.get("headers") or ()):
            resp = JSONResponse({"error": "forbidden: bearer token required"}, status_code=401)
            await resp(scope, receive, send)
            return
        await manager.handle_request(scope, receive, send)

    async def health(request: Request):
        if not authorized(request.scope.get("headers") or ()):
            return JSONResponse({"error": "forbidden"}, status_code=401)
        try:
            client = host.client()
            st = client.status()
            inst = client.pid
        except Exception as exc:  # noqa: BLE001
            st, inst = {"ok": False, "error": str(exc)}, None
        return JSONResponse({"ok": True, "profile": profile, "instance": inst, "listener": st,
                             "lease_held": bool(inst and host.leases.held(inst)), "version": VERSION})

    async def pending(request: Request):
        if not authorized(request.scope.get("headers") or ()):
            return JSONResponse({"error": "forbidden"}, status_code=401)
        return JSONResponse({"pending": store.pending()})

    async def apply(request: Request):
        import anyio
        if not authorized(request.scope.get("headers") or ()):
            return JSONResponse({"error": "forbidden"}, status_code=401)
        body = await request.json()
        pid = str(body.get("preview_id", ""))
        try:
            ans = await anyio.to_thread.run_sync(ops_d108.apply_preview, pid)
        except Exception as exc:  # noqa: BLE001
            return JSONResponse({"status": "error", "error": str(exc)[:2000]}, status_code=409)
        return JSONResponse(json.loads(json.dumps(ans, default=str)))

    class _MCP:  # an ASGI app object: Route serves exactly /mcp (Mount would 307-redirect /mcp to /mcp/)
        async def __call__(self, scope, receive, send):
            await mcp_app(scope, receive, send)

    @contextlib.asynccontextmanager
    async def lifespan(_app):
        async with manager.run():
            yield

    app = Starlette(routes=[Route("/mcp", _MCP(), methods=["GET", "POST", "DELETE"]), Route("/agr/health", health),
                            Route("/agr/pending", pending), Route("/agr/apply", apply, methods=["POST"])],
                    lifespan=lifespan)
    return app, info


def mcp_config(url: str, token: str, name: str = "agr") -> dict:
    """--mcp-config JSON for the claude CLI (Streamable HTTP + bearer)."""
    return {"mcpServers": {name: {"type": "http", "url": url, "headers": {"Authorization": "Bearer " + token}}}}


def serve(max_pid: int, profile: str | None = None, port: int = 0, env=None) -> None:
    import socket

    import uvicorn
    env = os.environ if env is None else env
    entry = agr_registry.select(max_pid, env)  # the Max must have its listener already
    app, info = build(profile, pin=max_pid, env=env)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", int(port)))
    real = sock.getsockname()[1]
    url = "http://127.0.0.1:{}/mcp".format(real)
    agr_registry.write("daemon", max_pid, {"pid": max_pid, "owner_pid": os.getpid(), "port": real, "url": url,
                                           "token": info["token"], "profile": info["profile"],
                                           "started": info["started"], "version": VERSION,
                                           "max_version": entry.get("max_version")}, env)
    print(json.dumps({"url": url, "profile": info["profile"], "max_pid": max_pid}), flush=True)
    try:
        config = uvicorn.Config(app, log_level="warning", lifespan="on")
        uvicorn.Server(config).run(sockets=[sock])
    finally:
        agr_registry.remove("daemon", max_pid, env)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="agr-mcp daemon: one Streamable HTTP MCP server per 3ds Max")
    ap.add_argument("--max-pid", type=int, default=int(os.environ.get("AGR_MCP_MAX_PID") or 0) or None)
    ap.add_argument("--profile", default=None, choices=agr_profiles.PROFILES)
    ap.add_argument("--port", type=int, default=0)
    a = ap.parse_args(argv)
    if a.max_pid is None:
        live = agr_registry.entries("max")
        if len(live) != 1:
            print("pass --max-pid: live AGR listeners {}".format([e["pid"] for e in live]), file=sys.stderr)
            return 2
        a.max_pid = int(live[0]["pid"])
    try:
        serve(a.max_pid, a.profile, a.port)
    except agr_registry.RegistryError as exc:
        print(str(exc), file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
