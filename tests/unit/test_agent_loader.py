import pytest

from euroclaw.agent_loader import get_profile, load_agents_from_yaml

SAMPLE = """
agents:
  - name: BrandStrategist
    role: Marketing Director
    goal: Generate posts
    allowed_tools:
      - search_internet
    cron_schedule:
      - "06:00"
"""


def _write(tmp_path, text):
    path = tmp_path / "agents.yaml"
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_loads_profiles(tmp_path):
    loaded = load_agents_from_yaml(_write(tmp_path, SAMPLE))
    profile = get_profile(loaded, "BrandStrategist")
    assert profile.role == "Marketing Director"
    assert profile.allowed_tools == ["search_internet"]
    assert profile.cron_schedule == ["06:00"]


def test_missing_name_raises(tmp_path):
    bad = "agents:\n  - role: no name here\n"
    with pytest.raises(ValueError):
        load_agents_from_yaml(_write(tmp_path, bad))


def test_duplicate_names_raise(tmp_path):
    dup = "agents:\n  - name: A\n  - name: A\n"
    with pytest.raises(ValueError, match="duplicate"):
        load_agents_from_yaml(_write(tmp_path, dup))


def test_unknown_profile_raises(tmp_path):
    loaded = load_agents_from_yaml(_write(tmp_path, SAMPLE))
    with pytest.raises(KeyError):
        get_profile(loaded, "Nope")
