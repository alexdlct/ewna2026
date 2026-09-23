# Symbol Cycle (App Lab standby app)

Cycles every Sound Guardian symbol on the Adafruit 8x8 RGB NeoPixel matrix,
data pin 6, forever. No Router Bridge, no commands, no microphone, no model.
Use it when the matrix must show something and the detection app is not
running.

Files:

- `app.yaml`             - App Lab app descriptor
- `sketch/sketch.ino`    - standalone sketch: patterns + animations + a loop that plays them all
- `python/main.py`       - keeps the app alive; does nothing else
- `generate_sketch.py`   - rebuilds sketch/sketch.ino from the main lighting sketch

Order shown: shatter (glass), SOS (alarm), skull (thud), voice, danger
(unknown), question mark, loud, CO, lightning, water, bat signal, Morse SOS,
left, right, then a 1.5 s pause and again.

`sketch/sketch.ino` is generated. After anyone edits frames or animations in
`../88_lighting_animated_rgb/88_lighting_animated_rgb.ino`, run:

    python generate_sketch.py

It copies the matrix config, colours, patterns, helpers and every `animate*()`
function, drops the Bridge and command code, and writes a fresh `setup()` and
`loop()`. New animations not yet in its ORDER list are appended at the end.
