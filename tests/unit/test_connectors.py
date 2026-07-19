"""Unit tests for the connector-generator subsystem."""

import pytest

from euroclaw.connectors import (
    ConnectorGenerator,
    ConnectorManifest,
    validate_connector_dir,
)


def test_manifest_name_validation():
    ok = ConnectorManifest(name="weather_fetcher", description="Fetch weather")
    assert ok.name == "weather_fetcher"

    with pytest.raises(ValueError):
        ConnectorManifest(name="Bad-Name", description="nope")


def test_content_hash_deterministic_and_sensitive():
    m1 = ConnectorManifest(name="a_conn", description="desc")
    m2 = ConnectorManifest(name="a_conn", description="desc")
    assert m1.content_hash() == m2.content_hash()

    m3 = ConnectorManifest(name="a_conn", description="different")
    assert m1.content_hash() != m3.content_hash()


def test_yaml_round_trip():
    manifest = ConnectorManifest(
        name="round_trip",
        description="desc",
        risk_class="low",
        egress_domains=["api.example.com"],
    )
    restored = ConnectorManifest.from_yaml(manifest.to_yaml())
    assert restored == manifest
    assert restored.content_hash() == manifest.content_hash()


def test_generate_without_llm_creates_files(tmp_path):
    target = str(tmp_path)
    explicit = ConnectorManifest(
        name="weather_conn",
        description="Fetch weather from api.example.com",
        risk_class="low",
    )
    generator = ConnectorGenerator(llm=None)
    manifest = generator.generate(
        "Fetch weather from api.example.com",
        target,
        manifest=explicit,
    )
    assert manifest.name == "weather_conn"

    for filename in (
        "manifest.yaml",
        "connector.py",
        "test_connector.py",
        "README.md",
        ".pending-review",
    ):
        assert (tmp_path / filename).exists(), filename

    connector_src = (tmp_path / "connector.py").read_text(encoding="utf-8")
    assert "AI-GENERATED CONNECTOR" in connector_src

    problems = validate_connector_dir(target)
    assert isinstance(problems, list)
    assert problems == []


def test_propose_manifest_with_fake_llm():
    class FakeLLM:
        def query_model(self, prompt, system_instruction=None):
            return (
                '{"name": "fake_conn", "description": "A fake connector", '
                '"risk_class": "low", "tools": []}'
            )

    generator = ConnectorGenerator(llm=FakeLLM())
    manifest = generator.propose_manifest("anything")
    assert isinstance(manifest, ConnectorManifest)
    assert manifest.name == "fake_conn"


def test_validate_dir_missing_connector(tmp_path):
    manifest = ConnectorManifest(
        name="incomplete",
        description="desc",
        risk_class="low",
    )
    (tmp_path / "manifest.yaml").write_text(manifest.to_yaml(), encoding="utf-8")
    problems = validate_connector_dir(str(tmp_path))
    assert any("connector.py" in p for p in problems)
