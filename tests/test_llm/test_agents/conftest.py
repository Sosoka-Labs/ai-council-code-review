"""conftest for test_agents.

The installed langchain/langgraph versions have a broken import:
  langchain.agents.factory imports ToolCallTransformer from langgraph.prebuilt,
  which no longer exists in the installed langgraph version.

We stub the broken module in sys.modules before any test collection begins so
that importing any agent module (which transitively pulls in langchain.agents)
does not raise an ImportError.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

# Only install the stub when the broken module is not already importable.
try:
    import langchain.agents  # noqa: F401
except ImportError:
    _agents_stub = MagicMock()
    # Provide the specific names that generalist.py uses at import time.
    _agents_stub.AgentExecutor = MagicMock
    _agents_stub.create_tool_calling_agent = MagicMock()
    sys.modules.setdefault("langchain.agents", _agents_stub)
    sys.modules.setdefault("langchain.agents.factory", MagicMock())
