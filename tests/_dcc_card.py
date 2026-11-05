"""Live kanban card id for DCC batch locks in tests."""
import os


def card_id() -> str:
    return os.environ.get("HERMES_KANBAN_TASK", "pytest")
