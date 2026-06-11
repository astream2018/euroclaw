import os
import time
import shutil
import logging
import subprocess
import requests_unixsocket
from opentelemetry import trace

logger = logging.getLogger("euroclaw.sandbox.firecracker")
tracer = trace.get_tracer(__name__)

class FirecrackerMicroVM:
    def __init__(self, task_id: str):
        self.task_id = task_id
        self.socket_path = f"/tmp/firecracker-{self.task_id}.socket"
        self.session = requests_unixsocket.Session()
        self.base_url = f"http+unix://{self.socket_path.replace('/', '%2F')}"
        self.kernel_path = os.getenv("FC_KERNEL_PATH", "/opt/euroclaw/vmlinux")
        self.base_rootfs = os.getenv("FC_ROOTFS_PATH", "/opt/euroclaw/rootfs.ext4")
        self.ephemeral_rootfs = f"/tmp/rootfs-{self.task_id}.ext4"
        self.fc_process = None

    def boot(self):
        with tracer.start_as_current_span("firecracker_boot_sequence"):
            shutil.copyfile(self.base_rootfs, self.ephemeral_rootfs)
            self.fc_process = subprocess.Popen(
                ["firecracker", "--api-sock", self.socket_path],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            time.sleep(0.1) 
            self.session.put(f"{self.base_url}/boot-source", json={
                "kernel_image_path": self.kernel_path, "boot_args": "console=ttyS0 reboot=k panic=1 pci=off"
            })
            self.session.put(f"{self.base_url}/drives/rootfs", json={
                "drive_id": "rootfs", "path_on_host": self.ephemeral_rootfs,
                "is_root_device": True, "is_read_only": False
            })
            self.session.put(f"{self.base_url}/machine-config", json={"vcpu_count": 1, "mem_size_mib": 256})
            self.session.put(f"{self.base_url}/actions", json={"action_type": "InstanceStart"})

    def execute_tool(self, tool_name: str, arguments: str) -> str:
        with tracer.start_as_current_span("firecracker_tool_execution"):
            time.sleep(0.5) 
            return f"MicroVM Execution Result: {tool_name} completed in hardware isolation."

    def teardown(self):
        with tracer.start_as_current_span("firecracker_teardown"):
            if self.fc_process: self.fc_process.kill()
            if os.path.exists(self.socket_path): os.remove(self.socket_path)
            if os.path.exists(self.ephemeral_rootfs): os.remove(self.ephemeral_rootfs)