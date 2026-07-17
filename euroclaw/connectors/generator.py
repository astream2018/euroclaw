"""Out-of-process connector generator.

This is a developer tool, NOT part of the runtime core. Generated connector
code is UNTRUSTED: the generator always writes a ``.pending-review`` marker and
prominent banners, and never auto-enables anything.

The LLM client is injected (a duck-typed object exposing
``query_model(prompt, system_instruction=None) -> str``). If no client is
provided, a :class:`SovereignLLMGateway` is lazily imported when available;
otherwise the generator falls back to fully deterministic behavior.
"""

from __future__ import annotations

import json
import logging
import os
import re

from euroclaw.connectors.spec import (
    ConnectorManifest,
    ConnectorTool,
)
from euroclaw.connectors.templates import (
    BANNER,
    CONNECTOR_TEMPLATE,
    METHOD_STUB_TEMPLATE,
    README_TEMPLATE,
    TEST_BODY_DEFAULT,
    TEST_TEMPLATE,
)

logger = logging.getLogger(__name__)

_MANIFEST_SCHEMA_HINT = (
    '{"name": "<snake_case>", "version": "0.1.0", '
    '"description": "<text>", "risk_class": "low|medium|high", '
    '"egress_domains": ["<host>"], '
    '"auth": {"type": "none|api_key|oauth2|basic", '
    '"scopes": [], "secret_env_vars": []}, '
    '"tools": [{"name": "<snake_case>", "description": "<text>", '
    '"parameters": {}}]}'
)


def slugify(text: str) -> str:
    """Return a snake_case slug that always starts with a letter."""
    lowered = (text or "").strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "_", lowered).strip("_")
    if not slug:
        slug = "connector"
    if not slug[0].isalpha():
        slug = "c_" + slug
    return slug


def _class_name(name: str) -> str:
    parts = [p for p in name.split("_") if p]
    return "".join(p.capitalize() for p in parts) + "Connector"


