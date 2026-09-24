import os
import numpy as np
import librosa

class AudioAnalyzer:

    def __init__(self) -> None:
        print("[Audio Analyzer] Инициализация сервиса анализа референсов...")

    async def analyze_reference_track(self, file_path: str) -> dict:

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Файл не найден по пути: {file_path}")

        print(f"[Audio Analyzer] Начало анализа трека: {file_path}")

        y, sr = librosa.load(path = file_path, sr=None)

        tempo,_= librosa.beat.beat_track(y=y,sr=sr)
        bpm = float(tempo) if isinstance(tempo, (np.ndarray, list)) else float(tempo)

        centroid = librosa.feature.spectral_centroid(y=y,sr=sr)
        centroid_mean = np.mean(centroid)

        chroma = librosa.feature.chroma_stft(y=y,sr=sr)
        chroma_mean = [float(np.mean(c)) for c in chroma ]

        analysis_result = {
            "bpm": round(bpm, 1),
            "spectral_centroid": round(centroid_mean, 2),
            "chroma_features": [round(x, 3) for x in chroma_mean],
            "estimated_mood": "dark/relaxing" if centroid_mean < 2200 else "bright/active"
        }

        return analysis_result