// sound_events.ino — Arduino UNO R4 WiFi LED matrix
//
// The PC does all audio processing and sends one event name per line over
// serial (115200 baud). This sketch only maps the name to an LED animation.
//
//   ALARM   -> SOS flashing
//   VOICE   -> sound-wave animation
//   FALL    -> skull flashes
//   STEPS   -> soft moving droplet gesture
//   GLASS   -> shatter growing outward
//   UNKNOWN -> double danger-sign pulse
//   IDLE    -> clear the matrix
//
// Test by hand: open Serial Monitor (115200, newline) and type GLASS.

#include <Arduino_LED_Matrix.h>

Arduino_LED_Matrix matrix;

// ============================================================
// FRAMES (8 rows x 13 cols, copied from lightning_animated.ino)
// ============================================================

uint8_t voice1[104] = {
  0,0,0,0,0,0,0,0,0,0,0,0,0,
  0,0,0,0,0,0,1,0,0,0,0,0,0,
  0,0,0,0,1,0,1,0,1,0,0,0,0,
  0,0,1,0,1,0,1,0,1,0,1,0,0,
  0,0,1,0,1,0,1,0,1,0,1,0,0,
  0,0,0,0,1,0,1,0,1,0,0,0,0,
  0,0,0,0,0,0,1,0,0,0,0,0,0,
  0,0,0,0,0,0,0,0,0,0,0,0,0
};

uint8_t voice2[104] = {
  0,0,0,0,1,0,1,0,1,0,0,0,0,
  0,0,1,0,1,0,1,0,1,0,1,0,0,
  1,0,1,0,1,0,1,0,1,0,1,0,1,
  1,0,1,0,1,0,1,0,1,0,1,0,1,
  1,0,1,0,1,0,1,0,1,0,1,0,1,
  1,0,1,0,1,0,1,0,1,0,1,0,1,
  0,0,1,0,1,0,1,0,1,0,1,0,0,
  0,0,0,0,1,0,1,0,1,0,0,0,0
};

uint8_t water1[104] = {
  0,0,0,0,0,0,1,0,0,0,0,0,0,
  0,0,0,0,0,1,1,1,0,0,0,0,0,
  0,0,0,0,0,0,1,0,0,0,0,0,0,
  0,0,0,0,0,0,0,0,0,0,0,0,0,
  0,0,0,0,0,0,0,0,0,0,0,0,0,
  0,0,0,0,0,0,0,0,0,0,0,0,0,
  0,0,0,0,0,0,0,0,0,0,0,0,0,
  0,0,0,0,0,0,0,0,0,0,0,0,0
};

uint8_t water2[104] = {
  0,0,0,0,0,0,0,0,0,0,0,0,0,
  0,0,0,0,0,0,0,0,0,0,0,0,0,
  0,0,0,0,0,0,1,0,0,0,0,0,0,
  0,0,0,0,0,1,1,1,0,0,0,0,0,
  0,0,0,0,0,1,1,1,0,0,0,0,0,
  0,0,0,0,0,0,1,0,0,0,0,0,0,
  0,0,0,0,0,0,0,0,0,0,0,0,0,
  0,0,0,0,0,0,0,0,0,0,0,0,0
};

uint8_t water3[104] = {
  0,0,0,0,0,0,0,0,0,0,0,0,0,
  0,0,0,0,0,0,0,0,0,0,0,0,0,
  0,0,0,0,0,0,0,0,0,0,0,0,0,
  0,0,0,0,0,0,1,0,0,0,0,0,0,
  0,0,0,0,0,1,1,1,0,0,0,0,0,
  0,0,0,0,1,1,1,1,1,0,0,0,0,
  0,0,0,0,1,1,1,1,1,0,0,0,0,
  0,0,0,0,0,1,1,1,0,0,0,0,0
};

uint8_t danger_sign[104] = {
  0,0,0,0,0,0,1,0,0,0,0,0,0,
  0,0,0,0,0,1,0,1,0,0,0,0,0,
  0,0,0,0,1,0,1,0,1,0,0,0,0,
  0,0,0,1,0,0,1,0,0,1,0,0,0,
  0,0,1,0,0,0,1,0,0,0,1,0,0,
  0,1,0,0,0,0,0,0,0,0,0,1,0,
  1,0,0,0,0,0,1,0,0,0,0,0,1,
  1,1,1,1,1,1,1,1,1,1,1,1,1
};

uint8_t shatter1[104] = {
  0,0,0,0,0,0,0,0,0,0,0,0,0,
  0,0,0,0,0,0,0,0,0,0,0,0,0,
  0,0,0,0,0,0,1,0,0,0,0,0,0,
  0,0,0,0,0,1,1,1,0,0,0,0,0,
  0,0,0,0,0,1,1,1,0,0,0,0,0,
  0,0,0,0,0,0,1,0,0,0,0,0,0,
  0,0,0,0,0,0,0,0,0,0,0,0,0,
  0,0,0,0,0,0,0,0,0,0,0,0,0
};

