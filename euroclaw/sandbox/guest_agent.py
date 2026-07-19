"""EuroClaw microVM guest agent.

This runs *inside* the Firecracker microVM rootfs. It listens on an ``AF_VSOCK``
port for one-line JSON requests from the host-side
:class:`~euroclaw.sandbox.firecracker.FirecrackerMicroVM`, executes the requested
tool, and returns a one-line JSON result. Pure stdlib so it runs in a minimal
rootfs with just Python.

Wire protocol (newline-delimited JSON, one request per connection)::

    -> {"tool": "execute_python", "arguments": "print(1+1)"}
    <- {"stdout": "2\n", "stderr": "", "exit_code": 0}

Firecracker handles the host ``CONNECT <port>`` handshake and forwards the
stream to this listener, so the agent only deals with the JSON payload.

Run inside the VM (e.g. from an init script)::

    python3 -m euroclaw.sandbox.guest_agent --port 5252
"""

from __future__ import annotations

import argparse
import json
import logging
import socket
import subprocess  # nosec B404
import sys

logging.basicConfig(level=logging.INFO, format="guest-agent: %(message)s")
logger = logging.getLogger(__name__)

# VMADDR_CID_ANY may be absent on non-Linux dev machines importing this module.
_CID_ANY = getattr(socket, "VMADDR_CID_ANY", 0xFFFFFFFF)


def run_tool(tool_name: str, arguments: str, timeout: int = 30) -> dict:
    """Execute a tool locally inside the VM and capture output."""
    if tool_name in {"execute_python", "python_compiler", "python"}:
        cmd = [sys.executable, "-c", arguments]
    else:
        # execute_bash / run_bash / anything else -> shell command.
        cmd = ["/bin/sh", "-c", arguments]  # nosec B603 B607
    try:
        proc = subprocess.run(  # nosec B603
            cmd, capture_output=True, text=True, timeout=timeout
        )
        return {
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "exit_code": proc.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": f"timed out after {timeout}s", "exit_code": 124}
    except Exception as exc:  # noqa: BLE001
        return {"stdout": "", "stderr": str(exc), "exit_code": 1}


def _read_line(conn: socket.socket) -> str:
    chunks: list[bytes] = []
    while True:
        byte = conn.recv(1)
        if not byte or byte == b"\n":
            break
        chunks.append(byte)
    return b"".join(chunks).decode(errors="replace")


def serve(port: int) -> None:
    if not hasattr(socket, "AF_VSOCK"):
        raise RuntimeError(
            "AF_VSOCK is unavailable; the guest agent must run on Linux inside "
            "the microVM."
        )
    server = socket.socket(socket.AF_VSOCK, socket.SOCK_STREAM)
    server.bind((_CID_ANY, port))
    server.listen(16)
    logger.info("listening on vsock port %s", port)
    while True:
        conn, _ = server.accept()
        try:
            request = _read_line(conn)
            payload = json.loads(request) if request else {}
            result = run_tool(payload.get("tool", ""), payload.get("arguments", ""))
            conn.sendall((json.dumps(result) + "\n").encode())
        except Exception as exc:  # noqa: BLE001
            error = {
                "stdout": "",
                "stderr": f"guest agent error: {exc}",
                "exit_code": 1,
            }
            try:
                conn.sendall((json.dumps(error) + "\n").encode())
            except Exception:
                pass
        finally:
            try:
                conn.close()
            except Exception:
                pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="EuroClaw microVM guest agent")
    parser.add_argument("--port", type=int, default=5252)
    args = parser.parse_args(argv)
    serve(args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
