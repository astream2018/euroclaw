"""Firecracker microVM sandbox backend.

Real host-side implementation providing hardware-virtualized (KVM) isolation.
It requires a Linux host with ``/dev/kvm`` and the ``firecracker`` binary, so
it will not run in every environment. When KVM is unavailable it raises
:class:`SandboxUnavailable` rather than silently degrading.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import socket
import subprocess
import sys
import time

import requests_unixsocket

from .base import Sandbox, SandboxResult, SandboxUnavailable

logger = logging.getLogger(__name__)


class FirecrackerMicroVM(Sandbox):
    """MicroVM-isolated sandbox backed by AWS Firecracker on a KVM host."""

    isolation_level = "microvm"

    def __init__(self, task_id: str) -> None:
        self.task_id = task_id
        self.socket_path = f"/tmp/firecracker-{task_id}.socket"  # nosec B108
        self.vsock_uds_path = f"/tmp/firecracker-{task_id}_vsock.sock"  # nosec B108
        # requests_unixsocket addresses a UDS by URL-encoding the socket path.
        encoded = self.socket_path.replace("/", "%2F")
        self.base_url = f"http+unix://{encoded}"
        self.kernel_path = os.getenv("FC_KERNEL_PATH", "/opt/euroclaw/vmlinux")
        self.base_rootfs = os.getenv("FC_ROOTFS_PATH", "/opt/euroclaw/rootfs.ext4")
        self.ephemeral_rootfs = f"/tmp/rootfs-{task_id}.ext4"  # nosec B108
        self.guest_port = int(os.getenv("FC_GUEST_PORT", "5252"))
        self.session = requests_unixsocket.Session()
        self.fc_process: subprocess.Popen | None = None

    # -- lifecycle ---------------------------------------------------------

    def _check_kvm(self) -> None:
        """Verify this host can run Firecracker; raise otherwise."""
        if sys.platform != "linux" or not os.path.exists("/dev/kvm"):
            raise SandboxUnavailable(
                "Firecracker backend requires a KVM-enabled Linux host "
                "(/dev/kvm not available on this platform). Run on such a "
                "host, or set SANDBOX_BACKEND=subprocess to use the "
                "process-level sandbox."
            )

    def _ensure_ok(self, resp, step: str) -> None:
        """Raise RuntimeError if a Firecracker API response is an error."""
        if resp.status_code >= 400:
            body = getattr(resp, "text", "")
            raise RuntimeError(
                f"firecracker API step {step!r} failed with status "
                f"{resp.status_code}: {body}"
            )

    def boot(self) -> None:
        self._check_kvm()

        # Give the VM its own writable copy of the base image.
        shutil.copyfile(self.base_rootfs, self.ephemeral_rootfs)

        fc_binary = os.getenv("FC_BINARY", "/usr/bin/firecracker")
        # NOTE: FC_USE_JAILER is documented for production hardening; when set,
        # operators are expected to wrap the binary with the jailer. This
        # implementation keeps things simple and invokes the binary directly.
        if os.getenv("FC_USE_JAILER"):
            logger.info(
                "FC_USE_JAILER is set; jailer wrapping is a deployment "
                "concern and is not applied by this backend."
            )
        self.fc_process = subprocess.Popen([fc_binary, "--api-sock", self.socket_path])

        # Give the API socket a moment to come up.
        time.sleep(0.5)

        boot_source = {
            "kernel_image_path": self.kernel_path,
            "boot_args": "console=ttyS0 reboot=k panic=1 pci=off",
        }
        resp = self.session.put(
            f"{self.base_url}/boot-source", json=boot_source, timeout=10
        )
        self._ensure_ok(resp, "boot-source")

        drive = {
            "drive_id": "rootfs",
            "path_on_host": self.ephemeral_rootfs,
            "is_root_device": True,
            "is_read_only": False,
        }
        resp = self.session.put(
            f"{self.base_url}/drives/rootfs", json=drive, timeout=10
        )
        self._ensure_ok(resp, "drive")

        machine_config = {
            "vcpu_count": int(os.getenv("FC_VCPUS", "1")),
            "mem_size_mib": int(os.getenv("FC_MEM_MIB", "256")),
        }
        resp = self.session.put(
            f"{self.base_url}/machine-config",
            json=machine_config,
            timeout=10,
        )
        self._ensure_ok(resp, "machine-config")

        vsock = {
            "guest_cid": 3,
            "uds_path": self.vsock_uds_path,
        }
        resp = self.session.put(f"{self.base_url}/vsock", json=vsock, timeout=10)
        self._ensure_ok(resp, "vsock")

        action = {"action_type": "InstanceStart"}
        resp = self.session.put(f"{self.base_url}/actions", json=action, timeout=10)
        self._ensure_ok(resp, "actions")

    # -- execution ---------------------------------------------------------

    def _guest_rpc(self, payload: dict, timeout: int) -> dict:
        """Send a request to the guest agent over the vsock UDS proxy."""
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        try:
            sock.connect(self.vsock_uds_path)
            # Firecracker vsock proxy expects a CONNECT handshake first.
            sock.sendall(f"CONNECT {self.guest_port}\n".encode())

            handshake = self._read_line(sock)
            if not handshake.startswith("OK"):
                raise RuntimeError(
                    f"unexpected vsock handshake response: {handshake!r}"
                )

            line = json.dumps(payload) + "\n"
            sock.sendall(line.encode())

            response_line = self._read_line(sock)
            return json.loads(response_line)
        finally:
            try:
                sock.close()
            except Exception:
                pass

    @staticmethod
    def _read_line(sock: socket.socket) -> str:
        """Read a single newline-terminated line from a socket."""
        chunks: list[bytes] = []
        while True:
            byte = sock.recv(1)
            if not byte:
                break
            if byte == b"\n":
                break
            chunks.append(byte)
        return b"".join(chunks).decode(errors="replace")

    def execute(
        self, tool_name: str, arguments: str, *, timeout: int = 30
    ) -> SandboxResult:
        payload = {"tool": tool_name, "arguments": arguments}
        try:
            data = self._guest_rpc(payload, timeout)
            return SandboxResult(
                stdout=data.get("stdout", ""),
                stderr=data.get("stderr", ""),
                exit_code=int(data.get("exit_code", 0)),
                backend="firecracker",
                isolation_level="microvm",
            )
        except Exception as exc:  # noqa: BLE001 - report, never raise
            return SandboxResult(
                stdout="",
                stderr=f"microVM guest agent communication failed: {exc}",
                exit_code=1,
                backend="firecracker",
                isolation_level="microvm",
            )

    # -- teardown ----------------------------------------------------------

    def teardown(self) -> None:
        if self.fc_process is not None:
            try:
                self.fc_process.kill()
            except Exception:
                pass
            self.fc_process = None

        for path in (
            self.socket_path,
            self.vsock_uds_path,
            self.ephemeral_rootfs,
        ):
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass
