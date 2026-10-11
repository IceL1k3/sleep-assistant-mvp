import json

from loguru import logger
from openai import OpenAI, OpenAIError


class LLMOrchestrator:
    """Текстовый ИИ-мозг бэкенда. Превращает жалобы на сон и DSP-фичи в теги для генератора."""

    def __init__(self, api_url: str = "http://localhost:11434/v1"):
        # Ollama полностью совместима с API OpenAI, используем стандартный клиент
        self.client = OpenAI(base_url=api_url, api_key="ollama")
        self.model_name = "qwen2.5:7b"  # Ваша локальная модель в Ollama

    def generate_music_tags(
        self, user_complaint: str, audio_features: dict | None = None
    ) -> dict:
        """
        Принимает контекст пользователя и фичи анализатора,
        возвращает строго валидированный JSON с музыкальными тегами.
        """
        ref_bpm = audio_features.get("bpm", 60.0) if audio_features else 60.0
        ref_mood = (
            audio_features.get("estimated_mood", "dark/relaxing")
            if audio_features
            else "dark/relaxing"
        )

        # Чистый, понятный для LLM промпт без опасного экранирования кавычек
        # Полностью абстрактный промпт без жестких привязок к конкретным числам
        system_prompt = (
            "You are a strict, production-grade AI Music Orchestrator for a sleep app.\n"
            "Your single job is to output a raw JSON object based on the provided User Request and Reference Audio Features.\n\n"
            "CRITICAL CONSTRAINTS FOR LOGIC AND WEIGHTS:\n"
            "1. Output format MUST be a single raw JSON object with keys 'musicgen_prompt' and 'reasoning'. No markdown, no triple backticks.\n"
            "2. RULE PRIORITIES AND WEIGHTS:\n"
            "   - PRIORITY 1.0 (WEIGHT: 100% - ABSOLUTE COMMAND): User Explicit Intent. If the user explicitly requests drums, beats, rhythm, or specific instruments, you MUST strictly include matching tags (e.g., 'slow hypnotic beat, soft rhythmic pulses, low-frequency downbeat'). In this case, you are FORBIDDEN from using the tag 'no drums'.\n"
            "   - PRIORITY 0.2 (WEIGHT: 20% - RECOMMENDATION): General Sleep Medicine Guidelines. Only apply negative tags like 'no drums, ambient drone' if the user DID NOT ask for rhythm or beats.\n"
            "3. BPM LOGIC: Look at the incoming Reference BPM value. If it represents a fast tempo and the user wants to relax/sleep, mathematically adapt the rhythm to a slow, relaxing sub-tempo (e.g. divide the incoming BPM value by 2) and output that calculated number in the tags. DO NOT delete the rhythm tokens if Priority 1.0 is active.\n"
            "4. NO CONTRADICTIONS: The 'reasoning' field must be in Russian and directly support the generated tokens. Never write contradictory statements.\n\n"
            "Strict JSON structure:\n"
            "{\n"
            '  "musicgen_prompt": "comma-separated english tags",\n'
            '  "reasoning": "короткое логичное объяснение"\n'
            "}"
        )

        user_prompt = (
            f"ACTUAL REQUEST:\n"
            f"User sleep issue: '{user_complaint}'\n"
            f"Reference audio features: BPM={ref_bpm}, Mood='{ref_mood}'\n\n"
            f"Generate the JSON response now."
        )

        print(
            f"[LLM Orchestrator] Отправка чистого промпта в Ollama... BMP:{ref_bpm}, mood:{ref_mood}"
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.4,
                response_format={"type": "json_object"},
            )

            raw_content = response.choices[0].message.content
            if not raw_content:
                raise ValueError("Ollama вернула пустой ответ (None)")

            raw_content = raw_content.strip()
            print(f"[LLM Orchestrator] Живой ответ от LLM: {raw_content}")

            # Парсим строчку в Python-словарь
            result_json = json.loads(raw_content)
            return result_json

        # 2. Ловим ошибку парсинга (когда нейросеть прислала "битый" JSON)
        except json.JSONDecodeError:
            # Используем .exception(), чтобы увидеть в логах, в каком именно символе сломался JSON
            logger.exception(
                "[LLM Orchestrator Error] Ошибка декодирования JSON структуры"
            )
            return self._get_fallback_response(ref_bpm)

        except ValueError as e:
            logger.warning(f"[LLM Orchestrator Error] Сеть вернула пустые данные: {e}")
            return self._get_fallback_response(ref_bpm)

        # 3. Ловим сетевые ошибки (таймаут, упал сервер Ollama, нет связи)
        except OpenAIError as e:
            logger.error(f"[LLM Orchestrator Error] Сбой сети или API: {e}")
            return self._get_fallback_response(ref_bpm)

    def _get_fallback_response(self, ref_bpm: float):
        return {
            "musicgen_prompt": f"dark ambient, slow space drone, {ref_bpm} bpm, relaxation",
            "reasoning": f"Критический сбой ИИ. Применены аварийные теги на базе референса {ref_bpm} BPM.",
        }
