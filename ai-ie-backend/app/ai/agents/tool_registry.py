from typing import Iterable


class ToolRegistry:
    """Simple registry for agent tools."""

    def __init__(self):
        self._tools = {}

    def register(self, name: str, tool):
        self._tools[name] = tool
        return tool

    def get(self, name: str):
        return self._tools[name]

    def get_tools(self) -> list:
        return list(self._tools.values())

    def names(self) -> Iterable[str]:
        return self._tools.keys()
