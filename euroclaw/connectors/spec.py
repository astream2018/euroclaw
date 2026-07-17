"""Pydantic models describing connector manifests and directory validation.

This module is part of the out-of-process connector-generator developer tool.
It intentionally avoids importing any EuroClaw runtime core modules so that it
can be used standalone.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Literal

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator

_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")


class ConnectorAuth(BaseModel):
    """Authentication requirements for a connector."""

    type: Literal["none", "api_key", "oauth2", "basic"] = "none"
    scopes: list[str] = Field(default_factory=list)
    secret_env_vars: list[str] = Field(default_factory=list)


class ConnectorTool(BaseModel):
    """A single callable tool exposed by a connector."""

    name: str
    description: str
    parameters: dict = Field(default_factory=dict)


class ConnectorManifest(BaseModel):
    """Declarative description of a connector.

    A manifest is the trusted, human-reviewable contract for a connector. The
    generated ``connector.py`` implementation is UNTRUSTED until reviewed.
    """

    name: str
    version: str = "0.1.0"
    description: str
    risk_class: Literal["low", "medium", "high"] = "medium"
    egress_domains: list[str] = Field(default_factory=list)
    auth: ConnectorAuth = Field(default_factory=ConnectorAuth)
    tools: list[ConnectorTool] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        if not _NAME_RE.match(value):
            raise ValueError(
                f"connector name {value!r} must be snake_case "
                "matching ^[a-z][a-z0-9_]*$"
            )
        return value

    def to_yaml(self) -> str:
        """Serialize the manifest to a YAML document."""
        return yaml.safe_dump(self.model_dump(), sort_keys=False)

    @classmethod
    def from_yaml(cls, text: str) -> "ConnectorManifest":
        """Parse a manifest from a YAML document."""
        data = yaml.safe_load(text) or {}
        return cls.model_validate(data)

    @classmethod
    def from_file(cls, path: str) -> "ConnectorManifest":
        """Parse a manifest from a YAML file on disk."""
        with open(path, "r", encoding="utf-8") as handle:
            return cls.from_yaml(handle.read())

    def content_hash(self) -> str:
        """Return a stable sha256 hex digest of the canonical manifest."""
        canonical = json.dumps(
            self.model_dump(),
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_connector_dir(path: str) -> list[str]:
    """Validate a connector directory.

    Returns a list of human-readable problems. An empty list means the
    directory is valid.
    """
    problems: list[str] = []

    manifest_path = os.path.join(path, "manifest.yaml")
    connector_path = os.path.join(path, "connector.py")

    manifest: ConnectorManifest | None = None

    if not os.path.isfile(manifest_path):
        problems.append("manifest.yaml is missing")
    else:
        try:
            manifest = ConnectorManifest.from_file(manifest_path)
        except ValidationError as exc:
            for err in exc.errors():
                loc = ".".join(str(part) for part in err.get("loc", ()))
                problems.append(
                    f"manifest.yaml invalid at {loc or '<root>'}: "
                    f"{err.get('msg', 'validation error')}"
                )
        except Exception as exc:  # noqa: BLE001 - surface any parse failure
            problems.append(f"manifest.yaml could not be parsed: {exc}")

    if not os.path.isfile(connector_path):
        problems.append("connector.py is missing")

    if manifest is not None:
        if manifest.risk_class != "low" and not manifest.egress_domains:
            problems.append(
                f"egress_domains must be non-empty when risk_class is "
                f"{manifest.risk_class!r}"
            )
        if manifest.auth.type != "none" and not manifest.auth.secret_env_vars:
            problems.append(
                f"auth.secret_env_vars must be non-empty when auth.type is "
                f"{manifest.auth.type!r}"
            )

    return problems
