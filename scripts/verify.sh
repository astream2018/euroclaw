#!/usr/bin/env bash
set -euo pipefail

export OTEL_SDK_DISABLED=true

python -m pytest -q tests/unit/test_app_health.py \
  tests/unit/test_core.py \
  tests/unit/test_plugins.py \
  tests/unit/test_logging.py \
  tests/unit/test_api_versioning.py \
  tests/unit/test_rate_limiting.py
