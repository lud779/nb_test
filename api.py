"""Synthetic order API used by the G3 fixture."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

DOWNLOAD_FIELD = "download_url"
CURRENT_PAGE_ONLY = True
SUPPORT_EXPIRED = False

# The fixture has 120 matched orders and five orders outside the current filter.
MATCHED_ORDERS = list(range(1, 121))
ORDERS = MATCHED_ORDERS + list(range(121, 126))


class OrdersHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        url = urlsplit(self.path)
        query = parse_qs(url.query)
        orders = MATCHED_ORDERS if query.get("matched") == ["1"] else ORDERS
        if url.path == "/":
            self.send_content("text/html", Path("page.html").read_bytes())
        elif url.path == "/orders":
            self.send_content("application/json", json.dumps({"ids": orders[:20], "total": len(orders)}).encode())
        elif url.path == "/export":
            status = "expired" if SUPPORT_EXPIRED and query.get("expired") == ["1"] else "ready"
            result = {DOWNLOAD_FIELD: "/orders.csv?" + url.query, "status": status}
            self.send_content("application/json", json.dumps(result).encode())
        elif url.path == "/orders.csv":
            exported = orders[:20] if CURRENT_PAGE_ONLY else orders
            self.send_content("text/csv", ("id\n" + "\n".join(map(str, exported)) + "\n").encode())
        else:
            self.send_error(404)

    def send_content(self, media_type: str, content: bytes) -> None:
        self.send_response(200)
        self.send_header("Content-Type", media_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format: str, *args: object) -> None:
        pass


def server(handler: type[OrdersHandler] = OrdersHandler) -> ThreadingHTTPServer:
    return ThreadingHTTPServer(("127.0.0.1", 0), handler)
