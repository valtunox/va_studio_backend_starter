"""
Base Agent

Abstract base class for AI agents.
Provides provider-agnostic interface for building AI agents.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class BaseAgent(ABC):
    """
    Abstract base class for AI agents.

    This class provides the foundation for building AI agents that can
    interact with various LLM providers (OpenAI, Anthropic, etc.).

    To implement a new agent:
    1. Create a new file in the agents/ directory
    2. Inherit from BaseAgent
    3. Implement the required abstract methods
    4. Register tools in the __init__ method

    Example:
        ```python
        from app.services.ai.base_agent import BaseAgent

        class MyAgent(BaseAgent):
            name = "my_agent"
            description = "My custom AI agent"

            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.register_tool(
                    name="my_tool",
                    func=self.my_tool_func,
                    description="Does something useful",
                )

            async def execute(self, input_text: str) -> str:
                # Your agent logic here
                return "Agent response"

            def my_tool_func(self, arg: str) -> str:
                return f"Processed: {arg}"
        ```
    """

    # Agent metadata (override in subclass)
    name: str = "base_agent"
    description: str = "Base AI agent"
    version: str = "1.0.0"

    def __init__(
        self,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs,
    ):
        """
        Initialize the agent.

        Args:
            model: LLM model to use (provider-specific)
            temperature: Sampling temperature (0.0 - 1.0)
            max_tokens: Maximum tokens in response
            **kwargs: Additional provider-specific arguments
        """
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.tools: Dict[str, Dict[str, Any]] = {}
        self.conversation_history: List[Dict[str, str]] = []
        self._provider = None

    def register_tool(
        self,
        name: str,
        func: callable,
        description: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Register a tool that the agent can use.

        Args:
            name: Tool name
            func: Callable function
            description: Tool description
            parameters: JSON schema for parameters
        """
        self.tools[name] = {
            "function": func,
            "description": description,
            "parameters": parameters or {},
        }

    def get_tool(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a registered tool by name."""
        return self.tools.get(name)

    def list_tools(self) -> List[str]:
        """List all registered tool names."""
        return list(self.tools.keys())

    def add_to_history(self, role: str, content: str) -> None:
        """Add a message to conversation history."""
        self.conversation_history.append({"role": role, "content": content})

    def clear_history(self) -> None:
        """Clear conversation history."""
        self.conversation_history = []

    def get_history(self) -> List[Dict[str, str]]:
        """Get conversation history."""
        return self.conversation_history.copy()

    @abstractmethod
    async def execute(self, input_text: str, **kwargs) -> str:
        """
        Execute the agent with the given input.

        Args:
            input_text: User input or query
            **kwargs: Additional execution arguments

        Returns:
            Agent response as string
        """
        pass

    async def stream(self, input_text: str, **kwargs):
        """
        Stream agent response.

        Override this method for streaming support.

        Args:
            input_text: User input or query
            **kwargs: Additional arguments

        Yields:
            Response chunks
        """
        response = await self.execute(input_text, **kwargs)
        yield response

    def to_dict(self) -> Dict[str, Any]:
        """Serialize agent configuration to dict."""
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "tools": list(self.tools.keys()),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BaseAgent":
        """Create agent from dict configuration."""
        return cls(
            model=data.get("model"),
            temperature=data.get("temperature", 0.7),
            max_tokens=data.get("max_tokens", 1000),
        )


class AgentResponse:
    """Container for agent response."""

    def __init__(
        self,
        content: str,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        usage: Optional[Dict[str, int]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.content = content
        self.tool_calls = tool_calls or []
        self.usage = usage or {}
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "tool_calls": self.tool_calls,
            "usage": self.usage,
            "metadata": self.metadata,
        }


class AgentError(Exception):
    """Base exception for agent errors."""

    def __init__(self, message: str, code: Optional[str] = None):
        super().__init__(message)
        self.code = code


class ProviderError(AgentError):
    """Error from LLM provider."""
    pass


class ToolExecutionError(AgentError):
    """Error during tool execution."""
    pass
