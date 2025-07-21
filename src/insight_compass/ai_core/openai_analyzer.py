# --- START OF FILE src/insight_compass/ai_core/openai_analyzer.py ---

import json
import logging
from pathlib import Path
from typing import List, Dict, Any

from openai import AsyncOpenAI

from ..core.config import settings
from .base import BaseLLMAnalyzer  # <-- ИЗМЕНЕНО: Импортируем наш контракт

logger = logging.getLogger(__name__)

class PromptManager:
    _prompts_cache: Dict[str, str] = {}
    _prompts_dir = Path(__file__).resolve().parents[3] / "config" / "prompts" / "openai"

    @classmethod
    def get_prompt(cls, name: str, **kwargs) -> str:
        if name not in cls._prompts_cache:
            try:
                prompt_path = cls._prompts_dir / f"{name}.txt"
                with open(prompt_path, 'r', encoding='utf-8') as f:
                    cls._prompts_cache[name] = f.read()
            except FileNotFoundError:
                logger.error(f"Prompt file not found: {prompt_path}")
                raise
        return cls._prompts_cache[name].format(**kwargs)


# ИЗМЕНЕНО: Класс теперь реализует наш контракт BaseLLMAnalyzer
class OpenAIAnalyzer(BaseLLMAnalyzer):
    """
    Конкретная реализация анализатора для OpenAI.
    """
    def __init__(self, client: AsyncOpenAI):
        self.client = client

    async def get_analysis(self, post_text: str, comments: List[str]) -> Dict[str, Any]:
        """
        Выполняет комплексный анализ одним запросом к OpenAI в JSON mode.
        """
        full_text = f"ПОСТ:\n{post_text}\n\nКОММЕНТАРИИ:\n" + "\n".join(f"- {c}" for c in comments)
        truncated_text = full_text[:settings.LLM_MAX_PROMPT_LENGTH]

        prompt = PromptManager.get_prompt("full_analysis", text=truncated_text)

        response = await self.client.chat.completions.create(
            model=settings.OPENAI_DEFAULT_MODEL_FOR_TASKS,
            messages=[
                {"role": "system", "content": "You are a helpful AI analyst. Your response must be a valid JSON object."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        content = response.choices[0].message.content

        try:
            analysis_data = json.loads(content)
            analysis_data["model_used"] = response.model
            return analysis_data
        except json.JSONDecodeError:
            logger.error(f"Failed to decode JSON from OpenAI response: {content}")
            return {"error": "Failed to decode JSON from LLM response"}

# --- END OF FILE src/insight_compass/ai_core/openai_analyzer.py ---