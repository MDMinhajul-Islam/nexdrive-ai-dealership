"""Test-wide environment defaults set before the application is imported."""

import os


os.environ.setdefault("RETELL_TOOL_API_KEY", "test-retell-tool-key")