uint8_t shatter2[104] = {
  0,0,0,0,0,0,1,0,0,0,0,0,0,
  0,0,0,0,0,0,1,0,0,0,0,0,0,
  0,0,1,0,0,0,1,0,0,0,1,0,0,
  0,0,0,1,0,1,1,1,0,1,0,0,0,
  0,0,0,1,1,1,1,1,1,1,0,0,0,
  0,0,1,0,0,0,1,0,0,0,1,0,0,
  0,0,0,0,0,0,1,0,0,0,0,0,0,
  0,0,0,0,0,0,1,0,0,0,0,0,0
};

uint8_t shatter3[104] = {
  1,0,0,0,0,0,1,0,0,0,0,0,1,
  0,1,0,0,0,0,1,0,0,0,0,1,0,
  0,0,1,0,0,0,1,0,0,0,1,0,0,
  0,0,0,1,0,1,1,1,0,1,0,0,0,
  1,1,1,1,1,1,1,1,1,1,1,1,1,
  0,0,0,1,0,1,1,1,0,1,0,0,0,
  0,0,1,0,0,0,1,0,0,0,1,0,0,
  0,1,0,0,0,0,1,0,0,0,0,1,0
};

uint8_t skull[104] = {
  0,0,0,1,1,1,1,1,1,1,0,0,0,
  0,0,1,1,1,1,1,1,1,1,1,0,0,
  0,1,1,1,0,0,1,0,0,1,1,1,0,
  0,1,1,1,0,0,1,0,0,1,1,1,0,
  0,1,1,1,1,1,1,1,1,1,1,1,0,
  0,0,1,1,0,1,0,1,0,1,1,0,0,
  0,0,0,1,1,1,1,1,1,1,0,0,0,
  0,0,0,1,0,1,0,1,0,1,0,0,0
};

uint8_t SOS[104] = {
  0,1,1,0,0,1,1,1,0,0,1,1,0,
  1,0,0,0,1,0,0,0,1,1,0,0,0,
  1,0,0,0,1,0,0,0,1,1,0,0,0,
  0,1,0,0,1,0,0,0,1,0,1,0,0,
  0,0,1,0,1,0,0,0,1,0,0,1,0,
  0,0,1,0,1,0,0,0,1,0,0,1,0,
  0,0,1,0,1,0,0,0,1,0,0,1,0,
  1,1,0,0,0,1,1,1,0,1,1,0,0
};

// ============================================================
// ANIMATIONS (blocking, delay-based — fine for the MVP)
// ============================================================

void animateVoice() {
  for (int i = 0; i < 4; i++) {
    matrix.draw(voice1); delay(180);
    matrix.draw(voice2); delay(180);
  }
}

void animateSteps() {
  // soft moving gesture: droplet falls twice
  for (int i = 0; i < 2; i++) {
    matrix.draw(water1); delay(180);
    matrix.draw(water2); delay(180);
    matrix.draw(water3); delay(350);
    matrix.clear();      delay(150);
  }
}

void animateUnknown() {
  // double warning pulse
  for (int i = 0; i < 2; i++) {
    matrix.draw(danger_sign); delay(200);
    matrix.clear();           delay(120);
  }
  matrix.draw(danger_sign); delay(400);
}

void animateShatter() {
  matrix.draw(shatter1); delay(130);
  matrix.draw(shatter2); delay(130);
  matrix.draw(shatter3); delay(500);
  matrix.clear();        delay(120);
  matrix.draw(shatter3); delay(300);
}

void animateSkull() {
  for (int i = 0; i < 3; i++) {
    matrix.draw(skull); delay(300);
    matrix.clear();     delay(120);
  }
  matrix.draw(skull); delay(500);
}

void animateSOS() {
  for (int i = 0; i < 6; i++) {
    matrix.draw(SOS); delay(180);
    matrix.clear();   delay(120);
  }
  matrix.draw(SOS); delay(500);
}

// ============================================================
// SERIAL DISPATCH
// ============================================================

void handleEvent(const String &cmd) {
  if      (cmd == "ALARM")   animateSOS();
  else if (cmd == "VOICE")   animateVoice();
  else if (cmd == "FALL")    animateSkull();
  else if (cmd == "STEPS")   animateSteps();
  else if (cmd == "GLASS")   animateShatter();
  else if (cmd == "UNKNOWN") animateUnknown();
  else if (cmd == "IDLE")    matrix.clear();
  // anything else: ignore
}

void flushSerial() {
  // Drop lines that queued up while a (blocking) animation played so we
  // don't replay stale events after the fact.
  while (Serial.available()) Serial.read();
}

void setup() {
  Serial.begin(115200);
  matrix.begin();
  matrix.setGrayscaleBits(1);

  // "ready" blink
  matrix.draw(danger_sign); delay(150);
  matrix.clear();
}

void loop() {
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    if (cmd.length() > 0) {
      handleEvent(cmd);
      flushSerial();
    }
  }
}
