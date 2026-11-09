"""The HTTP server class Composer uses: the standard threading server, minus the reverse DNS lookup of its own address.

http.server's server_bind() calls socket.getfqdn(host) only to fill in `server_name`, which nothing here reads. On a Mac
with no network, a VPN or a slow resolver that lookup can take a long time, and `composer up` (and `composer doctor`'s
port check) sat there before it listened. Found by the macOS CI run (the server did not answer /health in 20 s)."""
from __future__ import annotations

import socketserver
from http.server import ThreadingHTTPServer


class LocalHTTPServer(ThreadingHTTPServer):
    def server_bind(self) -> None:
        socketserver.TCPServer.server_bind(self)
        host, port = self.server_address[:2]
        self.server_name = str(host)
        self.server_port = port
