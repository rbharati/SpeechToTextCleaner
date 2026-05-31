from faster_whisper import WhisperModel

model = WhisperModel("small")

segments, info = model.transcribe("static/harvard.wav")

for segment in segments:
    print(segment.text)