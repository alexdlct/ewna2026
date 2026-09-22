import sounddevice as sd
import numpy as np

SAMPLE_RATE = 16000
DURATION = 1

print("Listening...")

while True:

    audio = sd.rec(
        int(SAMPLE_RATE * DURATION),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32"
    )

    sd.wait()

    audio = audio.flatten()

    rms = np.sqrt(np.mean(audio ** 2))

    print("Volume:", rms)