"""Run one check against the real HTTP API or browser and write its evidence report."""

import argparse
import json
import os
import re
import shutil
import subprocess
from contextlib import contextmanager
from hashlib import sha256
from html import unescape
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from urllib.request import urlopen

from api import OrdersHandler, server

SPEC = Path("specs/001-order-export")
CHECKS = {
    "g3-order-contract": ("E2E-contract", SPEC / "contract.json"),
    "g3-order-e2e": ("E2E-export", SPEC / "export.json"),
}


class TestHandler(OrdersHandler):
    def do_GET(self) -> None:
        if self.path == "/browser-probe":
            self.send_content("text/html", Path("browser_probe.html").read_bytes())
        else:
            super().do_GET()


@contextmanager
def listening():
    with server(TestHandler) as application:
        worker = Thread(target=application.serve_forever, daemon=True)
        worker.start()
        try:
            yield f"http://127.0.0.1:{application.server_port}"
        finally:
            application.shutdown()
            worker.join()


def contract(base, spec):
    with urlopen(base + "/export?matched=1", timeout=5) as response:
        body = json.load(response)
    field = spec["download_field"]
    assert isinstance(body.get(field), str) and body[field].startswith("/orders.csv"), (
        f"expected {field}, received {sorted(body)}"
    )
    assert body["status"] == spec["initial_status"], body
    return f"API returned {field} and status {body['status']}"


def browser(base, spec):
    chrome = os.environ.get("CHROME_BIN") or shutil.which("google-chrome")
    if not chrome:
        chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    with TemporaryDirectory(prefix="g3-browser-") as profile:
        response = subprocess.run(
            [chrome, "--headless", "--no-sandbox", "--disable-gpu", "--virtual-time-budget=12000",
             f"--user-data-dir={profile}", "--dump-dom", base + "/browser-probe"],
            capture_output=True, text=True, timeout=40, check=True,
        )
    result = re.search(r'<pre id="report">(.*?)</pre>', response.stdout, re.S)
    assert result and result[1] != "PENDING", "Browser did not produce an E2E result"
    report = json.loads(unescape(result[1]))
    assert "error" not in report, report
    assert report["visible"] == spec["list_page_size"], report
    first, last = spec["expected_ids"]
    assert report["ids"] == list(range(first, last + 1)), (
        f"expected {last - first + 1} matched orders, downloaded {len(report['ids'])}"
    )
    assert report["ready"] == "ready", report
    if spec["expired_status"] is not None:
        assert report["expired"] == spec["expired_status"] and not report["expired_download"], (
            f"expected expired with download disabled, got {report['expired']}"
        )
    return f"Browser displayed {report['visible']} rows and downloaded {len(report['ids'])} matched orders" + (
        f"; observed {report['expired']} with download disabled" if spec["expired_status"] else ""
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("check", choices=CHECKS)
    parser.add_argument("--environment", required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    scenario, path = CHECKS[args.check]
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    spec_digest = sha256(sha256(str(path).encode()).digest() + sha256(path.read_bytes()).digest()).hexdigest()
    test = contract if args.check == "g3-order-contract" else browser
    with listening() as base:
        try:
            summary = test(base, json.loads(path.read_text()))
            outcome = "passed"
        except AssertionError as failure:
            summary = str(failure)
            outcome = "failed"
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps({
        "check_id": args.check, "scenario_id": scenario, "kind": "test", "commit": commit,
        "spec_digest": spec_digest, "environment": args.environment, "outcome": outcome, "summary": summary,
    }) + "\n")
    print(summary)
    return int(outcome == "failed")


if __name__ == "__main__":
    raise SystemExit(main())
