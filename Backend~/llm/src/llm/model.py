"""
LLM Model Wrapper for VR Analytics
Uses NVIDIA API (OpenAI-compatible) with MiniMax M2.7 model.
No local model required — uses cloud inference via NVIDIA API.

API key is discovered automatically from:
  1. NVIDIA_API_KEY environment variable
  2. pipeline_config.json (written by Unity PipelineConfig component)
"""
import logging
import time
from pathlib import Path
from typing import Optional, Iterator, Dict, Any
import sys
import re
from dataclasses import dataclass

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config.settings import MODEL_CONFIG, HARDWARE_CONFIG

logger = logging.getLogger(__name__)

_REASONING_TOKEN_MULTIPLIER = 4


class LLMError(Exception):
    """Base exception for LLM-related errors."""
    pass


class ModelLoadError(LLMError):
    """Raised when client initialization fails."""
    pass


class GenerationError(LLMError):
    """Raised when text generation fails."""
    pass


class ModelNotLoadedError(LLMError):
    """Raised when trying to generate without loading model first."""
    pass


@dataclass
class GenerationResult:
    """Result from a generation request."""
    text: str
    tokens_generated: int
    prompt_tokens: int
    total_tokens: int
    generation_time_seconds: float
    tokens_per_second: float


class LLMInference:
    """
    LLM inference wrapper using NVIDIA's OpenAI-compatible API.
    No local GPU or model file required.
    """

    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
    ):
        self._client = None
        self._config = MODEL_CONFIG.copy()

        self._model = model or self._config.get("model_id", "minimaxai/minimax-m2.7")
        self._api_key = api_key or self._config.get("api_key", "")
        self._base_url = base_url or self._config.get("base_url", "https://integrate.api.nvidia.com/v1")
        self._temperature = temperature if temperature is not None else self._config.get("temperature", 0.7)
        self._max_tokens = max_tokens or self._config.get("max_tokens", 2048)
        self._top_p = top_p if top_p is not None else self._config.get("top_p", 0.9)

        if not self._api_key:
            logger.warning(
                "No NVIDIA API key found. Set NVIDIA_API_KEY env var or enter it "
                "in Unity's PipelineConfig component. LLM analysis will be skipped."
            )

        logger.info(f"LLMInference initialized: model={self._model}, base_url={self._base_url}")

    @property
    def is_loaded(self) -> bool:
        return self._client is not None

    @property
    def llm(self):
        return self._client

    def load_model(self, force_reload: bool = False) -> "LLMInference":
        if not self._api_key:
            raise ModelLoadError(
                "No NVIDIA API key configured. Set NVIDIA_API_KEY environment variable "
                "or enter it in Unity's PipelineConfig Inspector field."
            )

        try:
            from openai import OpenAI
        except ImportError:
            raise ModelLoadError("openai package not installed. Install with: pip install openai")

        if self._client is not None and not force_reload:
            return self

        logger.info(f"Initializing NVIDIA API client (model: {self._model})")
        try:
            self._client = OpenAI(base_url=self._base_url, api_key=self._api_key)
            logger.info("NVIDIA API client initialized successfully")
        except Exception as e:
            raise ModelLoadError(f"Client initialization failed: {e}")

        return self

    def generate(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        stream: bool = False,
        retry_count: int = 3,
        retry_delay: float = 1.0,
        **kwargs,
    ) -> Dict[str, Any]:
        if self._client is None:
            raise ModelNotLoadedError("Client not initialized. Call load_model() first.")

        max_tokens = max_tokens or self._max_tokens
        temperature = temperature if temperature is not None else self._temperature
        top_p = top_p if top_p is not None else self._top_p

        messages = self._parse_prompt_to_messages(prompt)

        last_error = None
        for attempt in range(retry_count):
            try:
                gen_start = time.time()
                api_max_tokens = max_tokens * _REASONING_TOKEN_MULTIPLIER

                if stream:
                    return self._generate_stream(messages, api_max_tokens, temperature, top_p)

                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    temperature=temperature,
                    top_p=top_p,
                    max_tokens=api_max_tokens,
                    stream=False,
                )

                gen_time = time.time() - gen_start
                choice = response.choices[0]
                usage = response.usage

                completion_tokens = usage.completion_tokens if usage else 0
                prompt_tokens = usage.prompt_tokens if usage else 0
                total_tokens = usage.total_tokens if usage else 0

                content = choice.message.content
                if not content:
                    content = getattr(choice.message, "reasoning_content", "") or ""

                result = {
                    "text": content.strip(),
                    "tokens_generated": completion_tokens,
                    "prompt_tokens": prompt_tokens,
                    "total_tokens": total_tokens,
                    "generation_time_seconds": gen_time,
                    "tokens_per_second": completion_tokens / gen_time if gen_time > 0 else 0,
                }

                logger.info(f"Generated {result['tokens_generated']} tokens in {gen_time:.2f}s "
                           f"({result['tokens_per_second']:.1f} tok/s)")
                return result

            except Exception as e:
                last_error = e
                logger.warning(f"Generation attempt {attempt + 1}/{retry_count} failed: {e}")
                if attempt < retry_count - 1:
                    time.sleep(retry_delay)

        raise GenerationError(f"Text generation failed after {retry_count} attempts: {last_error}")

    def _generate_stream(self, messages, max_tokens, temperature, top_p) -> Iterator[str]:
        stream = self._client.chat.completions.create(
            model=self._model, messages=messages,
            temperature=temperature, top_p=top_p,
            max_tokens=max_tokens, stream=True,
        )
        for chunk in stream:
            if not getattr(chunk, "choices", None):
                continue
            if chunk.choices[0].delta.content is not None:
                yield chunk.choices[0].delta.content

    def _parse_prompt_to_messages(self, prompt: str) -> list:
        if "<|user|>" in prompt or "<|system|>" in prompt:
            messages = []
            system_match = re.search(r"<\|system\|>\s*(.*?)\s*<\|end\|>", prompt, re.DOTALL)
            if system_match:
                messages.append({"role": "system", "content": system_match.group(1).strip()})
            user_matches = re.finditer(r"<\|user\|>\s*(.*?)\s*<\|end\|>", prompt, re.DOTALL)
            for match in user_matches:
                messages.append({"role": "user", "content": match.group(1).strip()})
            assistant_matches = re.finditer(r"<\|assistant\|>\s*(.*?)\s*(?:<\|end\|>|$)", prompt, re.DOTALL)
            for match in assistant_matches:
                content = match.group(1).strip()
                if content:
                    messages.append({"role": "assistant", "content": content})
            if messages:
                if not any(m["role"] == "user" for m in messages):
                    messages.append({"role": "user", "content": prompt})
                return messages
        return [{"role": "user", "content": prompt}]

    def create_chat_prompt(self, system_prompt: str, user_prompt: str) -> str:
        return f"<|system|>\n{system_prompt}<|end|>\n<|user|>\n{user_prompt}<|end|>\n<|assistant|>\n"

    def unload(self) -> None:
        if self._client is not None:
            self._client = None

    def get_model_info(self) -> Dict[str, Any]:
        return {
            "model_id": self._model,
            "base_url": self._base_url,
            "is_loaded": self.is_loaded,
            "max_tokens": self._max_tokens,
            "temperature": self._temperature,
            "api_type": "NVIDIA OpenAI-compatible",
        }

    def __enter__(self):
        self.load_model()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.unload()
        return False


LLMModel = LLMInference


def quick_generate(prompt: str, **kwargs) -> Dict[str, Any]:
    with LLMInference() as llm:
        return llm.generate(prompt, **kwargs)
