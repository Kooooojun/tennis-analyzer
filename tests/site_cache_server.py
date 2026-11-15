"""Local-only Range server for media E2E; --root holds private fixtures, --log records case IDs only."""
import argparse
import json
import re
import threading
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def send_head(self):
        path = Path(self.translate_path(self.path))
        if path.suffix != ".mp4" or not path.is_file():
            return super().send_head()
        query = parse_qs(urlsplit(self.path).query)
        size = path.stat().st_size
        match = re.fullmatch(r"bytes=(\d+)-(\d*)", self.headers.get("Range", ""))
        start = int(match[1]) if match else 0
        end = min(int(match[2]), size - 1) if match and match[2] else size - 1
        if start > end:
            self.send_error(416)
            return None
        self.send_response(206 if match else 200)
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-store")
        if match:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        self.media = dict(case=query.get("case", [""])[0], start=start, left=end - start + 1,
                          gap=float(query.get("gap", [0])[0]), interval=float(query.get("interval", [0])[0]))
        stream = path.open("rb")
        stream.seek(start)
        self.record("request", start=start)
        return stream

    def record(self, event, **fields):
        with self.server.log_lock:
            with self.server.event_log.open("a", encoding="utf-8") as log:
                log.write(json.dumps(dict(case=self.media["case"], event=event, time=time.monotonic(), **fields)) + "\n")

    def copyfile(self, source, outputfile):
        if not hasattr(self, "media"):
            return super().copyfile(source, outputfile)
        left, sent = self.media["left"], 0
        try:
            while left:
                data = source.read(min(left, 65536))
                if not data:
                    break
                outputfile.write(data)
                outputfile.flush()
                sent += len(data)
                left -= len(data)
                if sent == len(data) and self.media["gap"]:
                    self.record("pause", bytes=sent)
                    time.sleep(self.media["gap"])
                elif left and self.media["interval"]:
                    time.sleep(self.media["interval"])
            self.record("complete", bytes=sent)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            self.record("abort", bytes=sent)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--port", type=int, default=18763)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), partial(Handler, directory=str(args.root)))
    server.event_log, server.log_lock = args.log, threading.Lock()
    server.serve_forever()
