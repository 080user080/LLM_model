import os
import sys

# Додати всі можливі шляхи до CUDA бібліотек
venv_path = sys.prefix
nvidia_paths = [
    os.path.join(venv_path, 'Lib', 'site-packages', 'nvidia', 'cublas', 'bin'),
    os.path.join(venv_path, 'Lib', 'site-packages', 'nvidia', 'cudnn', 'bin'),
    os.path.join(venv_path, 'Lib', 'site-packages', 'nvidia', 'cuda_runtime', 'bin'),
    os.path.join(venv_path, 'Lib', 'site-packages', 'nvidia', 'cufft', 'bin'),
]

# Додати до PATH
for path in nvidia_paths:
    if os.path.exists(path):
        os.environ['PATH'] = path + os.pathsep + os.environ['PATH']
        try:
            os.add_dll_directory(path)
        except:
            pass

import sounddevice as sd
import numpy as np
from faster_whisper import WhisperModel

SAMPLE_RATE = 16000
DURATION = 4  # секунд

print("Завантаження моделі...")
model = WhisperModel(
    "medium",
    device="cuda",
    compute_type="float16"
)

print("Говори...")
audio = sd.rec(
    int(DURATION * SAMPLE_RATE),
    samplerate=SAMPLE_RATE,
    channels=1,
    dtype=np.float32
)
sd.wait()

audio = np.squeeze(audio)

segments, info = model.transcribe(
    audio,
    language="uk"
)

print("Результат:")
for seg in segments:
    print(seg.text)