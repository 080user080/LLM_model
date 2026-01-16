# test_filter.py
import numpy as np
from functions.logic_audio_filtering import get_audio_filter

filter = get_audio_filter()

# Тест: тихий сигнал
quiet_audio = np.random.randn(16000) * 0.001  # -60dB
filtered = filter.process_audio(quiet_audio)

print(f"Гучність ДО: {np.abs(quiet_audio).mean():.6f}")
print(f"Гучність ПІСЛЯ: {np.abs(filtered).mean():.6f}")
print(f"Gain: {filter.current_gain:.1f}x")