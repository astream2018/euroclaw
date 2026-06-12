from unittest.mock import patch, MagicMock
import subprocess

# Import your actual class from the src module
from src.sandbox_firecracker import FirecrackerMicroVM

# ==========================================
# TEST CASES FOR FIRECRACKER MICROVM
# ==========================================

@patch('src.sandbox_firecracker.requests_unixsocket.Session')
@patch('src.sandbox_firecracker.subprocess.Popen')
@patch('src.sandbox_firecracker.shutil.copyfile')
def test_firecracker_boot(mock_copyfile, mock_popen, mock_session_class):
    """
    Test the boot sequence without actually spinning up a VM.
    We mock file copying, subprocess creation, and socket requests.
    """
    # Setup the mocked requests session
    mock_session_instance = MagicMock()
    mock_session_class.return_value = mock_session_instance
    
    # Initialize the VM
    vm = FirecrackerMicroVM(task_id="test-task-123")
    
    # Run the boot method
    vm.boot()
    
    # 1. Assert the root filesystem was copied
    mock_copyfile.assert_called_once_with(vm.base_rootfs, vm.ephemeral_rootfs)
    
    # 2. Assert the firecracker subprocess was launched correctly
    mock_popen.assert_called_once_with(
        ["firecracker", "--api-sock", vm.socket_path],
        stdout=subprocess.DEVNULL, 
        stderr=subprocess.DEVNULL
    )
    
    # 3. Assert the setup API calls were made to the socket (boot-source, drives, machine-config, actions)
    assert mock_session_instance.put.call_count == 4


def test_firecracker_execute_tool():
    """
    Test the tool execution logic. 
    Since this method currently just sleeps and returns a formatted string, 
    we can run it directly without heavy mocking.
    """
    vm = FirecrackerMicroVM(task_id="test-task-123")
    
    # Run the tool
    result = vm.execute_tool(tool_name="python_compiler", arguments="print('hello world')")
    
    # Assert the output matches the expected format
    assert "MicroVM Execution Result:" in result
    assert "python_compiler" in result
    assert "completed in hardware isolation" in result


@patch('src.sandbox_firecracker.os.remove')
@patch('src.sandbox_firecracker.os.path.exists')
def test_firecracker_teardown(mock_exists, mock_remove):
    """
    Test that the VM process is killed and temporary files are cleaned up.
    """
    # Force os.path.exists to return True so the cleanup block triggers
    mock_exists.return_value = True 
    
    vm = FirecrackerMicroVM(task_id="test-task-123")
    
    # Mock a running process so we can test the .kill() method
    vm.fc_process = MagicMock() 
    
    # Run the teardown
    vm.teardown()
    
    # 1. Assert the process kill signal was sent
    vm.fc_process.kill.assert_called_once()
    
    # 2. Assert both the socket and ephemeral rootfs files were deleted
    assert mock_remove.call_count == 2