#!/usr/bin/env bash
# Build a minimal ext4 rootfs containing Python + the EuroClaw guest agent,
# plus fetch a Firecracker-compatible kernel. Run on a Linux host with root.
#
#   sudo bash deploy/firecracker/build-rootfs.sh
#
# Outputs (defaults match .env_example):
#   /opt/euroclaw/vmlinux
#   /opt/euroclaw/rootfs.ext4
set -euo pipefail

OUT_DIR="${OUT_DIR:-/opt/euroclaw}"
ROOTFS="${OUT_DIR}/rootfs.ext4"
KERNEL="${OUT_DIR}/vmlinux"
SIZE_MB="${SIZE_MB:-512}"
GUEST_PORT="${FC_GUEST_PORT:-5252}"

mkdir -p "${OUT_DIR}"

# 1. Kernel: reuse a known-good Firecracker CI kernel if not present.
if [[ ! -f "${KERNEL}" ]]; then
  echo "Downloading a Firecracker-compatible kernel..."
  ARCH="$(uname -m)"
  curl -fsSL -o "${KERNEL}" \
    "https://s3.amazonaws.com/spec.ccfc.min/firecracker-ci/v1.10/${ARCH}/vmlinux-6.1.128"
fi

# 2. Rootfs: Alpine + python3 + the guest agent, started at boot.
echo "Building ${ROOTFS} (${SIZE_MB}MB)..."
dd if=/dev/zero of="${ROOTFS}" bs=1M count="${SIZE_MB}"
mkfs.ext4 -q "${ROOTFS}"

MNT="$(mktemp -d)"
mount -o loop "${ROOTFS}" "${MNT}"
trap 'umount "${MNT}" 2>/dev/null || true; rmdir "${MNT}" 2>/dev/null || true' EXIT

docker export "$(docker create alpine:3.20)" | tar -C "${MNT}" -xf -
cat > "${MNT}/etc/resolv.conf" <<'EOF'
nameserver 1.1.1.1
EOF

# Install python and drop the guest agent in.
chroot "${MNT}" /bin/sh -c "apk add --no-cache python3" || true
mkdir -p "${MNT}/opt/euroclaw"
cp "$(dirname "$0")/../../euroclaw/sandbox/guest_agent.py" \
   "${MNT}/opt/euroclaw/guest_agent.py"

# Autostart the agent on boot via an init service.
cat > "${MNT}/etc/init.d/euroclaw-agent" <<EOF
#!/sbin/openrc-run
command="/usr/bin/python3"
command_args="/opt/euroclaw/guest_agent.py --port ${GUEST_PORT}"
command_background=true
pidfile="/run/euroclaw-agent.pid"
EOF
chmod +x "${MNT}/etc/init.d/euroclaw-agent"
chroot "${MNT}" /bin/sh -c "rc-update add euroclaw-agent default" || true

echo "Done. Set FC_KERNEL_PATH=${KERNEL} and FC_ROOTFS_PATH=${ROOTFS}."