class ConnectorGenerator:
    """Generate connector scaffolding from a natural-language description."""

    def __init__(self, llm=None):
        self._injected_llm = llm

    def _llm(self):
        """Return the injected client, or lazily build a gateway if possible."""
        if self._injected_llm is not None:
            return self._injected_llm
        try:
            from euroclaw.llm_gateway import SovereignLLMGateway

            return SovereignLLMGateway()
        except Exception as exc:  # noqa: BLE001 - gateway is optional
            logger.debug("No LLM gateway available: %s", exc)
            return None

    def _fallback_manifest(self, description: str) -> ConnectorManifest:
        """Deterministic minimal manifest derived only from the description."""
        words = re.findall(r"[a-zA-Z0-9]+", description or "")
        base = "_".join(words[:3]) if words else "connector"
        name = slugify(base)
        logger.info("propose_manifest: using deterministic fallback manifest")
        return ConnectorManifest(
            name=name,
            description=(description or "").strip() or "Generated connector.",
            risk_class="medium",
            tools=[
                ConnectorTool(
                    name="run",
                    description=("Placeholder tool. Define real tools during review."),
                    parameters={},
                )
            ],
        )

    def propose_manifest(self, description: str) -> ConnectorManifest:
        """Propose a manifest for ``description``.

        Uses the LLM if available, otherwise falls back to a deterministic
        minimal manifest. Never fabricates tool logic.
        """
        llm = self._llm()
        if llm is None:
            return self._fallback_manifest(description)

        system = (
            "You design connector manifests. Return ONLY JSON (no prose, no "
            "markdown fences) matching this schema: " + _MANIFEST_SCHEMA_HINT
        )
        prompt = (
            "Produce a connector manifest for the following description. "
            "The 'name' and each tool 'name' must be snake_case. Do not invent "
            "credentials. Description:\n" + (description or "")
        )
        try:
            raw = llm.query_model(prompt, system_instruction=system)
            data = json.loads(_extract_json(raw))
            manifest = ConnectorManifest.model_validate(data)
            logger.info("propose_manifest: used LLM-proposed manifest")
            return manifest
        except Exception as exc:  # noqa: BLE001 - defensive: any failure -> fallback
            logger.warning(
                "propose_manifest: LLM path failed (%s); using fallback", exc
            )
            return self._fallback_manifest(description)

    def _render_methods(self, manifest: ConnectorManifest, llm) -> str:
        """Render method definitions, optionally filled by the LLM."""
        tools = manifest.tools or [
            ConnectorTool(name="run", description="Placeholder tool.")
        ]
        blocks: list[str] = []
        for tool in tools:
            method_name = slugify(tool.name)
            doc = (tool.description or "").replace('"""', "'''")
            block = None
            if llm is not None:
                block = self._llm_method_body(manifest, tool, method_name, llm)
            if not block:
                block = METHOD_STUB_TEMPLATE.replace(
                    "{method_name}", method_name
                ).replace("{method_doc}", doc)
            blocks.append(block)
        return "\n".join(blocks)

    def _llm_method_body(self, manifest, tool, method_name, llm):
        """Best-effort LLM fill of a single method. Returns None on failure."""
        system = (
            "You implement one Python method body for an UNTRUSTED connector. "
            "Return ONLY the full method definition (def ...:) indented 4 "
            "spaces, valid Python, no markdown fences, no class wrapper."
        )
        prompt = (
            f"Connector: {manifest.name}\n"
            f"Allowed egress domains: {manifest.egress_domains}\n"
            f"Auth env vars: {manifest.auth.secret_env_vars}\n"
            f"Implement method '{method_name}' for tool described as: "
            f"{tool.description}\nParameters schema: {tool.parameters}"
        )
        try:
            raw = llm.query_model(prompt, system_instruction=system)
        except Exception as exc:  # noqa: BLE001
            logger.warning("method fill failed for %s: %s", method_name, exc)
            return None
        body = _strip_fences(raw).strip("\n")
        if not body.lstrip().startswith("def "):
            logger.warning("method fill for %s not a def; using stub", method_name)
            return None
        # Ensure 4-space indentation of the def line.
        lines = body.splitlines()
        if not lines[0].startswith("    "):
            lines = ["    " + line if line.strip() else line for line in lines]
        return "\n".join(lines) + "\n"

    def generate(
        self,
        description: str,
        target_dir: str,
        *,
        manifest: ConnectorManifest | None = None,
    ) -> ConnectorManifest:
        """Generate connector scaffolding into ``target_dir``.

        Fully functional with ``llm=None`` (writes NotImplementedError stubs).
        Always writes a ``.pending-review`` marker.
        """
        if manifest is None:
            manifest = self.propose_manifest(description)

        os.makedirs(target_dir, exist_ok=True)
        llm = self._llm()

        class_name = _class_name(manifest.name)
        methods = self._render_methods(manifest, llm)

        connector_src = (
            CONNECTOR_TEMPLATE.replace("{BANNER}", BANNER)
            .replace("{class_name}", class_name)
            .replace("{name}", manifest.name)
            .replace("{description}", manifest.description)
            .replace("{methods}", methods)
        )

        test_src = (
            TEST_TEMPLATE.replace("{BANNER}", BANNER)
            .replace("{class_name}", class_name)
            .replace("{name}", manifest.name)
            .replace("{test_body}", TEST_BODY_DEFAULT)
        )

        readme_src = README_TEMPLATE.replace("{name}", manifest.name).replace(
            "{description}", manifest.description
        )

        _write(os.path.join(target_dir, "manifest.yaml"), manifest.to_yaml())
        _write(os.path.join(target_dir, "connector.py"), connector_src)
        _write(os.path.join(target_dir, "test_connector.py"), test_src)
        _write(os.path.join(target_dir, "README.md"), readme_src)
        _write(os.path.join(target_dir, ".pending-review"), "")

        logger.info(
            "Generated connector %r into %s (PENDING REVIEW)",
            manifest.name,
            target_dir,
        )
        return manifest


def _write(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


def _strip_fences(text: str) -> str:
    text = (text or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # drop opening fence (possibly ```python) and trailing fence
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines)
    return text


def _extract_json(text: str) -> str:
    """Extract the first JSON object from possibly fenced LLM output."""
    cleaned = _strip_fences(text)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        return cleaned[start : end + 1]
    return cleaned
