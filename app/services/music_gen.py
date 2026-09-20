import os
import torch
from audiocraft.models.musicgen import MusicGen

class AdaptiveMusicGenerator:
    """Бизнес-логика пошаговой генерации музыки (Audio Continuation) на базе MusicGen."""
    def __init__(self, model_name: str = "facebook/musicgen-small"):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"[Generator Service] Загрузка музыкальной модели {model_name} на устройство: {self.device}...")
        
        # Загружаем предобученную модель Meta MusicGen
        self.model = MusicGen.get_pretrained(model_name)
        
        # Оптимизация под мобильную RTX 3050 8GB:
        # Переносим модель в fp16 (mixed precision) для двукратной экономии VRAM и ускорения
        if self.device == "cuda":
            setattr(self.model.lm, "custom_backward", False)  # Фикс для стабильности fp16 в AudioCraft
            # Переводим веса тензоров в половинную точность
            self.model.lm.half() 
            
    def generate_first_chunk(self, prompt: str, duration: int = 15) -> str:
        """Генерирует первые 15 секунд музыки по текстовым тегам."""
        print(f"[Generator Service] Синтез стартового отрезка по промпту: {prompt}")
        
        # Выставляем параметры генерации для нашей видеокарты
        self.model.set_generation_params(
            duration=duration,
            top_k=250,          # Ограничение выборки токенов для стабильности мелодии
            temperature=1.0,    # Контроль хаотичности звука
            cfg_coef=3.0        # Насколько строго следовать текстовому промпту
        )
        
        # Генерируем аудио (на выходе трехмерный тензор)
        with torch.inference_mode():
            with torch.autocast(device_type=self.device, dtype=torch.float16):
                wav = self.model.generate([prompt])
                
        # Путь для сохранения (убедитесь, что папка app/storage будет создана)
        os.makedirs("app/storage", exist_ok=True)
        output_path = "app/storage/output_chunk_0.wav"
        
        # Сохраняем аудио на диск через torchaudio (MusicGen выдает sample rate 32000 Гц)
        import torchaudio
        torchaudio.save(output_path, wav[0].cpu(), sample_rate=32000)
        
        print(f"[Generator Service] Стартовый файл сохранен: {output_path}")
        return output_path
        
    def generate_next_chunk(self, prompt: str, previous_chunk_path: str, duration: int = 15, overlap: int = 3) -> str:
        """Генерирует следующий отрезок музыки на основе аудиоконтекста (хвоста последние 3 сек)."""
        print(f"[Generator Service] Continuation: продолжение потока на основе: {previous_chunk_path}")
        
        import torchaudio
        # 1. Загружаем предыдущий чанк
        prompt_wav, sr = torchaudio.load(previous_chunk_path)
        
        # 2. Вырезаем последние `overlap` секунд (хвост) для контекста
        # sr * overlap — количество фреймов звука
        overlap_frames = int(sr * overlap)
        prompt_sequence = prompt_wav[:, -overlap_frames:]
        
        # 3. Выставляем параметры для продолжения
        self.model.set_generation_params(
            duration=duration,
            top_k=250,
            temperature=1.0,
            cfg_coef=3.0
        )
        
        # 4. Запускаем встроенный метод генерации продолжения
        with torch.inference_mode():
            with torch.autocast(device_type=self.device, dtype=torch.float16):
                # Передаем аудио-хвост и текстовый промпт
                wav = self.model.generate_continuation(
                    prompt_sequence.to(self.device), 
                    prompt_sample_rate=sr, 
                    descriptions=[prompt]
                )
                
        next_chunk_path = "app/storage/output_chunk_next.wav"
        torchaudio.save(next_chunk_path, wav[0].cpu(), sample_rate=32000)
        
        return next_chunk_path
