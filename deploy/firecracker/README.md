# Firecracker microVM backend

Hardware-isolated (KVM) execution for untrusted agent code. Each tool call boots
a disposable microVM, runs the tool via the in-VM guest agent over `virtio-vsock`,
and destroys the VM.

## Requirements

- A **bare-metal or nested-virtualization Linux host** with `/dev/kvm`.
- The [`firecracker`](https://github.com/firecracker-microvm/firecracker) binary.
- A kernel image and an ext4 rootfs that contains Python + the EuroClaw guest agent
  ([`euroclaw/sandbox/guest_agent.py`](../../euroclaw/sandbox/guest_agent.py)),
  auto-started on boot and listening on the vsock port (`FC_GUEST_PORT`, default 5252).

## Build the images

```bash
sudo bash deploy/firecracker/build-rootfs.sh
# -> /opt/euroclaw/vmlinux and /opt/euroclaw/rootfs.ext4
```

## Enable the backend

```env
SANDBOX_BACKEND=firecracker
FC_KERNEL_PATH=/opt/euroclaw/vmlinux
FC_ROOTFS_PATH=/opt/euroclaw/rootfs.ext4
FC_BINARY=/usr/bin/firecracker
FC_GUEST_PORT=5252
```

## Verify

```bash
SANDBOX_BACKEND=firecracker pytest tests/integration/test_firecracker_sandbox.py -q
```

The test auto-skips on hosts without KVM + the binary + built images. On a proper
KVM node it boots a real microVM and asserts `print(2+2)` returns `4` from inside
hardware isolation.

## Production hardening

- Wrap the binary with Firecracker's **`jailer`** (cgroups, chroot, namespaces).
- Give each VM a network namespace with **no egress** unless a tool needs it.
- Use a **read-only** base rootfs + a copy-on-write overlay per task.
- Pin CPU/memory (`FC_VCPUS`, `FC_MEM_MIB`) and enforce per-task timeouts.
