"""坐席分配测试：多坐席账号、CAS 抢单、assignee 校验、列表过滤、自动指派。"""
from __future__ import annotations

import pytest

from server.auth import accounts as accounts_module
from server.auth.accounts import AuthUser, _load_extra_operators
from server.services.chat_store import MemoryChatStore
from server.services.customer_service import customer_service


def _op(user_id: str, display_name: str) -> AuthUser:
    return AuthUser(id=user_id, username=user_id, role="operator", display_name=display_name)


def _seed_agents(monkeypatch, agents: list[dict]) -> None:
    """把 accounts 的 operator 列表替换为指定坐席（list_users 内部读模块级 _USERS）。"""
    users = {
        agent["id"]: {
            "id": agent["id"],
            "username": agent["id"],
            "password_hash": "",
            "password_salt": "",
            "role": "operator",
            "display_name": agent["name"],
        }
        for agent in agents
    }
    monkeypatch.setattr(accounts_module, "_USERS", users)


def _make_handoff(conversation_id: str) -> None:
    """直接构造一个已转人工（待认领）的会话，绕过图链路。"""
    store = customer_service._active_store
    store.get_or_create_conversation(conversation_id, user_id="u-1")
    store.update_conversation(conversation_id, status="handoff", handoff_reason="测试转人工")


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    for store in (customer_service._store, customer_service._fallback_store):
        store.clear()
    customer_service._graph_checked = True
    customer_service._graph_agent = None
    yield


# ── 账号层 ──────────────────────────────────────────────


def test_load_extra_operators_parses_json(monkeypatch):
    monkeypatch.setenv(
        "AUTH_OPERATORS",
        '[{"id":"op2","username":"bob","password":"bob123","display_name":"Bob"}]',
    )
    assert _load_extra_operators() == [
        {"id": "op2", "username": "bob", "password": "bob123", "display_name": "Bob"}
    ]


def test_load_extra_operators_empty_or_invalid(monkeypatch):
    monkeypatch.delenv("AUTH_OPERATORS", raising=False)
    assert _load_extra_operators() == []
    monkeypatch.setenv("AUTH_OPERATORS", "not-json")
    assert _load_extra_operators() == []


# ── 存储层 CAS ─────────────────────────────────────────


def test_store_assign_release_cas():
    store = MemoryChatStore()
    store.get_or_create_conversation("c-1")
    assert store.assign_conversation("c-1", "op1", "A", "2026-01-01T00:00:00+00:00") is True
    # 已被认领，再次抢占失败
    assert store.assign_conversation("c-1", "op2", "B", "2026-01-01T00:00:00+00:00") is False
    # 非本人释放失败
    assert store.release_conversation("c-1", "op2") is False
    assert store.release_conversation("c-1", "op1") is True
    assert store.get_conversation("c-1")["assignee_id"] is None


# ── 服务层：领取 / 释放 / 回复校验 ──────────────────────


def test_claim_cas_prevents_double_claim(monkeypatch):
    _seed_agents(monkeypatch, [{"id": "op1", "name": "坐席一"}, {"id": "op2", "name": "坐席二"}])
    _make_handoff("c-1")
    result = customer_service.claim_conversation("c-1", _op("op1", "坐席一"))
    assert result["claimed"] is True
    assert result["assignee_id"] == "op1"
    with pytest.raises(ValueError):
        customer_service.claim_conversation("c-1", _op("op2", "坐席二"))
    assert customer_service.get_conversation("c-1")["assignee_id"] == "op1"


def test_claim_rejects_non_handoff(monkeypatch):
    _seed_agents(monkeypatch, [{"id": "op1", "name": "坐席一"}])
    customer_service._active_store.get_or_create_conversation("c-open", user_id="u-1")
    with pytest.raises(ValueError):
        customer_service.claim_conversation("c-open", _op("op1", "坐席一"))


def test_release_only_owner(monkeypatch):
    _seed_agents(monkeypatch, [{"id": "op1", "name": "坐席一"}, {"id": "op2", "name": "坐席二"}])
    _make_handoff("c-1")
    customer_service.claim_conversation("c-1", _op("op1", "坐席一"))
    with pytest.raises(ValueError):
        customer_service.release_conversation("c-1", _op("op2", "坐席二"))
    assert customer_service.release_conversation("c-1", _op("op1", "坐席一"))["released"] is True
    assert customer_service.get_conversation("c-1")["assignee_id"] is None


def test_manual_reply_rejects_other_assignee(monkeypatch):
    _seed_agents(monkeypatch, [{"id": "op1", "name": "坐席一"}, {"id": "op2", "name": "坐席二"}])
    _make_handoff("c-1")
    customer_service.claim_conversation("c-1", _op("op1", "坐席一"))
    with pytest.raises(ValueError):
        customer_service.send_manual_reply("c-1", "你好", _op("op2", "坐席二"))


def test_manual_reply_auto_claims(monkeypatch):
    _seed_agents(monkeypatch, [{"id": "op1", "name": "坐席一"}])
    _make_handoff("c-1")
    result = customer_service.send_manual_reply("c-1", "您好，有什么可以帮您", _op("op1", "坐席一"))
    assert result["agent_name"] == "坐席一"
    assert result["assignee_id"] == "op1"
    conv = customer_service.get_conversation("c-1")
    assert conv["assignee_id"] == "op1"
    assert conv["status"] == "manual"


# ── 服务层：列表过滤 / 坐席列表 / 自动指派 ───────────────


def test_list_conversations_filter(monkeypatch):
    _seed_agents(monkeypatch, [{"id": "op1", "name": "坐席一"}, {"id": "op2", "name": "坐席二"}])
    _make_handoff("c-1")
    _make_handoff("c-2")
    _make_handoff("c-3")
    customer_service.claim_conversation("c-1", _op("op1", "坐席一"))
    customer_service.claim_conversation("c-2", _op("op2", "坐席二"))

    mine = customer_service.list_conversations(filter="mine", agent_id="op1")
    assert {c["id"] for c in mine} == {"c-1"}

    unassigned = customer_service.list_conversations(filter="unassigned")
    assert {c["id"] for c in unassigned} == {"c-3"}

    all_c = customer_service.list_conversations(filter="all")
    assert {c["id"] for c in all_c} == {"c-1", "c-2", "c-3"}


def test_list_agents_with_load(monkeypatch):
    _seed_agents(monkeypatch, [{"id": "op1", "name": "坐席一"}, {"id": "op2", "name": "坐席二"}])
    _make_handoff("c-1")
    customer_service.claim_conversation("c-1", _op("op1", "坐席一"))

    agents = customer_service.list_agents()
    by_id = {a["id"]: a for a in agents}
    assert by_id["op1"]["active_count"] == 1
    assert by_id["op2"]["active_count"] == 0
    assert by_id["op1"]["display_name"] == "坐席一"


def test_auto_assign_least_loaded(monkeypatch):
    _seed_agents(monkeypatch, [{"id": "op1", "name": "坐席一"}, {"id": "op2", "name": "坐席二"}])
    _make_handoff("c-1")
    customer_service.claim_conversation("c-1", _op("op1", "坐席一"))  # op1 在办 1
    _make_handoff("c-2")
    customer_service._auto_assign("c-2")  # 应分给负载更小的 op2
    assert customer_service.get_conversation("c-2")["assignee_id"] == "op2"


def test_auto_assign_no_agents_leaves_unassigned(monkeypatch):
    _seed_agents(monkeypatch, [])
    _make_handoff("c-1")
    customer_service._auto_assign("c-1")
    assert customer_service.get_conversation("c-1")["assignee_id"] is None
