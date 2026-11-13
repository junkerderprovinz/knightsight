import socketserver
import threading

from . import protocol


class _Loopback(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def serve(panel):
    """Listens on the loopback port, which an SSH tunnel reaches but the network does not.

    Returns None when another program holds the port, as the Windows panel does.
    """
    gate = threading.Lock()

    class Talk(socketserver.StreamRequestHandler):
        def handle(self):
            for line in self.rfile:
                # One request at a time, whichever connection it comes from.
                with gate:
                    answer = protocol.reply(line, panel)
                self.wfile.write(answer.encode("utf-8") + b"\n")
                self.wfile.flush()

    try:
        server = _Loopback(("127.0.0.1", protocol.PORT), Talk)
    except OSError:
        return None
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server
