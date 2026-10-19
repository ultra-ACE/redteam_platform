import os

from app.adapters.factory import resolve_secret_ref


def test_resolve_secret_ref_variants() -> None:
    assert resolve_secret_ref(None) is None
    assert resolve_secret_ref("") is None
    assert resolve_secret_ref("literal:sk-abc") == "sk-abc"
    assert resolve_secret_ref("  literal:sk-abc  ") == "sk-abc"
    # 历史明文数据不能静默丢失
    assert resolve_secret_ref("sk-abc") == "sk-abc"


def test_resolve_secret_ref_env(monkeypatch) -> None:
    monkeypatch.setenv("TEST_MODEL_KEY", "env-secret")
    assert resolve_secret_ref("env:TEST_MODEL_KEY") == "env-secret"
    assert resolve_secret_ref("env:NOT_EXIST_KEY") == os.getenv("NOT_EXIST_KEY")
