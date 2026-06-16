from __future__ import annotations

from src.models.schemas import SessionContext
from src.storage.db import (
    add_user_memory,
    clear_user_long_term_memory,
    delete_all_user_sessions,
    delete_session,
    get_messages,
    init_db,
    list_user_sessions,
    save_message,
    save_session,
    upsert_user_profile,
)

init_db()

uid = "hist_test_user"
delete_all_user_sessions(uid)
clear_user_long_term_memory(uid)

ctx1 = SessionContext(session_id="sess_hist_1", user_id=uid)
ctx2 = SessionContext(session_id="sess_hist_2", user_id=uid)
save_session(ctx1)
save_session(ctx2)
save_message("sess_hist_1", "user", "第一条测试推荐")
save_message("sess_hist_1", "assistant", "好的，推荐金枕")
save_message("sess_hist_2", "user", "验真 TR20260609002")
save_message("sess_hist_2", "assistant", "可以买")

items = list_user_sessions(uid)
assert len(items) == 2
assert items[0]["preview"].startswith("验真") or items[0]["preview"].startswith("第一条")
print("OK list sessions:", len(items))

assert delete_session("sess_hist_1", uid)
assert delete_session("sess_hist_1", uid) is False
assert len(get_messages("sess_hist_1")) == 0
remaining = list_user_sessions(uid)
assert len(remaining) == 1
print("OK delete one")

upsert_user_profile(uid, taste_tags=["偏甜"], budget_min=200, budget_max=300)
add_user_memory(uid, "记住我不吃太浓气味", "preference")
cleared = clear_user_long_term_memory(uid)
assert cleared["profiles"] >= 1
assert cleared["memories"] >= 1
print("OK clear memory:", cleared)

count = delete_all_user_sessions(uid)
assert count == 1
assert len(list_user_sessions(uid)) == 0
print("OK clear all sessions:", count)

wrong = delete_session("sess_hist_2", "other_user")
assert wrong is False
print("OK access denied")

print("ALL HISTORY TESTS PASSED")
