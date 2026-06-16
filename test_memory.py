import os

os.environ.setdefault("AGENT_MODE", "rules")

from src.storage.db import (
    get_user_profile,
    init_db,
    save_message,
    upsert_user_profile,
)
from src.storage.connection import database_label
from src.storage.memory import build_long_term_context, sync_slots_to_profile
from src.models.schemas import SessionSlots

init_db()
print("database:", database_label())

upsert_user_profile(
    "test_user",
    taste_tags=["偏甜", "气味适中"],
    budget_min=200,
    budget_max=350,
    favorite_variety="金枕",
)
sync_slots_to_profile("test_user", SessionSlots(variety="金枕", budget=[250, 300], taste_tags=["偏甜"]))

profile = get_user_profile("test_user")
assert profile is not None
assert profile["favorite_variety"] == "金枕"
print("OK profile")

ltm = build_long_term_context("test_user")
assert "金枕" in ltm
assert "偏甜" in ltm
print("OK long_term_context:", ltm[:60], "...")

print("ALL MEMORY TESTS PASSED")
