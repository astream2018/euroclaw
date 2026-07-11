#!/usr/bin/env bash
set -euo pipefail

python -m pytest -q tests/unit/test_app_health.py tests/unit/test_api_versioning.py tests/unit/test_plugin_contracts.py tests/unit/test_rate_limiting.py tests/unit/test_security.py
