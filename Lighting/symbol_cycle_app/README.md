# Symbol Cycle (App Lab standby app)

Cycles every Sound Guardian symbol on the Adafruit 8x8 RGB NeoPixel matrix,
data pin 6, forever. No Router Bridge, no microphone, no model. Use it when
the matrix must show something and the detection app is not running.

Files:

- `app.yaml`             - App Lab app descriptor
- `sketch/sketch.ino`    - the 88 lighting sketch with `#define STANDBY_CYCLE 1`
- `python/main.py`       - keeps the app alive; does nothing else

Order shown: shatter (glass), SOS (alarm), skull (thud), voice, danger
(unknown), loud, CO, lightning, water, bat signal, Morse SOS, left, right,
then a 1.5 s pause and again.

`sketch/sketch.ino` is generated from
`../88_lighting_animated_rgb/88_lighting_animated_rgb.ino`; after editing
frames there, regenerate with:

    sed 's/^#define STANDBY_CYCLE 0/#define STANDBY_CYCLE 1/' \
        ../88_lighting_animated_rgb/88_lighting_animated_rgb.ino > sketch/sketch.ino

(keep the three GENERATED comment lines at the top if you like).
