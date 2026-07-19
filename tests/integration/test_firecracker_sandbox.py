"""KVM-gated Firecracker integration test.

This is skipped automatically unless the host can actually run Firecracker
(Linux + /dev/kvm + the firecracker binary + a built kernel/rootfs). It is the
real end-to-end check for hardware-isolated execution and is meant to run on a
dedicated KVM node in CI, not on developer laptops.

Prerequisites (see deploy/firecracker/README.md):
  * FC_KERNEL_PATH points at a vmlinux
  * FC_ROOTFS_PATH points at an ext4 rootfs containing the guest agent
  * SANDBOX_BACKEND=firecracker
"""

import os
import shutil
import sys

import pytest

from euroclaw.sandbox import get_sandbox
from euroclaw.sandbox.base import SandboxUnavailable

_KVM = sys.platform == "linux" and os.path.exists("/dev/kvm")
_BINARY = shutil.which("firecracker") or os.path.exists(
    os.getenv("FC_BINARY", "/usr/bin/firecracker")
)
_IMAGES = os.path.exists(os.getenv("FC_KERNEL_PATH", "")) and os.path.exists(
    os.getenv("FC_ROOTFS_PATH", "")
)

pytestmark = pytest.mark.skipif(
    not (_KVM and _BINARY and _IMAGES),
    reason="Firecracker requires a KVM host with a built kernel + rootfs image",
)


def test_microvm_executes_python():
    sandbox = get_sandbox("firecracker")
    with sandbox:
        result = sandbox.execute("execute_python", "print(2 + 2)", timeout=30)
    assert result.isolation_level == "microvm"
    assert "4" in result.stdout


def test_check_kvm_raises_without_device(monkeypatch):
    # Even on a KVM host, verify the guard fires when /dev/kvm is hidden.
    from euroclaw.sandbox.firecracker import FirecrackerMicroVM

    monkeypatch.setattr(os.path, "exists", lambda p: False)
    vm = FirecrackerMicroVM(task_id="guard-test")
    with pytest.raises(SandboxUnavailable):
        vm.boot()
