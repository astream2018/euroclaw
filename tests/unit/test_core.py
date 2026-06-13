import os
import pytest
import subprocess
from unittest.mock import patch, MagicMock
from src.sandbox_firecracker import FirecrackerMicroVM
import requests.exceptions


# ==========================================
# TEST CASES FOR FIRECRACKER MICROVM ERROR FLOW
# ==========================================

@patch('src.sandbox_firecracker.requests_unixsocket.Session')
@patch('src.sandbox_firecracker.subprocess.Popen')
@patch('src.sandbox_firecracker.shutil.copyfile')
def test_firecracker_boot_socket_failure(mock_copyfile, mock_popen, mock_session_class):
    """
    Test that a failure to communicate with the Firecracker API socket
    is handled or raised predictably.
    """
    mock_session_instance = MagicMock()
    # Simulate a ConnectionError when trying to configure the boot-source
    mock_session_instance.put.side_effect = requests.exceptions.ConnectionError("Socket refused")
    mock_session_class.return_value = mock_session_instance
    
    vm = FirecrackerMicroVM(task_id="test-crash-123")
    
    # We expect the boot process to fail and raise the ConnectionError
    with pytest.raises(requests.exceptions.ConnectionError, match="Socket refused"):
        vm.boot()
    
    # Verify that it actually attempted to launch the process before failing
    mock_popen.assert_called_once()


# ==========================================
# TEST CASES FOR FIRECRACKER MICROVM HAPPY FLOW
# ==========================================

@patch('src.sandbox_firecracker.requests_unixsocket.Session')
@patch('src.sandbox_firecracker.subprocess.Popen')
@patch('src.sandbox_firecracker.shutil.copyfile')
def test_firecracker_boot(mock_copyfile, mock_popen, mock_session_class):
    mock_session_instance = MagicMock()
    mock_session_class.return_value = mock_session_instance
    
    vm = FirecrackerMicroVM(task_id="test-task-123")
    vm.boot()
    
    mock_copyfile.assert_called_once_with(vm.base_rootfs, vm.ephemeral_rootfs)
    
    mock_popen.assert_called_once_with(
        ["firecracker", "--api-sock", vm.socket_path],
        stdout=subprocess.DEVNULL, 
        stderr=subprocess.DEVNULL
    )
    
    assert mock_session_instance.put.call_count == 4


def test_firecracker_execute_tool():
    vm = FirecrackerMicroVM(task_id="test-task-123")
    result = vm.execute_tool(tool_name="python_compiler", arguments="print('hello world')")
    
    assert "MicroVM Execution Result:" in result
    assert "python_compiler" in result
    assert "completed in hardware isolation" in result


real_exists = os.path.exists

@patch('src.sandbox_firecracker.os.remove')
@patch('src.sandbox_firecracker.os.path.exists')
def test_firecracker_teardown(mock_exists, mock_remove):
    # Safely mock exists only for the files we want to trigger cleanup for, 
    # letting normal system background checks pass to prevent crashes.
    mock_exists.side_effect = lambda p: True if "test-task-123" in str(p) else real_exists(p)
    
    vm = FirecrackerMicroVM(task_id="test-task-123")
    vm.fc_process = MagicMock() 
    
    vm.teardown()
    
    vm.fc_process.kill.assert_called_once()
    assert mock_remove.call_count == 2