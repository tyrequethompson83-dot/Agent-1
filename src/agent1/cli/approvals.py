from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from agent1.approvals_bridge import ExternalApprovalsBridge
from agent1.config import Settings


def _default_config() -> dict[str, Any]:
    return {
        "version": 1,
        "protocol": "exec-approvals.v1",
        "socket": {"path": "", "token": ""},
        "tcp": {"host": "", "port": 0},
        "socketPath": "",
        "authToken": "",
        "host": "",
        "port": 0,
        "permissions": {"default": "ask", "allow": [], "deny": []},
    }


def _normalize_list(values: list[Any]) -> list[str]:
    normalized = sorted({str(item).strip() for item in values if str(item).strip()})
    return normalized


def _load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return _default_config()
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        if not isinstance(data, dict):
            return _default_config()
        return data
    except Exception:
        return _default_config()


def _save_config(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _extract_endpoint(config: dict[str, Any]) -> tuple[str, str, str, int]:
    socket_cfg = config.get("socket", {}) if isinstance(config.get("socket"), dict) else {}
    tcp_cfg = config.get("tcp", {}) if isinstance(config.get("tcp"), dict) else {}
    socket_path = str(socket_cfg.get("path", "")).strip() or str(config.get("socketPath", "")).strip()
    token = str(socket_cfg.get("token", "")).strip() or str(config.get("authToken", "")).strip()
    host = str(tcp_cfg.get("host", "")).strip() or str(config.get("host", "")).strip()
    try:
        port = int(tcp_cfg.get("port", 0) or config.get("port", 0) or 0)
    except Exception:
        port = 0
    return socket_path, token, host, port


def _set_endpoint(
    config: dict[str, Any],
    socket_path: str | None,
    token: str | None,
    host: str | None,
    port: int | None,
) -> None:
    existing = config.get("socket", {}) if isinstance(config.get("socket"), dict) else {}
    existing_tcp = config.get("tcp", {}) if isinstance(config.get("tcp"), dict) else {}
    try:
        existing_port = int(existing_tcp.get("port", 0) or 0)
    except Exception:
        existing_port = 0
    cfg = {
        "path": str(socket_path).strip() if socket_path is not None else str(existing.get("path", "")).strip(),
        "token": str(token).strip() if token is not None else str(existing.get("token", "")).strip(),
    }
    config["socket"] = cfg
    config["socketPath"] = cfg["path"]
    config["authToken"] = cfg["token"]
    tcp_cfg = {
        "host": str(host).strip() if host is not None else str(existing_tcp.get("host", "")).strip(),
        "port": int(port) if port is not None else existing_port,
    }
    config["tcp"] = tcp_cfg
    config["host"] = tcp_cfg["host"]
    config["port"] = tcp_cfg["port"]


def _permissions(config: dict[str, Any]) -> dict[str, Any]:
    permissions = config.get("permissions", {}) if isinstance(config.get("permissions"), dict) else {}
    default_action = str(permissions.get("default", "ask")).strip().lower()
    if default_action not in {"ask", "allow", "deny"}:
        default_action = "ask"
    allow = _normalize_list(list(permissions.get("allow", [])))
    deny = _normalize_list(list(permissions.get("deny", [])))
    return {"default": default_action, "allow": allow, "deny": deny}


def _set_permissions(config: dict[str, Any], permissions: dict[str, Any]) -> None:
    config["permissions"] = {
        "default": permissions["default"],
        "allow": _normalize_list(list(permissions["allow"])),
        "deny": _normalize_list(list(permissions["deny"])),
    }


def _print_summary(config_path: Path, config: dict[str, Any]) -> None:
    socket_path, token, host, port = _extract_endpoint(config)
    perms = _permissions(config)
    token_masked = "[empty]" if not token else f"{token[:4]}...{token[-4:]}" if len(token) > 8 else "***"
    transport = "tcp" if host and port > 0 else "unix"
    print(f"Config: {config_path}")
    print(f"Protocol: {config.get('protocol', 'exec-approvals.v1')}")
    if transport == "tcp":
        print(f"TCP endpoint: {host}:{port}")
        print(f"Socket path: {socket_path or '[unused]'}")
    else:
        print(f"Socket path: {socket_path or '[empty]'}")
        print("TCP endpoint: [not set]")
    print(f"Token: {token_masked}")
    print(f"Default permission: {perms['default']}")
    print(f"Allowlist: {', '.join(perms['allow']) or '[none]'}")
    print(f"Denylist: {', '.join(perms['deny']) or '[none]'}")


def _probe_socket(settings: Settings, config_path: Path, timeout_seconds: int | None = None) -> tuple[bool, str]:
    probe = settings.model_copy(deep=True)
    probe.external_approvals_enabled = True
    probe.external_approvals_config_path = config_path
    if timeout_seconds is not None:
        probe.external_approvals_timeout_seconds = max(1, int(timeout_seconds))
    bridge = ExternalApprovalsBridge(probe)
    return bridge.socket_reachable()


def run_approvals_cli(settings: Settings, argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agent1 approvals", description="Manage external approvals daemon config.")
    parser.add_argument("--config", default=str(settings.external_approvals_config_path))
    parser.add_argument("--timeout", type=int, default=None)
    sub = parser.add_subparsers(dest="command", required=True)

    get_parser = sub.add_parser("get", help="Print current approvals config.")
    get_parser.add_argument("--json", action="store_true")
    get_parser.add_argument("--check", action="store_true", help="Also test socket reachability.")

    set_parser = sub.add_parser("set", help="Set daemon socket path/token.")
    set_parser.add_argument("--socket-path", dest="socket_path", default=None)
    set_parser.add_argument("--token", default=None)
    set_parser.add_argument("--host", default=None, help="TCP host for Windows-friendly approvals transport.")
    set_parser.add_argument("--port", type=int, default=None, help="TCP port for Windows-friendly approvals transport.")

    default_parser = sub.add_parser("default", help="Set default permission behavior.")
    default_parser.add_argument("value", choices=["ask", "allow", "deny"])

    allow_parser = sub.add_parser("allowlist", help="Manage allowlist entries.")
    allow_sub = allow_parser.add_subparsers(dest="allow_action", required=True)
    allow_sub.add_parser("list")
    allow_add = allow_sub.add_parser("add")
    allow_add.add_argument("item")
    allow_remove = allow_sub.add_parser("remove")
    allow_remove.add_argument("item")
    allow_sub.add_parser("clear")

    deny_parser = sub.add_parser("denylist", help="Manage denylist entries.")
    deny_sub = deny_parser.add_subparsers(dest="deny_action", required=True)
    deny_sub.add_parser("list")
    deny_add = deny_sub.add_parser("add")
    deny_add.add_argument("item")
    deny_remove = deny_sub.add_parser("remove")
    deny_remove.add_argument("item")
    deny_sub.add_parser("clear")

    check_parser = sub.add_parser("check", help="Check daemon socket handshake.")
    check_parser.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    config_path = Path(os.path.expandvars(os.path.expanduser(str(args.config)))).resolve()
    config = _load_config(config_path)

    if args.command == "get":
        if args.json:
            print(json.dumps(config, indent=2))
        else:
            _print_summary(config_path=config_path, config=config)
        if args.check:
            ok, details = _probe_socket(settings=settings, config_path=config_path, timeout_seconds=args.timeout)
            status = "OK" if ok else "FAIL"
            print(f"Daemon check: [{status}] {details}")
            return 0 if ok else 1
        return 0

    if args.command == "set":
        if args.socket_path is None and args.token is None and args.host is None and args.port is None:
            print("Nothing changed. Provide --socket-path/--token or --host/--port.")
            return 1
        _set_endpoint(
            config,
            socket_path=args.socket_path,
            token=args.token,
            host=args.host,
            port=args.port,
        )
        _set_permissions(config, _permissions(config))
        _save_config(config_path, config)
        _print_summary(config_path, config)
        return 0

    if args.command == "default":
        perms = _permissions(config)
        perms["default"] = args.value
        _set_permissions(config, perms)
        _save_config(config_path, config)
        _print_summary(config_path, config)
        return 0

    if args.command == "allowlist":
        perms = _permissions(config)
        if args.allow_action == "list":
            print("\n".join(perms["allow"]) if perms["allow"] else "[none]")
            return 0
        if args.allow_action == "add":
            perms["allow"] = _normalize_list([*perms["allow"], args.item])
        elif args.allow_action == "remove":
            perms["allow"] = [item for item in perms["allow"] if item != args.item]
        elif args.allow_action == "clear":
            perms["allow"] = []
        _set_permissions(config, perms)
        _save_config(config_path, config)
        print("\n".join(perms["allow"]) if perms["allow"] else "[none]")
        return 0

    if args.command == "denylist":
        perms = _permissions(config)
        if args.deny_action == "list":
            print("\n".join(perms["deny"]) if perms["deny"] else "[none]")
            return 0
        if args.deny_action == "add":
            perms["deny"] = _normalize_list([*perms["deny"], args.item])
        elif args.deny_action == "remove":
            perms["deny"] = [item for item in perms["deny"] if item != args.item]
        elif args.deny_action == "clear":
            perms["deny"] = []
        _set_permissions(config, perms)
        _save_config(config_path, config)
        print("\n".join(perms["deny"]) if perms["deny"] else "[none]")
        return 0

    if args.command == "check":
        ok, details = _probe_socket(settings=settings, config_path=config_path, timeout_seconds=args.timeout)
        if args.json:
            print(json.dumps({"ok": ok, "details": details}, indent=2))
        else:
            print(f"[{'OK' if ok else 'FAIL'}] {details}")
        return 0 if ok else 1

    print("Unknown approvals command.")
    return 1
