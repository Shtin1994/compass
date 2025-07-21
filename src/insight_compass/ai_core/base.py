# --- START OF FILE src/insight_compass/ai_core/base.py ---

from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BaseLLMAnalyzer(ABC):
    """
    Абстрактный базовый класс (контракт) для всех анализаторов на базе LLM.

    Определяет, какие методы должен реализовать любой анализатор,
    чтобы быть совместимым с нашей системой.
    """

    @abstractmethod
    async def get_analysis(self, post_text: str, comments: List[str]) -> Dict[str, Any]:
        """
        Основной метод, выполняющий комплексный анализ текста.

        Должен принимать текст поста и список текстов комментариев и возвращать
        словарь со структурированным результатом анализа (summary, sentiment, etc.).
        """
        pass

# --- END OF FILE src/insight_compass/ai_core/base.py ---