"""HTTP wrapper for jqktrader.

This module exposes the public interfaces of a trader instance over HTTP
without introducing third-party web framework dependencies.
"""

from __future__ import annotations

import argparse
import inspect
import json
import os
import sys
import threading
import traceback
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Iterable, Tuple
from urllib.parse import parse_qs, urlparse


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
DEFAULT_EXE_PATH = r"C:\thshrj\thsh\xiadan.exe"
DEFAULT_TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

from jqktrader.api import use


class ObjectRegistry:
    """Stores non-JSON-native objects and returns opaque handles."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._objects: Dict[str, Any] = {}

    def put(self, value: Any) -> str:
        handle = uuid.uuid4().hex
        with self._lock:
            self._objects[handle] = value
        return handle

    def get(self, handle: str) -> Any:
        with self._lock:
            if handle not in self._objects:
                raise KeyError("unknown object handle: %s" % handle)
            return self._objects[handle]


def _is_public(name: str) -> bool:
    return not name.startswith("_")


def _iter_public_members(target: Any) -> Iterable[Tuple[str, Any]]:
    for name in dir(target):
        if not _is_public(name):
            continue
        yield name, inspect.getattr_static(target, name)


def _describe_member(target: Any, name: str, descriptor: Any) -> Dict[str, Any]:
    entry = {
        "name": name,
        "kind": "attribute",
        "doc": inspect.getdoc(descriptor) or "",
    }
    if isinstance(descriptor, property):
        entry["kind"] = "property"
        return entry

    member = getattr(target, name)
    if callable(member):
        entry["kind"] = "method"
        try:
            entry["signature"] = str(inspect.signature(member))
        except (TypeError, ValueError):
            entry["signature"] = "(...)"
    return entry


class TraderHttpService:
    """Stateful HTTP facade for a single trader instance."""

    def __init__(
        self,
        trader: Any,
        auto_connect: bool = False,
        auto_connect_kwargs: Dict[str, Any] | None = None,
    ) -> None:
        self.trader = trader
        self.registry = ObjectRegistry()
        self.call_lock = threading.RLock()
        self.auto_connect = auto_connect
        self.auto_connect_kwargs = auto_connect_kwargs or {}

    def list_trader_interfaces(self) -> Dict[str, Dict[str, Any]]:
        interfaces = {}
        for name, descriptor in _iter_public_members(self.trader):
            interfaces[name] = _describe_member(self.trader, name, descriptor)
        return interfaces

    def encode(self, value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, bytes):
            return {
                "__type__": "bytes",
                "encoding": "utf-8",
                "value": value.decode("utf-8", errors="replace"),
            }
        if isinstance(value, dict):
            return {str(key): self.encode(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [self.encode(item) for item in value]
        if inspect.isclass(value):
            attrs = {}
            for name in dir(value):
                if not _is_public(name):
                    continue
                item = getattr(value, name)
                if callable(item):
                    continue
                try:
                    attrs[name] = self.encode(item)
                except Exception:
                    attrs[name] = repr(item)
            return {
                "__type__": "class",
                "name": value.__name__,
                "module": value.__module__,
                "attributes": attrs,
            }

        handle = self.registry.put(value)
        return {
            "__type__": type(value).__name__,
            "__handle__": handle,
            "repr": repr(value),
        }

    def decode(self, value: Any) -> Any:
        if isinstance(value, dict):
            if "__handle__" in value:
                return self.registry.get(value["__handle__"])
            return {key: self.decode(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self.decode(item) for item in value]
        return value

    def _coerce_query_value(self, raw: str) -> Any:
        try:
            return self.decode(json.loads(raw))
        except json.JSONDecodeError:
            return raw

    def parse_invocation_payload(self, body: bytes, query: str) -> Tuple[list, dict]:
        args = []
        kwargs = {}

        if query:
            parsed = parse_qs(query, keep_blank_values=True)
            kwargs.update(
                {
                    key: self._coerce_query_value(values[-1])
                    for key, values in parsed.items()
                }
            )

        if not body:
            return args, kwargs

        payload = self.decode(json.loads(body.decode("utf-8")))
        if isinstance(payload, list):
            args.extend(payload)
            return args, kwargs
        if isinstance(payload, dict):
            if "args" in payload or "kwargs" in payload:
                args.extend(payload.get("args", []))
                kwargs.update(payload.get("kwargs", {}))
            else:
                kwargs.update(payload)
            return args, kwargs

        args.append(payload)
        return args, kwargs

    def invoke_target(self, target: Any, name: str, args: list, kwargs: dict) -> Dict[str, Any]:
        descriptor = inspect.getattr_static(target, name)
        member = getattr(target, name)
        kind = "property" if isinstance(descriptor, property) else "method" if callable(member) else "attribute"

        if kind == "property" or not callable(member):
            if args or kwargs:
                raise TypeError("%s does not accept arguments" % name)
            result = member
        else:
            result = member(*args, **kwargs)

        return {
            "name": name,
            "kind": kind,
            "result": self.encode(result),
        }

    def invoke_trader(self, name: str, args: list, kwargs: dict) -> Dict[str, Any]:
        with self.call_lock:
            self._ensure_connected(name)
            try:
                return self.invoke_target(self.trader, name, args, kwargs)
            except Exception:
                if not self._should_reconnect_after_failure(name):
                    raise
                self._reconnect()
                return self.invoke_target(self.trader, name, args, kwargs)

    def invoke_object(self, handle: str, name: str, args: list, kwargs: dict) -> Dict[str, Any]:
        target = self.registry.get(handle)
        with self.call_lock:
            return self.invoke_target(target, name, args, kwargs)

    def describe_object(self, handle: str) -> Dict[str, Any]:
        target = self.registry.get(handle)
        return {
            "handle": handle,
            "type": type(target).__name__,
            "repr": repr(target),
            "interfaces": {
                name: _describe_member(target, name, descriptor)
                for name, descriptor in _iter_public_members(target)
            },
        }

    def _ensure_connected(self, method_name: str) -> None:
        if method_name == "connect":
            return
        if not self.auto_connect:
            return
        if self._is_connection_alive():
            return
        self._reconnect()

    def _is_connected(self) -> bool:
        return getattr(self.trader, "app", None) is not None and getattr(
            self.trader, "main", None
        ) is not None

    def _resolve_window(self, window: Any) -> Any:
        resolver = getattr(window, "wrapper_object", None)
        if callable(resolver):
            return resolver()
        return window

    def _is_connection_alive(self) -> bool:
        if not self._is_connected():
            return False

        try:
            self._resolve_window(self.trader.app.top_window())
            self._resolve_window(self.trader.main)
        except Exception:
            return False
        return True

    def _reset_connection_state(self) -> None:
        for attr in ("_app", "_main", "_toolbar"):
            if hasattr(self.trader, attr):
                setattr(self.trader, attr, None)

    def _reconnect(self) -> None:
        self._reset_connection_state()
        self.trader.connect(**self.auto_connect_kwargs)

    def _should_reconnect_after_failure(self, method_name: str) -> bool:
        if method_name == "connect":
            return False
        if not self.auto_connect:
            return False
        return not self._is_connection_alive()

    def connection_status(self) -> Dict[str, bool]:
        connected = self._is_connected()
        return {
            "connected": connected,
            "connection_alive": self._is_connection_alive() if connected else False,
            "auto_connect": self.auto_connect,
        }


def create_handler(service: TraderHttpService):
    class TraderRequestHandler(BaseHTTPRequestHandler):
        server_version = "jqktrader-http/1.0"

        def do_GET(self) -> None:
            self._dispatch()

        def do_POST(self) -> None:
            self._dispatch()

        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def _read_body(self) -> bytes:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0:
                return b""
            return self.rfile.read(length)

        def _send_json(self, payload: Dict[str, Any], status: int = HTTPStatus.OK) -> None:
            body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _dispatch(self) -> None:
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"

            try:
                if path == "/":
                    self._send_json(
                        {
                            "ok": True,
                            "service": "jqktrader-http",
                            "routes": {
                                "health": "GET /health",
                                "interfaces": "GET /interfaces",
                                "trader": "GET|POST /trader/<name>",
                                "object_info": "GET /objects/<handle>",
                                "object_call": "GET|POST /objects/<handle>/<name>",
                            },
                            "interfaces": service.list_trader_interfaces(),
                            "examples": [
                                {
                                    "name": "connect",
                                    "method": "POST",
                                    "path": "/trader/connect",
                                    "body": {
                                        "exe_path": "C:/ths/xiadan.exe",
                                        "tesseract_cmd": "C:/Program Files/Tesseract-OCR/tesseract.exe",
                                    },
                                },
                                {
                                    "name": "balance",
                                    "method": "GET",
                                    "path": "/trader/balance",
                                },
                                {
                                    "name": "buy",
                                    "method": "POST",
                                    "path": "/trader/buy",
                                    "body": {
                                        "security": "600000",
                                        "price": 10.5,
                                        "amount": 100,
                                    },
                                },
                            ],
                        }
                    )
                    return

                if path == "/health":
                    self._send_json(
                        {
                            "ok": True,
                            "status": "healthy",
                            "trader": service.connection_status(),
                        }
                    )
                    return

                if path == "/interfaces":
                    self._send_json(
                        {"ok": True, "interfaces": service.list_trader_interfaces()}
                    )
                    return

                if path.startswith("/trader/"):
                    name = path.split("/", 2)[2]
                    body = self._read_body()
                    args, kwargs = service.parse_invocation_payload(body, parsed.query)
                    result = service.invoke_trader(name, args, kwargs)
                    self._send_json({"ok": True, **result})
                    return

                if path.startswith("/objects/"):
                    parts = [item for item in path.split("/") if item]
                    if len(parts) == 2:
                        result = service.describe_object(parts[1])
                        self._send_json({"ok": True, **result})
                        return
                    if len(parts) == 3:
                        body = self._read_body()
                        args, kwargs = service.parse_invocation_payload(body, parsed.query)
                        result = service.invoke_object(parts[1], parts[2], args, kwargs)
                        self._send_json({"ok": True, **result})
                        return

                self._send_json(
                    {"ok": False, "error": {"type": "NotFound", "message": path}},
                    status=HTTPStatus.NOT_FOUND,
                )
            except KeyError as exc:
                self._send_json(
                    {
                        "ok": False,
                        "error": {
                            "type": type(exc).__name__,
                            "message": str(exc),
                        },
                    },
                    status=HTTPStatus.NOT_FOUND,
                )
            except AttributeError as exc:
                self._send_json(
                    {
                        "ok": False,
                        "error": {
                            "type": type(exc).__name__,
                            "message": str(exc),
                        },
                    },
                    status=HTTPStatus.NOT_FOUND,
                )
            except json.JSONDecodeError as exc:
                self._send_json(
                    {
                        "ok": False,
                        "error": {
                            "type": type(exc).__name__,
                            "message": "request body must be valid JSON",
                        },
                    },
                    status=HTTPStatus.BAD_REQUEST,
                )
            except Exception as exc:
                self._send_json(
                    {
                        "ok": False,
                        "error": {
                            "type": type(exc).__name__,
                            "message": str(exc),
                            "traceback": traceback.format_exc().splitlines(),
                        },
                    },
                    status=HTTPStatus.INTERNAL_SERVER_ERROR,
                )

    return TraderRequestHandler


def serve(
    host: str = "127.0.0.1",
    port: int = 8000,
    debug: bool = False,
    auto_connect: bool = True,
    connect_on_first_use: bool = False,
    **kwargs: Any
) -> None:
    trader = use(debug=debug)
    connect_kwargs = dict(kwargs)
    connect_kwargs.setdefault("exe_path", DEFAULT_EXE_PATH)
    connect_kwargs.setdefault("tesseract_cmd", DEFAULT_TESSERACT_CMD)
    connect_kwargs = {key: value for key, value in connect_kwargs.items() if value is not None}
    service = TraderHttpService(
        trader,
        auto_connect=auto_connect or connect_on_first_use,
        auto_connect_kwargs=connect_kwargs,
    )
    if auto_connect:
        trader.connect(**connect_kwargs)
    handler_class = create_handler(service)
    server = ThreadingHTTPServer((host, port), handler_class)
    print("jqktrader HTTP service listening on http://%s:%s" % (host, port))
    server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run jqktrader HTTP service")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host")
    parser.add_argument("--port", default=8000, type=int, help="Bind port")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--auto-connect", action="store_true", help="Connect trader during service startup")
    parser.add_argument(
        "--connect-on-first-use",
        action="store_true",
        help="Connect trader automatically before the first business request",
    )
    parser.add_argument(
        "--exe-path",
        default=DEFAULT_EXE_PATH,
        help="Trading client exe path",
    )
    parser.add_argument(
        "--tesseract-cmd",
        default=DEFAULT_TESSERACT_CMD,
        help="Tesseract executable path",
    )
    parser.add_argument(
        "--editor-need-type-keys",
        action="store_true",
        help="Use type_keys for editor input",
    )
    args = parser.parse_args()
    serve(
        host=args.host,
        port=args.port,
        debug=args.debug,
        auto_connect=args.auto_connect,
        connect_on_first_use=args.connect_on_first_use,
        exe_path=args.exe_path,
        tesseract_cmd=args.tesseract_cmd,
        editor_need_type_keys=args.editor_need_type_keys,
    )


if __name__ == "__main__":
    main()
