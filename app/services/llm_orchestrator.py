import json
from openai import OpenAI

class LLMOrchestrator:
    """Текстовый ИИ-мозг бэкенда. Превращает жалобы на сон и DSP-фичи в теги для генератора."""
    def __init__(self, api_url: str = "http://localhost:11434/v1"):
        # Ollama полностью совместима с API OpenAI, используем стандартный клиент
        self.client = OpenAI(base_url=api_url, api_key="ollama")
        self.model_name = "qwen2.5:7b"  # Ваша локальная модель в Ollama

    def generate_music_tags(self, user_complaint: str, audio_features: dict | None = None) -> dict:

        """
        Принимает контекст пользователя и фичи анализатора, 
        возвращает структурированные музыкальные теги.
        """
        # Базовые фичи на случай, если пользователь не загрузил референс
        ref_bpm = audio_features.get("bpm", 60.0) if audio_features else 60.0
        ref_mood = audio_features.get("estimated_mood", "dark/relaxing") if audio_features else "dark/relaxing"
        
        # Системные инструкции для жесткого контроля вывода модели
        system_prompt = (
            "You are an expert AI Music Orchestrator for a sleep assistant application.\n"
            "Your task is to analyze the user's emotional/physical state and combine it with reference audio features "
            "to generate optimal text tags for a music generation AI (MusicGen).\n"
            "CRITICAL: You must reply ONLY with a raw JSON object. Do not include any markdown formatting, "
            "no ```json blocks, no conversational text. Just the pure JSON.\n\n"
            "The JSON structure must be exactly:\n"
            "{\n"
            "  \"musicgen_prompt\": \"string of english tags separated by commas\",\n"
            "  \"reasoning\": \"short explanation in Russian of why these tags were chosen\"\n"
            "}"
        )

        user_prompt = (
            f"User sleep issue: '{user_complaint}'\n"
            f"Reference audio features: BPM={ref_bpm}, Mood='{ref_mood}'\n\n"
            f"Generate the JSON response. Keep musicgen_prompt strictly focused on ambient sleep music, slow tempo, "
            f"matching the target BPM near {ref_bpm}. Use tags like: dark ambient, slow space drone, relaxation, no drums, etc."
        )

        print(f"[LLM Orchestrator] Отправка запроса в локальную Ollama ({self.model_name})...")
        
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                response_format={"type": "json_object"}
            )
            
            # 🌟 ИСПРАВЛЕНО: Безопасное извлечение контента с защитой от None
            raw_content = response.choices[0].message.content
            
            if not raw_content:
                raise ValueError("Локальная LLM вернула пустой ответ (None)")
                
            # Теперь Pylance на 100% уверен, что здесь строка, и не будет ругаться!
            raw_content = raw_content.strip()
            print(f"[LLM Orchestrator] Получен ответ от LLM: {raw_content}")
            
            # Парсим строчку в Python-словарь
            result_json = json.loads(raw_content)
            return result_json
            
        except Exception as e:
            print(f"[LLM Orchestrator Error] Ошибка вызова локальной LLM: {e}")
            # Безопасный дефолтный вариант на случай сбоя
            return {
                "musicgen_prompt": "dark ambient, slow space drone, melancholic guitar, 60 bpm, relaxation, no drums",
                "reasoning": "Ошибка вызова локальной LLM. Применены базовые расслабляющие теги."
            }
