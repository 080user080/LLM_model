from faster_whisper import WhisperModel

model = WhisperModel(
    "medium",
    device="cuda",
    compute_type="float16"
)

segments, info = model.transcribe(
    "test.wav",
    language="uk"
)

for s in segments:
    print(s.text)
