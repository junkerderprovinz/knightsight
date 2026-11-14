"""What the smoke tests share: processes they start, waiting, pictures and the MCP server."""

import base64
import json
import os
import socket
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
LINUX = os.path.dirname(HERE)
REPO = os.path.dirname(LINUX)
sys.path.insert(0, LINUX)

import gi  # noqa: E402

gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf  # noqa: E402

from knightsight import protocol  # noqa: E402

started = []


def run(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout.strip()


def spawn(*args, **kw):
    p = subprocess.Popen(args, **kw)
    started.append(p)
    return p


def stop_all():
    for p in reversed(started):
        p.kill()
        p.wait()


def wait_for(check, what, seconds=15):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        value = check()
        if value:
            return value
        time.sleep(0.1)
    raise AssertionError("timed out waiting for " + what)


def pixbuf(png):
    loader = GdkPixbuf.PixbufLoader()
    loader.write(base64.b64decode(png))
    loader.close()
    return loader.get_pixbuf()


def pixel_of(pb, x, y):
    data = pb.get_pixels()
    i = y * pb.get_rowstride() + x * pb.get_n_channels()
    return tuple(data[i:i + 3])


def pixel(png, x, y):
    return pixel_of(pixbuf(png), x, y)


def listening():
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", protocol.PORT)) == 0


class Mcp:
    def __init__(self):
        self.p = spawn("node", os.path.join(REPO, "mcp", "knightsight-mcp.mjs"), stdin=subprocess.PIPE,
                       stdout=subprocess.PIPE, text=True)
        self.n = 0
        self.call("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}})

    def call(self, method, params):
        self.n += 1
        self.p.stdin.write(json.dumps({"jsonrpc": "2.0", "id": self.n, "method": method, "params": params}) + "\n")
        self.p.stdin.flush()
        return json.loads(self.p.stdout.readline())["result"]

    def tool(self, name, **args):
        return self.call("tools/call", {"name": name, "arguments": args})


def text_of(result):
    return "\n".join(c["text"] for c in result["content"] if c["type"] == "text")


def image_of(result):
    return next(c["data"] for c in result["content"] if c["type"] == "image")
