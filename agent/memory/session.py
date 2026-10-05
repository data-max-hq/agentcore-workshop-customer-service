"""AgentCore Memory session manager, with a no-op local fallback.

`get_memory_session_manager` returns None when the memory isn't deployed (its
env var is unset -- e.g. local `agentcore dev`), so main.py falls back to an
in-process session dict and local dev needs no cloud. `agentcore deploy` sets
MEMORY_REFUNDMEMORY_ID and this returns a real manager backed by AgentCore Memory.
"""
import os
import uuid
from typing import Optional

from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig
from bedrock_agentcore.memory.integrations.strands.session_manager import AgentCoreMemorySessionManager

MEMORY_ID = os.getenv("MEMORY_REFUNDMEMORY_ID")  # set by `agentcore deploy`
REGION = os.getenv("AWS_REGION")


def get_memory_session_manager(session_id: Optional[str], actor_id: str) -> Optional[AgentCoreMemorySessionManager]:
    if not MEMORY_ID:
        return None
    return AgentCoreMemorySessionManager(
        AgentCoreMemoryConfig(
            memory_id=MEMORY_ID,
            session_id=session_id or uuid.uuid4().hex,
            actor_id=actor_id,
        ),
        REGION,
    )
