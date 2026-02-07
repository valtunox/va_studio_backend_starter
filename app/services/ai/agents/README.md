# AI Agents Guide

This directory contains AI agent implementations for the VA Studio Backend.

## Overview

AI agents provide intelligent automation capabilities powered by Large Language Models (LLMs).
The architecture is provider-agnostic, supporting multiple LLM providers.

## Supported Providers

Configure your preferred provider in the `.env` file:

- **OpenAI**: Set `OPENAI_API_KEY`
- **Anthropic**: Set `ANTHROPIC_API_KEY`
- **Google Gemini**: Set `GOOGLE_API_KEY`
- **Azure OpenAI**: Set `AZURE_OPENAI_API_KEY` and `AZURE_OPENAI_ENDPOINT`

## Creating a New Agent

1. Create a new Python file in this directory (e.g., `my_agent.py`)

2. Inherit from `BaseAgent`:

```python
from app.services.ai.base_agent import BaseAgent, AgentResponse

class MyAgent(BaseAgent):
    name = "my_agent"
    description = "Description of what this agent does"
    version = "1.0.0"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Register tools the agent can use
        self.register_tool(
            name="search",
            func=self.search,
            description="Search for information",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                },
                "required": ["query"],
            },
        )

    async def execute(self, input_text: str, **kwargs) -> str:
        """Main execution logic."""
        # Add to conversation history
        self.add_to_history("user", input_text)

        # Your agent logic here
        # Example with OpenAI:
        # from openai import AsyncOpenAI
        # client = AsyncOpenAI()
        # response = await client.chat.completions.create(...)

        response = f"Processed: {input_text}"

        self.add_to_history("assistant", response)
        return response

    def search(self, query: str) -> str:
        """Tool function for searching."""
        # Implement search logic
        return f"Search results for: {query}"
```

3. Register the agent in `__init__.py`:

```python
from app.services.ai.agents.my_agent import MyAgent

__all__ = ["MyAgent"]
```

4. Add route endpoint if needed in `routes.py`.

## Using LangChain

For more complex agents, use LangChain:

```python
from langchain.chat_models import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain.tools import Tool
from langchain.prompts import ChatPromptTemplate

class LangChainAgent(BaseAgent):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.llm = ChatOpenAI(model="gpt-4", temperature=0.7)

    async def execute(self, input_text: str, **kwargs) -> str:
        tools = [
            Tool(
                name="search",
                func=self.search,
                description="Search for information",
            ),
        ]

        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a helpful assistant."),
            ("human", "{input}"),
        ])

        agent = create_openai_tools_agent(self.llm, tools, prompt)
        executor = AgentExecutor(agent=agent, tools=tools)

        result = await executor.ainvoke({"input": input_text})
        return result["output"]
```

## Best Practices

1. **Keep agents focused**: Each agent should have a specific purpose
2. **Use tools**: Break complex tasks into reusable tools
3. **Handle errors gracefully**: Catch provider errors and return helpful messages
4. **Log interactions**: Use the logger for debugging
5. **Respect rate limits**: Implement backoff for API rate limits
6. **Secure prompts**: Never expose system prompts to users
7. **Test thoroughly**: Write unit tests for agent logic

## Example Agents

### Assistant Agent
General-purpose conversational AI for customer support, FAQ, etc.

### Code Agent
Code generation, review, and explanation.

### Analytics Agent
Data analysis, report generation, and insights.

### Email Agent
Email composition and response drafting.

## Configuration

Environment variables for AI configuration:

```env
# OpenAI
OPENAI_API_KEY=sk-...

# Anthropic
ANTHROPIC_API_KEY=sk-ant-...

# Model selection
AI_PROVIDER=openai  # or: anthropic, google, azure
AI_MODEL=gpt-4
AI_TEMPERATURE=0.7
AI_MAX_TOKENS=1000
```

## Dependencies

Required packages for AI features:

```txt
langchain>=0.1.0
langchain-openai>=0.0.5
langchain-anthropic>=0.1.0
openai>=1.0.0
anthropic>=0.5.0
```

Add these to `requirements.txt` when implementing AI features.
