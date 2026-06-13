import pytest
from unittest.mock import patch
from plugins.local_files import LocalFileSystemPlugin

def test_local_file_plugin_blocks_path_traversal():
    """
    Test that the file system plugin strictly enforces zero-trust boundaries
    and rejects directory traversal attacks.
    """
    # Initialize plugin with a specific safe directory
    plugin = LocalFileSystemPlugin(allowed_directories_env="/app/safe_workspace")
    
    # Attempt a classic path traversal attack
    malicious_path = "../../../etc/passwd"
    result = plugin.read_file(malicious_path)
    
    # Assert the framework intercepted and blocked the attempt
    assert "ERROR: Access Denied" in result
    assert "restricted" in result

def test_local_file_plugin_allows_safe_files(tmp_path):
    """
    Test that the plugin successfully reads files within its allowed boundary.
    """
    # Create a temporary safe workspace and file for testing
    safe_workspace = tmp_path / "workspace"
    safe_workspace.mkdir()
    test_file = safe_workspace / "data.txt"
    test_file.write_text("secure data content")
    
    plugin = LocalFileSystemPlugin(allowed_directories_env=str(safe_workspace))
    
    # Attempt to read the valid file
    result = plugin.read_file(str(test_file))
    
    assert result == "secure data content"