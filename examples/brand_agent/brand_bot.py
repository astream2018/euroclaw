"""Runnable example: a scheduled branding agent built on EuroClaw.

    pip install -e .
    python examples/brand_agent/brand_bot.py

Requires a local LLM (see the README Quickstart). The agent reasons via the
sovereign gateway and any tool it calls is routed through EuroClaw's RBAC +
HITL + sandbox path.
"""

import time

from dotenv import load_dotenv

from euroclaw import EuroclawOrchestrator
from euroclaw.agent_loader import get_profile, load_agents_from_yaml


def build_orchestrator() -> tuple[EuroclawOrchestrator, list[str]]:
    load_dotenv()
    loaded = load_agents_from_yaml("examples/brand_agent/agents.yaml")
    profile = get_profile(loaded, "BrandStrategist")

    orchestrator = EuroclawOrchestrator(name=profile.name)
    return orchestrator, profile.cron_schedule


def run_campaign(orchestrator: EuroclawOrchestrator) -> None:
    prompt = (
        "Create an image concept for Open Source Security and request "
        "Telegram approval before publishing."
    )
    print("\n--- CAMPAIGN RESULT ---")
    print(orchestrator.handle_request(prompt, roles=["operator"]))


def main() -> None:
    orchestrator, schedule = build_orchestrator()
    try:
        import schedule as scheduler
    except ImportError:
        print("Install the 'schedule' package to enable timed runs. Running once now.")
        run_campaign(orchestrator)
        return

    for target_time in schedule:
        scheduler.every().day.at(target_time).do(run_campaign, orchestrator)
        print(f" - Scheduled daily run at {target_time}")

    while True:
        scheduler.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
