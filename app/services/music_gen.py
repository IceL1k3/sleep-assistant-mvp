import os
import torch
import soundfile as sf
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
        
        audio_data = wav[0].squeeze(0).cpu().numpy().T.astype('float32')  # Транспонируем для формата soundfile
        sf.write(output_path, audio_data, 32000, format="WAV")

        print(f"[Generator Service] Стартовый файл сохранен: {output_path}")
        return output_path
        
    def generate_next_chunk(self, prompt: str, previous_chunk_path: str, duration: int = 15, overlap: int = 3) -> str:
        """Генерирует следующий отрезок музыки на основе аудиоконтекста (хвоста последние 3 сек)."""
        print(f"[Generator Service] Continuation: продолжение потока на основе: {previous_chunk_path}")
        
        # 1. Безопасное чтение файла через soundfile
        import soundfile as sf
        prompt_data, sr = sf.read(previous_chunk_path)
        
        # 2. Превращаем массив данных в тензор PyTorch
        prompt_wav = torch.tensor(prompt_data).float()
        
        # 3. Принудительно приводим к 2D виду [channels, frames]:
        # Если soundfile прочитал моно [frames], превращаем в [1, frames].
        # Если стерео [frames, channels], транспонируем в [channels, frames].
        if prompt_wav.ndim == 1:
            prompt_wav = prompt_wav.unsqueeze(0)
        else:
            prompt_wav = prompt_wav.T
            
        # 4. Вырезаем последние `overlap` секунд (хвост) для контекста
        overlap_frames = int(sr * overlap)
        prompt_sequence = prompt_wav[:, -overlap_frames:]
        
        # 🌟 ЖЕЛЕЗОБЕТОННЫЙ ФИКС ДЛЯ ИИ [B, C, T]:
        # Добавляем фейковое измерение батча на нулевую позицию. 
        # Тензор из [channels, frames] гарантированно превращается в 3D [1, channels, frames]!
        prompt_sequence_3d = prompt_sequence.unsqueeze(0)
        
        # 5. Выставляем параметры для генерации продолжения
        self.model.set_generation_params(
            duration=duration,
            top_k=250,
            temperature=1.0,
            cfg_coef=3.0
        )
        
        # 6. Запускаем генерацию продолжения, передавая правильный 3D-тензор
        with torch.inference_mode():
            with torch.autocast(device_type=self.device, dtype=torch.float16):
                wav = self.model.generate_continuation(
                    prompt_sequence_3d.to(self.device), 
                    prompt_sample_rate=sr, 
                    descriptions=[prompt]
                )
                
        next_chunk_path = "app/storage/output_chunk_next.wav"
        
        # 7. Чистое сохранение в float32:
        # wav[0] или wav.squeeze(0) убирает батч -> остается 2D [channels, frames].
        # Переводим в NumPy, транспонируем .T в [frames, channels] для soundfile
        audio_data_next = wav[0].cpu().numpy().T.astype('float32')
        sf.write(next_chunk_path, audio_data_next, 32000, format="WAV")
        
        return next_chunk_path
