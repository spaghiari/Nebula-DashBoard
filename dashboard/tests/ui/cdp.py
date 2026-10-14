"""Client CDP minimal (stdlib) : WebSocket texte + Runtime.evaluate.

Suffisant pour piloter Edge/Chrome headless depuis un test : pas de
dépendance (ni selenium ni websocket-client).
"""
from __future__ import annotations

import base64
import http.client
import json
import os
import socket
import struct
import time
import urllib.parse


class CDP:
    def __init__(self, ws_url: str, timeout: float = 60):
        u = urllib.parse.urlparse(ws_url)
        self.sock = socket.create_connection((u.hostname, u.port), timeout=timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        req = (f"GET {u.path} HTTP/1.1\r\nHost: {u.hostname}:{u.port}\r\nUpgrade: websocket\r\n"
               f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n")
        self.sock.sendall(req.encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("handshake WebSocket interrompu")
            buf += chunk
        if b" 101 " not in buf.split(b"\r\n", 1)[0]:
            raise ConnectionError("handshake WebSocket refusé")
        self._rest = buf.split(b"\r\n\r\n", 1)[1]
        self.id = 0
        self.events: list[dict] = []

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass

    def _recv_exact(self, n: int) -> bytes:
        while len(self._rest) < n:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise ConnectionError("WebSocket fermé")
            self._rest += chunk
        out, self._rest = self._rest[:n], self._rest[n:]
        return out

    def _recv_frame(self) -> str:
        msg = b""
        while True:
            b1, b2 = self._recv_exact(2)
            fin, op = b1 & 0x80, b1 & 0x0F
            ln = b2 & 0x7F
            if ln == 126:
                ln = struct.unpack(">H", self._recv_exact(2))[0]
            elif ln == 127:
                ln = struct.unpack(">Q", self._recv_exact(8))[0]
            data = self._recv_exact(ln)
            if op == 9:  # ping : ignoré (le navigateur ne l'exige pas en local)
                continue
            msg += data
            if fin:
                return msg.decode("utf-8", "replace")

    def _send(self, text: str) -> None:
        data = text.encode()
        hdr = bytes([0x81])
        mask = os.urandom(4)
        ln = len(data)
        if ln < 126:
            hdr += bytes([0x80 | ln])
        elif ln < 65536:
            hdr += bytes([0x80 | 126]) + struct.pack(">H", ln)
        else:
            hdr += bytes([0x80 | 127]) + struct.pack(">Q", ln)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
        self.sock.sendall(hdr + mask + masked)

    def call(self, method: str, **params):
        self.id += 1
        my = self.id
        self._send(json.dumps({"id": my, "method": method, "params": params}))
        while True:
            m = json.loads(self._recv_frame())
            if m.get("id") == my:
                if "error" in m:
                    raise RuntimeError(m["error"])
                return m.get("result")
            self.events.append(m)

    def js(self, expr: str, timeout: int = 30000):
        r = self.call("Runtime.evaluate", expression=expr, awaitPromise=True,
                      returnByValue=True, timeout=timeout)
        if r.get("exceptionDetails"):
            raise RuntimeError(json.dumps(r["exceptionDetails"])[:800])
        return r["result"].get("value")


def page_ws(port: int, timeout: float = 20) -> str:
    """URL WebSocket de la première page ouverte par le navigateur."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        # http.client et non urllib : urllib consulte le proxy système.
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
        try:
            conn.request("GET", "/json/list")
            tabs = json.loads(conn.getresponse().read())
            pages = [t for t in tabs if t.get("type") == "page"]
            if pages:
                return pages[0]["webSocketDebuggerUrl"]
        except (OSError, ValueError):
            pass
        finally:
            conn.close()
        time.sleep(0.2)
    raise RuntimeError("aucune page CDP")
