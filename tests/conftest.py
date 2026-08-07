"""Shared fixtures.

The mock model is the reason CI can run the whole pipeline on every push without an API
key or a bill. Contributors get a real end-to-end signal in seconds, which is the
difference between a test suite people run and one they skip.
"""

from __future__ import annotations

import pytest
from inspect_ai.model import Model, ModelOutput, get_model

from aimpoint.core.registry import load_env

MOCK = "mockllm/model"


def submit_call(items: list[dict]) -> ModelOutput:
    """A scripted `submit` tool call."""
    return ModelOutput.for_tool_call(MOCK, "submit", {"items": items})


def abstain_call(reason: str = "insufficient evidence") -> ModelOutput:
    return ModelOutput.for_tool_call(MOCK, "abstain", {"reason": reason})


def request_info_call(field: str, reason: str = "needed") -> ModelOutput:
    return ModelOutput.for_tool_call(MOCK, "request_info", {"field": field, "reason": reason})


def mock_model(outputs: list[ModelOutput]) -> Model:
    """A model that replays a fixed script of tool calls."""
    return get_model(MOCK, custom_outputs=outputs)


@pytest.fixture(scope="session")
def env():
    return load_env("target_triage")


@pytest.fixture(scope="session")
def dev_scenarios(env):
    from aimpoint.core.env import Split

    return env.scenarios(Split.DEV)


@pytest.fixture
def scenario_by_id(dev_scenarios):
    return {scenario.id: scenario for scenario in dev_scenarios}
