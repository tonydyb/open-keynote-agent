"""Tests for the interactive agent session runtime (004-add-interactive-agent-runtime)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

import open_keynote_agent.cli as cli_module
from open_keynote_agent.agent.executor import execute_plan
from open_keynote_agent.agent.planner import PlanValidationError, plan_turn
from open_keynote_agent.agent.registry import ToolDefinition, ToolRegistry
from open_keynote_agent.agent.session import Plan, ProposedToolCall, SessionState, Turn
from open_keynote_agent.cli import app
from open_keynote_agent.llm.fake import FakeLLMClient
from open_keynote_agent.runtime.events import EventLog
from open_keynote_agent.tools.demo import register_demo_tools


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_registry() -> ToolRegistry:
    registry = ToolRegistry()
    register_demo_tools(registry)
    return registry


def _echo_tool(args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    return {"observation": f"echo: {args.get('msg', '')}", "msg": args.get("msg", "")}


# ---------------------------------------------------------------------------
# ToolRegistry
# ---------------------------------------------------------------------------

class TestToolRegistry:
    def test_register_and_lookup(self):
        registry = ToolRegistry()
        tool = ToolDefinition(
            name="test.echo",
            description="Echo a message",
            parameters={"type": "object", "properties": {"msg": {"type": "string"}}, "required": ["msg"]},
            mutating=False,
            handler=_echo_tool,
        )
        registry.register(tool)
        assert "test.echo" in registry
        assert registry.get("test.echo") is tool

    def test_duplicate_registration_raises(self):
        registry = ToolRegistry()
        tool = ToolDefinition(
            name="test.echo", description="", parameters={}, mutating=False, handler=_echo_tool
        )
        registry.register(tool)
        with pytest.raises(ValueError, match="already registered"):
            registry.register(tool)

    def test_unknown_tool_returns_none(self):
        registry = ToolRegistry()
        assert registry.get("no.such.tool") is None

    def test_all_returns_registered_tools(self):
        registry = _make_registry()
        names = {t.name for t in registry.all()}
        assert "demo.create_document" in names
        assert "demo.add_slide" in names
        assert "demo.export_pdf" in names
        assert "demo.get_document_info" in names


# ---------------------------------------------------------------------------
# SessionState
# ---------------------------------------------------------------------------

class TestSessionState:
    def test_initial_state(self):
        state = SessionState()
        assert state.turns == []
        assert state.context == {}
        assert state.session_id != ""

    def test_recent_observations_empty(self):
        state = SessionState()
        assert state.recent_observations() == []

    def test_recent_observations_accumulated(self):
        state = SessionState()
        plan = Plan(steps=[])
        state.turns.append(Turn(instruction="a", plan=plan, approved=True, observations=["obs1", "obs2"]))
        state.turns.append(Turn(instruction="b", plan=plan, approved=True, observations=["obs3"]))
        assert state.recent_observations() == ["obs1", "obs2", "obs3"]

    def test_recent_observations_window(self):
        state = SessionState()
        plan = Plan(steps=[])
        for i in range(20):
            state.turns.append(Turn(instruction=str(i), plan=plan, approved=True, observations=[f"obs{i}"]))
        obs = state.recent_observations(window=3)
        assert len(obs) == 3
        assert obs[-1] == "obs19"


# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------

class TestPlanner:
    def _registry_with_echo(self) -> ToolRegistry:
        registry = ToolRegistry()
        registry.register(ToolDefinition(
            name="test.echo",
            description="Echo a message",
            parameters={"type": "object", "properties": {"msg": {"type": "string"}}, "required": ["msg"]},
            mutating=False,
            handler=_echo_tool,
        ))
        return registry

    def test_valid_plan_returned(self):
        registry = self._registry_with_echo()
        client = FakeLLMClient(response={
            "steps": [{"tool": "test.echo", "args": {"msg": "hello"}, "description": "Echo hello"}]
        })
        state = SessionState()
        plan = plan_turn("echo hello", state, registry, client)
        assert len(plan.steps) == 1
        assert plan.steps[0].tool == "test.echo"
        assert plan.steps[0].args == {"msg": "hello"}

    def test_unknown_tool_raises(self):
        registry = self._registry_with_echo()
        client = FakeLLMClient(response={
            "steps": [{"tool": "no.such.tool", "args": {}, "description": "oops"}]
        })
        state = SessionState()
        with pytest.raises(PlanValidationError, match="Unknown tool"):
            plan_turn("do something", state, registry, client)

    def test_missing_required_arg_raises(self):
        registry = self._registry_with_echo()
        client = FakeLLMClient(response={
            "steps": [{"tool": "test.echo", "args": {}, "description": "Missing msg"}]
        })
        state = SessionState()
        with pytest.raises(PlanValidationError, match="missing required args"):
            plan_turn("echo without arg", state, registry, client)

    def test_empty_steps_returns_empty_plan(self):
        registry = self._registry_with_echo()
        client = FakeLLMClient(response={"steps": []})
        state = SessionState()
        plan = plan_turn("do nothing", state, registry, client)
        assert plan.steps == []


# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------

class TestExecutor:
    def test_successful_execution(self):
        registry = ToolRegistry()
        registry.register(ToolDefinition(
            name="test.echo",
            description="",
            parameters={"type": "object", "properties": {"msg": {"type": "string"}}, "required": ["msg"]},
            mutating=False,
            handler=_echo_tool,
        ))
        state = SessionState()
        plan = Plan(steps=[ProposedToolCall(tool="test.echo", args={"msg": "hi"}, description="Echo hi")])
        results = execute_plan(plan, registry, state)
        assert len(results) == 1
        assert results[0].ok is True
        assert "hi" in results[0].observation

    def test_handler_exception_recorded_and_stops(self):
        def boom(args: dict, ctx: dict) -> dict:
            raise RuntimeError("kaboom")

        registry = ToolRegistry()
        registry.register(ToolDefinition(
            name="test.boom", description="", parameters={}, mutating=False, handler=boom
        ))
        registry.register(ToolDefinition(
            name="test.echo", description="", parameters={}, mutating=False, handler=_echo_tool
        ))
        state = SessionState()
        plan = Plan(steps=[
            ProposedToolCall(tool="test.boom", args={}, description="boom"),
            ProposedToolCall(tool="test.echo", args={"msg": "after"}, description="after"),
        ])
        results = execute_plan(plan, registry, state)
        assert len(results) == 1
        assert results[0].ok is False
        assert "kaboom" in results[0].error  # type: ignore[operator]

    def test_missing_required_arg_stops(self):
        registry = ToolRegistry()
        registry.register(ToolDefinition(
            name="test.echo",
            description="",
            parameters={"type": "object", "properties": {"msg": {"type": "string"}}, "required": ["msg"]},
            mutating=False,
            handler=_echo_tool,
        ))
        state = SessionState()
        plan = Plan(steps=[ProposedToolCall(tool="test.echo", args={}, description="no arg")])
        results = execute_plan(plan, registry, state)
        assert len(results) == 1
        assert results[0].ok is False


# ---------------------------------------------------------------------------
# Demo tools
# ---------------------------------------------------------------------------

class TestDemoTools:
    def test_create_document(self):
        registry = _make_registry()
        state = SessionState()
        plan = Plan(steps=[ProposedToolCall(
            tool="demo.create_document", args={"name": "test"}, description="create"
        )])
        results = execute_plan(plan, registry, state)
        assert results[0].ok
        assert state.context["demo"]["name"] == "test"
        assert state.context["demo"]["slides"] == []

    def test_add_slide(self):
        registry = _make_registry()
        state = SessionState()
        state.context["demo"] = {"name": "test", "slides": []}
        plan = Plan(steps=[ProposedToolCall(
            tool="demo.add_slide", args={"kind": "title", "title": "Hello"}, description="add"
        )])
        results = execute_plan(plan, registry, state)
        assert results[0].ok
        assert len(state.context["demo"]["slides"]) == 1
        assert state.context["demo"]["slides"][0]["title"] == "Hello"

    def test_set_text(self):
        registry = _make_registry()
        state = SessionState()
        state.context["demo"] = {"name": "test", "slides": [{"kind": "title", "title": "T", "text": ""}]}
        plan = Plan(steps=[ProposedToolCall(
            tool="demo.set_text", args={"slide": 1, "text": "body text"}, description="set"
        )])
        results = execute_plan(plan, registry, state)
        assert results[0].ok
        assert state.context["demo"]["slides"][0]["text"] == "body text"

    def test_set_text_out_of_range_fails(self):
        registry = _make_registry()
        state = SessionState()
        state.context["demo"] = {"name": "test", "slides": []}
        plan = Plan(steps=[ProposedToolCall(
            tool="demo.set_text", args={"slide": 5, "text": "x"}, description="oob"
        )])
        results = execute_plan(plan, registry, state)
        assert results[0].ok is False

    def test_export_pdf(self, tmp_path: Path):
        registry = _make_registry()
        state = SessionState()
        state.context["demo"] = {"name": "test", "slides": []}
        out = tmp_path / "out.pdf"
        plan = Plan(steps=[ProposedToolCall(
            tool="demo.export_pdf", args={"path": str(out)}, description="export"
        )])
        results = execute_plan(plan, registry, state)
        assert results[0].ok
        assert out.exists()

    def test_get_document_info_no_doc(self):
        registry = _make_registry()
        state = SessionState()
        plan = Plan(steps=[ProposedToolCall(
            tool="demo.get_document_info", args={}, description="info"
        )])
        results = execute_plan(plan, registry, state)
        assert results[0].ok
        assert results[0].output["name"] is None

    def test_get_document_info_with_doc(self):
        registry = _make_registry()
        state = SessionState()
        state.context["demo"] = {"name": "proj", "slides": [{}, {}]}
        plan = Plan(steps=[ProposedToolCall(
            tool="demo.get_document_info", args={}, description="info"
        )])
        results = execute_plan(plan, registry, state)
        assert results[0].ok
        assert results[0].output["name"] == "proj"
        assert results[0].output["slide_count"] == 2

    def test_add_slide_without_document_fails(self):
        registry = _make_registry()
        state = SessionState()
        plan = Plan(steps=[ProposedToolCall(
            tool="demo.add_slide", args={"kind": "title", "title": "X"}, description="add"
        )])
        results = execute_plan(plan, registry, state)
        assert results[0].ok is False


# ---------------------------------------------------------------------------
# EventLog
# ---------------------------------------------------------------------------

class TestEventLog:
    def test_events_written_in_order(self, tmp_path: Path):
        log = EventLog(tmp_path / "events.jsonl")
        log.append("session_start", {"session_id": "abc"})
        log.append("turn_start", {"turn_index": 0, "instruction": "hi"})
        log.append("session_end", {"session_id": "abc", "turn_count": 1})

        lines = (tmp_path / "events.jsonl").read_text().splitlines()
        events = [json.loads(line) for line in lines]
        assert len(events) == 3
        assert events[0]["seq"] == 0
        assert events[0]["type"] == "session_start"
        assert events[1]["seq"] == 1
        assert events[1]["type"] == "turn_start"
        assert events[2]["seq"] == 2
        assert events[2]["type"] == "session_end"

    def test_events_have_ts_field(self, tmp_path: Path):
        log = EventLog(tmp_path / "events.jsonl")
        log.append("ping", {})
        line = (tmp_path / "events.jsonl").read_text().strip()
        event = json.loads(line)
        assert "ts" in event
        assert event["ts"]  # non-empty


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------

runner = CliRunner()


class TestSessionCLI:
    def test_session_exits_on_done(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        client = FakeLLMClient(response={"steps": []})
        monkeypatch.setattr(cli_module, "load_llm_client_from_env", lambda: client)
        result = runner.invoke(app, ["session", "--no-confirm"], input="done\n")
        assert result.exit_code == 0
        assert "Session ended" in result.output

    def test_session_single_turn_no_confirm(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        client = FakeLLMClient(response={
            "steps": [{"tool": "demo.create_document", "args": {"name": "proj"}, "description": "Create proj"}]
        })
        monkeypatch.setattr(cli_module, "load_llm_client_from_env", lambda: client)
        result = runner.invoke(app, ["session", "--no-confirm"], input="create a deck\ndone\n")
        assert result.exit_code == 0
        assert "Create proj" in result.output
        assert 'Created document "proj"' in result.output

    def test_session_writes_event_log(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        client = FakeLLMClient(response={
            "steps": [{"tool": "demo.get_document_info", "args": {}, "description": "Get info"}]
        })
        monkeypatch.setattr(cli_module, "load_llm_client_from_env", lambda: client)
        result = runner.invoke(app, ["session", "--no-confirm"], input="check status\ndone\n")
        assert result.exit_code == 0

        runs = list((tmp_path / ".runs").iterdir())
        assert len(runs) == 1
        events_path = runs[0] / "events.jsonl"
        assert events_path.exists()
        events = [json.loads(line) for line in events_path.read_text().splitlines()]
        types = [e["type"] for e in events]
        assert "session_start" in types
        assert "turn_start" in types
        assert "plan_proposed" in types
        assert "session_end" in types

    def test_session_rejection_skips_execution(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        client = FakeLLMClient(response={
            "steps": [{"tool": "demo.create_document", "args": {"name": "x"}, "description": "Create x"}]
        })
        monkeypatch.setattr(cli_module, "load_llm_client_from_env", lambda: client)
        result = runner.invoke(app, ["session"], input="create a deck\nn\ndone\n")
        assert result.exit_code == 0
        assert "Skipped" in result.output
        assert "demo" not in str(tmp_path / ".runs")
