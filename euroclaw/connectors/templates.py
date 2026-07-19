"""String templates for generated connector artifacts.

Placeholders use simple ``{token}`` markers that are substituted with
``str.replace`` so that ordinary Python braces in the generated source do not
need escaping.

Recognized tokens:
    {BANNER}     - the untrusted-code banner comment block
    {class_name} - generated connector class name
    {name}       - connector manifest name (snake_case)
    {description}- connector description
    {methods}    - generated method definitions (connector.py)
    {test_body}  - generated test body (test_connector.py)
"""

from __future__ import annotations

BANNER = (
    "# ==== AI-GENERATED CONNECTOR — UNTRUSTED. "
    "REVIEW BEFORE ENABLING. ====\n"
    "# This file was produced by the EuroClaw connector generator.\n"
    "# It has NOT been reviewed and MUST NOT be auto-enabled. A\n"
    "# `.pending-review` marker is present until a human removes it.\n"
    "# ============================================================="
)

CONNECTOR_TEMPLATE = '''{BANNER}
"""Connector implementation for {name}.

{description}
"""

from __future__ import annotations

# The manifest is the trusted contract for this connector. It is loaded from
# the sibling manifest.yaml at import time for reference/introspection.
import os

try:
    from euroclaw.connectors.spec import ConnectorManifest

    _MANIFEST_PATH = os.path.join(os.path.dirname(__file__), "manifest.yaml")
    __euroclaw_manifest__ = ConnectorManifest.from_file(_MANIFEST_PATH)
except Exception:  # pragma: no cover - manifest optional at runtime
    __euroclaw_manifest__ = None


class {class_name}:
    """Auto-generated connector. Review every method before enabling."""

    manifest = __euroclaw_manifest__

{methods}
'''

METHOD_STUB_TEMPLATE = '''    def {method_name}(self, **kwargs):
        """{method_doc}"""
        raise NotImplementedError(
            "AI-generated connector method {method_name!r} is not implemented. "
            "Review and implement before enabling."
        )
'''

TEST_TEMPLATE = '''{BANNER}
"""Generated smoke tests for the {name} connector.

These tests only assert the connector module imports and exposes its tools.
They intentionally do NOT execute tool logic, which is untrusted.
"""

import importlib.util
import os


def _load_module():
    path = os.path.join(os.path.dirname(__file__), "connector.py")
    spec = importlib.util.spec_from_file_location("{name}_connector", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_connector_imports():
    module = _load_module()
    assert hasattr(module, "{class_name}")


def test_connector_exposes_tools():
    module = _load_module()
    connector_cls = getattr(module, "{class_name}")
{test_body}
'''

TEST_BODY_DEFAULT = "    assert connector_cls is not None"

README_TEMPLATE = """# {name}

> AI-GENERATED CONNECTOR — UNTRUSTED. REVIEW BEFORE ENABLING.

{description}

## Status

This connector is **pending review**. A `.pending-review` marker file is
present in this directory. Do not enable this connector until a human has
reviewed `connector.py` and removed the marker.

## Files

- `manifest.yaml` - the trusted, human-reviewable contract.
- `connector.py` - the UNTRUSTED generated implementation.
- `test_connector.py` - generated smoke tests (do not execute tool logic).

## Review checklist

1. Confirm the declared `egress_domains` match what the code actually calls.
2. Confirm `auth.secret_env_vars` are read from the environment, never hardcoded.
3. Confirm each tool method does only what its description claims.
4. Remove the `.pending-review` marker once satisfied.
"""
