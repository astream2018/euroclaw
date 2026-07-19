"""Unit tests for the EuroClaw sandbox subsystem."""

from __future__ import annotations

import sys
from unittest import mock

import pytest

from euroclaw.sandbox import (
    Sandbox,
    SandboxResult,
    SandboxUnavailable,
    get_sandbox,
)
from euroclaw.sandbox.firecracker import FirecrackerMicroVM
from euroclaw.sandbox.subprocess_sandbox import SubprocessSandbox


# -- get_sandbox ----------------------------------------------------------


def test_get_sandbox_default_is_subprocess(monkeypatch):
    monkeypatch.delenv("SANDBOX_BACKEND", raising=False)
    sbx = get_sandbox()
    assert isinstance(sbx, SubprocessSandbox)
    assert isinstance(sbx, Sandbox)


def test_get_sandbox_unknown_backend_raises():
    with pytest.raises(ValueError):
        get_sandbox("does-not-exist")


# -- SubprocessSandbox execution ------------------------------------------


def test_subprocess_python_echo():
    sbx = SubprocessSandbox()
    result = sbx.execute("execute_python", "print('hi')")
    assert result.ok
    assert "hi" in result.stdout


def test_subprocess_respects_timeout():
    sbx = SubprocessSandbox()
    code = f"import time; time.sleep(5)"  # noqa: F541
    result = sbx.execute("execute_python", code, timeout=1)
    assert result.timed_out is True
    assert result.exit_code == 124


# -- SandboxResult --------------------------------------------------------


def test_sandbox_result_ok_and_as_text():
    ok = SandboxResult(stdout="hello", exit_code=0)
    assert ok.ok is True
    text = ok.as_text()
    assert "OK" in text
    assert "hello" in text

    failed = SandboxResult(stdout="", stderr="boom", exit_code=2)
    assert failed.ok is False
    ftext = failed.as_text()
    assert "FAILED" in ftext
    assert "boom" in ftext

    timed = SandboxResult(stdout="", exit_code=124, timed_out=True)
    assert timed.ok is False
    assert "TIMED OUT" in timed.as_text()


# -- FirecrackerMicroVM ---------------------------------------------------


def test_firecracker_check_kvm_raises_without_kvm():
    vm = FirecrackerMicroVM(task_id="test1234")
    with (
        mock.patch("os.path.exists", return_value=False),
        mock.patch.object(sys, "platform", "linux"),
    ):
        with pytest.raises(SandboxUnavailable):
            vm.boot()


def test_firecracker_boot_happy_path():
    vm = FirecrackerMicroVM(task_id="test1234")

    fake_resp = mock.Mock()
    fake_resp.status_code = 204

    with (
        mock.patch.object(vm, "_check_kvm", return_value=None),
        mock.patch("euroclaw.sandbox.firecracker.shutil.copyfile") as mock_copy,
        mock.patch("euroclaw.sandbox.firecracker.subprocess.Popen") as mock_popen,
        mock.patch("euroclaw.sandbox.firecracker.time.sleep"),
        mock.patch.object(vm.session, "put", return_value=fake_resp) as mock_put,
    ):
        vm.boot()

    assert mock_popen.call_count == 1
    mock_copy.assert_called_once()
    # boot-source, drive, machine-config, vsock, actions => 5 puts.
    assert mock_put.call_count == 5
