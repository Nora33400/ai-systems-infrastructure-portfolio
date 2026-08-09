from __future__ import annotations


def slugify(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in value)
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-") or "intent"


def planner_output(title: str, intent: str) -> str:
    return (
        f"# PLAN - {title}\n\n"
        "## Objective\n"
        f"{intent}\n\n"
        "## Phases\n"
        "1. Frame intent and boundaries.\n"
        "2. Define runtime and control surfaces.\n"
        "3. Build storage and planning substrate.\n"
        "4. Connect observability and automation.\n"
        "5. Harden and package the node.\n"
    )


def architect_output(title: str, intent: str) -> str:
    return (
        f"# ARCHITECTURE - {title}\n\n"
        "## System planes\n"
        "- core runtime\n"
        "- TileMindFS substrate\n"
        "- resource planner\n"
        "- daemon API\n"
        "- dashboard shell\n\n"
        "## Flow\n"
        "intent -> queue -> plan -> architecture -> tasks -> archive -> report\n\n"
        f"## Intent anchor\n{intent}\n"
    )


def builder_output(title: str, intent: str) -> str:
    return (
        f"# TASKS - {title}\n\n"
        "- Define commands.\n"
        "- Generate state transitions.\n"
        "- Produce TileMindFS manifests.\n"
        "- Track events and artifacts.\n"
        "- Expose dashboard and daemon.\n\n"
        f"Intent reference: {intent}\n"
    )
