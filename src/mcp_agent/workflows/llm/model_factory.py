from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional, Type, Dict, Union, Callable

from mcp_agent.agents.agent import Agent
from mcp_agent.workflows.llm.augmented_llm_anthropic import AnthropicAugmentedLLM
from mcp_agent.workflows.llm.augmented_llm_openai import OpenAIAugmentedLLM
from mcp_agent.workflows.llm.augmented_llm import RequestParams

# Type alias for LLM classes
LLMClass = Union[Type[AnthropicAugmentedLLM], Type[OpenAIAugmentedLLM]]


class Provider(Enum):
    """Supported LLM providers"""

    ANTHROPIC = auto()
    OPENAI = auto()


class ReasoningEffort(Enum):
    """Optional reasoning effort levels"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class ModelConfig:
    """Configuration for a specific model"""

    provider: Provider
    model_name: str
    reasoning_effort: Optional[ReasoningEffort] = None


class ModelFactory:
    """Factory for creating LLM instances based on model specifications"""

    # Mapping of provider strings to enum values
    PROVIDER_MAP = {
        "anthropic": Provider.ANTHROPIC,
        "openai": Provider.OPENAI,
    }

    # Mapping of effort strings to enum values
    EFFORT_MAP = {
        "low": ReasoningEffort.LOW,
        "medium": ReasoningEffort.MEDIUM,
        "high": ReasoningEffort.HIGH,
    }

    # TODO -- add context window size information for display/mmanagement
    # TODO -- add audio supporting got-4o-audio-preview
    # Mapping of model names to their default providers
    DEFAULT_PROVIDERS = {
        "gpt-4o": Provider.OPENAI,
        "gpt-4o-mini": Provider.OPENAI,
        "o1-mini": Provider.OPENAI,
        "o1": Provider.OPENAI,
        "o1-preview": Provider.OPENAI,
        "o3-mini": Provider.OPENAI,
        "claude-3-haiku-20240307": Provider.ANTHROPIC,
        "claude-3-5-sonnet-20240620": Provider.ANTHROPIC,
        "claude-3-5-sonnet-20241022": Provider.ANTHROPIC,
        "claude-3-5-sonnet-latest": Provider.ANTHROPIC,
        "claude-3-7-sonnet-latest": Provider.ANTHROPIC,
        "claude-3-7-sonnet-20250219": Provider.ANTHROPIC,
        "claude-3-opus-20240229": Provider.ANTHROPIC,
        "claude-3-opus-latest": Provider.ANTHROPIC,
    }

    MODEL_ALIASES = {
        "sonnet": "claude-3-7-sonnet-latest",
        "sonnet35": "claude-3-5-sonnet-latest",
        "sonnet37": "claude-3-7-sonnet-latest",
        "claude": "claude-3-5-sonnet-latest",
        "haiku": "claude-3-haiku-20240307",
        "haiku3": "claude-3-haiku-20240307",
        "opus": "claude-3-opus-latest",
        "opus3": "claude-3-opus-latest",
    }

    # Mapping of providers to their LLM classes
    PROVIDER_CLASSES: Dict[Provider, LLMClass] = {
        Provider.ANTHROPIC: AnthropicAugmentedLLM,
        Provider.OPENAI: OpenAIAugmentedLLM,
    }

    @classmethod
    def parse_model_string(cls, model_string: str) -> ModelConfig:
        """Parse a model string into a ModelConfig object"""
        # Check if model string is an alias
        model_string = cls.MODEL_ALIASES.get(model_string, model_string)
        parts = model_string.split(".")

        # Start with all parts as the model name
        model_parts = parts.copy()
        provider = None
        reasoning_effort = None

        # Check last part for reasoning effort
        if len(parts) > 1 and parts[-1].lower() in cls.EFFORT_MAP:
            reasoning_effort = cls.EFFORT_MAP[parts[-1].lower()]
            model_parts = model_parts[:-1]

        # Check first part for provider
        if len(model_parts) > 1:
            potential_provider = model_parts[0]
            if potential_provider in cls.PROVIDER_MAP:
                provider = cls.PROVIDER_MAP[potential_provider]
                model_parts = model_parts[1:]

        # Join remaining parts as model name
        model_name = ".".join(model_parts)

        # If no provider was found in the string, look it up in defaults
        if provider is None:
            provider = cls.DEFAULT_PROVIDERS.get(model_name)
            if provider is None:
                raise ValueError(f"Unknown model: {model_name}")

        return ModelConfig(
            provider=provider, model_name=model_name, reasoning_effort=reasoning_effort
        )

    @classmethod
    def create_factory(
        cls, model_string: str, request_params: Optional[RequestParams] = None
    ) -> Callable[..., LLMClass]:
        """
        Creates a factory function that follows the attach_llm protocol.

        Args:
            model_string: The model specification string (e.g. "gpt-4o.high")
            request_params: Optional parameters to configure LLM behavior

        Returns:
            A callable that takes an agent parameter and returns an LLM instance
        """
        # Parse configuration up front
        config = cls.parse_model_string(model_string)
        llm_class = cls.PROVIDER_CLASSES[config.provider]

        # Create a factory function matching the attach_llm protocol
        def factory(agent: Agent, **kwargs) -> LLMClass:
            # Create merged params with parsed model name
            factory_params = (
                request_params.model_copy() if request_params else RequestParams()
            )
            factory_params.model = (
                config.model_name
            )  # Use the parsed model name, not the alias

            # Merge with any provided default_request_params
            if "default_request_params" in kwargs and kwargs["default_request_params"]:
                params_dict = factory_params.model_dump()
                params_dict.update(
                    kwargs["default_request_params"].model_dump(exclude_unset=True)
                )
                factory_params = RequestParams(**params_dict)
                factory_params.model = (
                    config.model_name
                )  # Ensure parsed model name isn't overwritten

            llm = llm_class(
                agent=agent,
                model=config.model_name,
                reasoning_effort=config.reasoning_effort.value
                if config.reasoning_effort
                else None,
                request_params=factory_params,
                name=kwargs.get("name"),
            )
            return llm

        return factory
