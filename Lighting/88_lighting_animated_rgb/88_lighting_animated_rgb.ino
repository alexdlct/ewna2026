#include <Adafruit_NeoPixel.h>
#include <Arduino_RouterBridge.h>

// ============================================================
// SOUND GUARDIAN
// Arduino UNO Q + Adafruit 8x8 RGB NeoPixel Matrix
//
// App Lab sends:
//
// Bridge.notify("sound_event", "GLASS")
//
// Router Bridge:
// App Lab -> MCU -> RGB Matrix
// ============================================================


// ============================================================
// MATRIX CONFIGURATION
// ============================================================

#define LED_PIN     6
#define ROWS        8
#define COLS        8
#define NUM_PIXELS  64

Adafruit_NeoPixel matrix(
  NUM_PIXELS,
  LED_PIN,
  NEO_GRB + NEO_KHZ800
);

const uint8_t BRIGHTNESS = 40;


// ============================================================
// COLORS
// ============================================================

uint32_t RED;
uint32_t GREEN;
uint32_t BLUE;
uint32_t CYAN;
uint32_t YELLOW;
uint32_t ORANGE;
uint32_t PURPLE;
uint32_t PINK;
uint32_t WHITE;


// ============================================================
// 8x8 PATTERNS
// ============================================================

// ============================================================
// BATMAN SYMBOL
// ============================================================

const uint8_t bat_symbol[64] = {
  1,0,0,0,0,0,0,1,
  1,1,0,0,0,0,1,1,
  1,1,1,0,0,1,1,1,
  0,1,1,1,1,1,1,0,
  0,1,1,1,1,1,1,0,
  0,0,1,1,1,1,0,0,
  0,0,1,0,0,1,0,0,
  0,0,0,1,1,0,0,0
};

// ============================================================
// QUESTION MARK
// ============================================================

const uint8_t question_mark[64] = {
  0,1,1,1,1,1,0,0,
  1,1,0,0,0,1,1,0,
  0,0,0,0,0,1,1,0,
  0,0,0,0,1,1,0,0,
  0,0,0,1,1,0,0,0,
  0,0,0,1,0,0,0,0,
  0,0,0,0,0,0,0,0,
  0,0,0,1,0,0,0,0
};

// LEFT ARROW
const uint8_t arrow_left[64] = {
  0,0,0,1,0,0,0,0,
  0,0,1,1,0,0,0,0,
  0,1,1,0,0,0,0,0,
  1,1,1,1,1,1,1,1,
  1,1,1,1,1,1,1,1,
  0,1,1,0,0,0,0,0,
  0,0,1,1,0,0,0,0,
  0,0,0,1,0,0,0,0
};


// RIGHT ARROW
const uint8_t arrow_right[64] = {
  0,0,0,0,1,0,0,0,
  0,0,0,0,1,1,0,0,
  0,0,0,0,0,1,1,0,
  1,1,1,1,1,1,1,1,
  1,1,1,1,1,1,1,1,
  0,0,0,0,0,1,1,0,
  0,0,0,0,1,1,0,0,
  0,0,0,0,1,0,0,0
};


// VOICE FRAME 1
const uint8_t voice1[64] = {
  0,0,0,0,0,0,0,0,
  0,0,0,1,0,0,0,0,
  0,0,1,1,0,1,0,0,
  0,1,0,1,0,1,0,0,
  0,1,0,1,0,1,0,0,
  0,0,1,1,0,1,0,0,
  0,0,0,1,0,0,0,0,
  0,0,0,0,0,0,0,0
};


// VOICE FRAME 2
const uint8_t voice2[64] = {
  0,0,1,0,1,0,0,0,
  0,1,1,0,1,0,1,0,
  1,0,1,0,1,0,1,0,
  1,0,1,0,1,0,1,1,
  1,0,1,0,1,0,1,1,
  1,0,1,0,1,0,1,0,
  0,1,1,0,1,0,1,0,
  0,0,1,0,1,0,0,0
};


// WATER FRAME 1
const uint8_t water1[64] = {
  0,0,0,1,0,0,0,0,
  0,0,1,1,1,0,0,0,
  0,0,0,1,0,0,0,0,
  0,0,0,0,0,0,0,0,
  0,0,0,0,0,0,0,0,
  0,0,0,0,0,0,0,0,
  0,0,0,0,0,0,0,0,
  0,0,0,0,0,0,0,0
};


// WATER FRAME 2
const uint8_t water2[64] = {
  0,0,0,0,0,0,0,0,
  0,0,0,0,0,0,0,0,
  0,0,0,1,0,0,0,0,
  0,0,1,1,1,0,0,0,
  0,0,1,1,1,0,0,0,
  0,0,0,1,0,0,0,0,
  0,0,0,0,0,0,0,0,
  0,0,0,0,0,0,0,0
};


// WATER FRAME 3
const uint8_t water3[64] = {
  0,0,0,0,0,0,0,0,
  0,0,0,0,0,0,0,0,
  0,0,0,0,0,0,0,0,
  0,0,0,1,0,0,0,0,
  0,0,1,1,1,0,0,0,
  0,1,1,1,1,1,0,0,
  0,1,1,1,1,1,0,0,
  0,0,1,1,1,0,0,0
};


// DANGER SIGN
const uint8_t danger_sign[64] = {
  0,0,0,1,1,0,0,0,
  0,0,1,0,0,1,0,0,
  0,1,0,1,1,0,1,0,
  0,1,0,1,1,0,1,0,
  1,0,0,1,1,0,0,1,
  1,0,0,0,0,0,0,1,
  1,0,0,1,1,0,0,1,
  1,1,1,1,1,1,1,1
};


// LIGHTNING
const uint8_t lightning_symbol[64] = {
  0,0,0,1,1,1,0,0,
  0,0,1,1,1,0,0,0,
  0,1,1,1,0,0,0,0,
  0,1,1,1,1,1,1,0,
  0,0,0,1,1,1,0,0,
  0,0,1,1,1,0,0,0,
  0,1,1,1,0,0,0,0,
  1,1,0,0,0,0,0,0
};


// SHATTER FRAME 1
const uint8_t shatter1[64] = {
  0,0,0,0,0,0,0,0,
  0,0,0,0,0,0,0,0,
  0,0,0,1,0,0,0,0,
  0,0,1,1,1,0,0,0,
  0,0,1,1,1,0,0,0,
  0,0,0,1,0,0,0,0,
  0,0,0,0,0,0,0,0,
  0,0,0,0,0,0,0,0
};


// SHATTER FRAME 2
const uint8_t shatter2[64] = {
  0,0,0,1,0,0,0,0,
  0,0,0,1,0,0,0,0,
  0,1,0,1,0,1,0,0,
  0,0,1,1,1,0,0,0,
  0,1,1,1,1,1,0,0,
  0,1,0,1,0,1,0,0,
  0,0,0,1,0,0,0,0,
  0,0,0,1,0,0,0,0
};


// SHATTER FRAME 3
const uint8_t shatter3[64] = {
  1,0,0,1,0,0,0,1,
  0,1,0,1,0,0,1,0,
  0,0,1,1,0,1,0,0,
  1,0,1,1,1,0,0,1,
  1,1,1,1,1,1,1,1,
  1,0,1,1,1,0,0,1,
  0,1,0,1,0,1,1,0,
  1,0,0,1,0,0,0,1
};


// SKULL
const uint8_t skull[64] = {
  0,0,1,1,1,1,0,0,
  0,1,1,1,1,1,1,0,
  1,1,0,1,1,0,1,1,
  1,1,0,1,1,0,1,1,
  1,1,1,1,1,1,1,1,
  0,1,1,0,0,1,1,0,
  0,0,1,1,1,1,0,0,
  0,0,1,0,0,1,0,0
};


// CO
const uint8_t CO_symbol[64] = {
  0,1,1,0,0,1,1,0,
  1,0,0,0,1,0,0,1,
  1,0,0,0,1,0,0,1,
  1,0,0,0,1,0,0,1,
  1,0,0,0,1,0,0,1,
  1,0,0,0,1,0,0,1,
  1,0,0,0,1,0,0,1,
  0,1,1,0,0,1,1,0
};


// SOS
const uint8_t SOS_symbol[64] = {
  1,1,0,1,1,0,1,1,
  1,0,0,1,0,1,1,0,
  1,0,0,1,0,1,1,0,
  0,1,0,1,0,1,0,1,
  0,1,0,1,0,1,0,1,
  0,0,1,1,0,1,0,1,
  0,0,1,1,0,1,0,1,
  1,1,0,0,1,0,1,1
};


// ============================================================
// XY -> NEOPIXEL INDEX
// Serpentine/zig-zag Adafruit matrix
// ============================================================

int XY(int x, int y) {

  if (y % 2 == 0) {
    return y * 8 + x;
  }

  return y * 8 + (7 - x);
}


// ============================================================
// BASIC MATRIX FUNCTIONS
// ============================================================

void clearMatrix() {

  matrix.clear();
  matrix.show();
}


void fillMatrix(uint32_t color) {

  for (int i = 0; i < NUM_PIXELS; i++) {
    matrix.setPixelColor(i, color);
  }

  matrix.show();
}


void drawPattern(
  const uint8_t pattern[],
  uint32_t color
) {

  matrix.clear();

  for (int y = 0; y < 8; y++) {

    for (int x = 0; x < 8; x++) {

      int patternIndex = y * 8 + x;

      if (pattern[patternIndex]) {

        matrix.setPixelColor(
          XY(x, y),
          color
        );
      }
    }
  }

  matrix.show();
}


void drawShifted(
  const uint8_t pattern[],
  int shiftX,
  uint32_t color
) {

  matrix.clear();

  for (int y = 0; y < 8; y++) {

    for (int x = 0; x < 8; x++) {

      if (pattern[y * 8 + x]) {

        int newX = x + shiftX;

        if (newX >= 0 && newX < 8) {

          matrix.setPixelColor(
            XY(newX, y),
            color
          );
        }
      }
    }
  }

  matrix.show();
}

// ============================================================
// QUESTION MARK
// ============================================================

void animateQuestionMark() {

  drawPattern(
    question_mark,
    PURPLE
  );

  delay(1500);

  clearMatrix();
}


// ============================================================
// BAT SIGNAL
// ============================================================

void animateBat() {

  // Flash like a signal appearing in the sky
  for (int i = 0; i < 3; i++) {

    drawPattern(
      bat_symbol,
      YELLOW
    );

    delay(400);

    clearMatrix();

    delay(180);
  }

  // Hold final bat symbol
  drawPattern(
    bat_symbol,
    YELLOW
  );

  delay(1200);

  clearMatrix();
}

// ============================================================
// LEFT
// ============================================================

void animateLeft() {

  for (int offset = 0; offset <= 8; offset++) {

    drawShifted(
      arrow_left,
      -offset,
      GREEN
    );

    delay(70);
  }

  clearMatrix();
}


// ============================================================
// RIGHT
// ============================================================

void animateRight() {

  for (int offset = 0; offset <= 8; offset++) {

    drawShifted(
      arrow_right,
      offset,
      BLUE
    );

    delay(70);
  }

  clearMatrix();
}


// ============================================================
// VOICE / SCREAMING
// ============================================================

void animateVoice() {

  for (int i = 0; i < 4; i++) {

    drawPattern(
      voice1,
      PURPLE
    );

    delay(180);

    drawPattern(
      voice2,
      PINK
    );

    delay(180);
  }

  clearMatrix();
}


// ============================================================
// WATER
// ============================================================

void animateWater() {

  drawPattern(
    water1,
    CYAN
  );

  delay(180);

  drawPattern(
    water2,
    BLUE
  );

  delay(180);

  drawPattern(
    water3,
    CYAN
  );

  delay(350);

  clearMatrix();
}


// ============================================================
// DANGER / UNKNOWN
// ============================================================

void animateDanger() {

  for (int i = 0; i < 4; i++) {

    drawPattern(
      danger_sign,
      RED
    );

    delay(200);

    clearMatrix();

    delay(120);
  }
}


// ============================================================
// ELECTRICAL
// ============================================================

void animateLightning() {

  for (int i = 0; i < 4; i++) {

    drawPattern(
      lightning_symbol,
      YELLOW
    );

    delay(70);

    clearMatrix();

    delay(60);
  }

  drawPattern(
    lightning_symbol,
    YELLOW
  );

  delay(300);

  clearMatrix();
}


// ============================================================
// GLASS BREAKING
// ============================================================

void animateShatter() {

  drawPattern(
    shatter1,
    WHITE
  );

  delay(130);

  drawPattern(
    shatter2,
    ORANGE
  );

  delay(130);

  drawPattern(
    shatter3,
    RED
  );

  delay(500);

  clearMatrix();
}


// ============================================================
// FALL / THUD
// ============================================================

void animateSkull() {

  for (int i = 0; i < 3; i++) {

    drawPattern(
      skull,
      RED
    );

    delay(300);

    clearMatrix();

    delay(120);
  }

  drawPattern(
    skull,
    RED
  );

  delay(500);

  clearMatrix();
}


// ============================================================
// CARBON MONOXIDE
// ============================================================

void animateCO() {

  for (int i = 0; i < 4; i++) {

    drawPattern(
      CO_symbol,
      ORANGE
    );

    delay(250);

    clearMatrix();

    delay(150);
  }
}


// ============================================================
// SOS / ALARM
// ============================================================

void animateSOS() {

  for (int i = 0; i < 6; i++) {

    drawPattern(
      SOS_symbol,
      RED
    );

    delay(180);

    clearMatrix();

    delay(120);
  }

  drawPattern(
    SOS_symbol,
    RED
  );

  delay(500);

  clearMatrix();
}


// ============================================================
// LOUD SOUND
// ============================================================

void animateLoud() {

  fillMatrix(RED);
  delay(150);

  fillMatrix(YELLOW);
  delay(150);

  fillMatrix(GREEN);
  delay(150);

  fillMatrix(CYAN);
  delay(150);

  fillMatrix(BLUE);
  delay(150);

  fillMatrix(PURPLE);
  delay(150);

  fillMatrix(WHITE);
  delay(200);

  fillMatrix(RED);
  delay(150);

  fillMatrix(YELLOW);
  delay(150);

  fillMatrix(GREEN);
  delay(150);

  fillMatrix(CYAN);
  delay(150);

  fillMatrix(BLUE);
  delay(150);

  fillMatrix(PURPLE);
  delay(150);

  clearMatrix();
}

// ============================================================
// MORSE CODE SOS
//
// S = ...
// O = ---
// S = ...
//
// dot  = 1 unit
// dash = 3 units
// gap between symbols = 1 unit
// gap between letters = 3 units
// ============================================================

const int MORSE_UNIT = 180;


// ------------------------------------------------------------
// MORSE DOT
// ------------------------------------------------------------

void morseDot() {

  fillMatrix(RED);

  delay(MORSE_UNIT);

  clearMatrix();

  delay(MORSE_UNIT);
}


// ------------------------------------------------------------
// MORSE DASH
// ------------------------------------------------------------

void morseDash() {

  fillMatrix(RED);

  delay(MORSE_UNIT * 3);

  clearMatrix();

  delay(MORSE_UNIT);
}


// ------------------------------------------------------------
// MORSE SOS
// ------------------------------------------------------------

void animateMorseSOS() {

  // --------------------
  // S = ...
  // --------------------

  morseDot();
  morseDot();
  morseDot();


  // We already waited 1 unit after last dot.
  // Add 2 more = 3 units between letters.

  delay(MORSE_UNIT * 2);


  // --------------------
  // O = ---
  // --------------------

  morseDash();
  morseDash();
  morseDash();


  delay(MORSE_UNIT * 2);


  // --------------------
  // S = ...
  // --------------------

  morseDot();
  morseDot();
  morseDot();


  // Final pause

  delay(MORSE_UNIT * 6);

  clearMatrix();
}


// ============================================================
// SOUND GUARDIAN EVENT HANDLER
// ============================================================

void handleEvent(String command) {

  command.trim();
  command.toUpperCase();

  Serial.print("Sound Guardian event: ");
  Serial.println(command);


  // ALARM / SIREN
  if (command == "ALARM") {

    animateSOS();
  }

  // BAT SIGNAL
  else if (
    command == "BAT" ||
    command == "BAT_SIGNAL"
  ) {

    animateBat();
  }


  // MORSE SOS
  else if (
    command == "MORSE" ||
    command == "MORSE_SOS"
  ) {

    animateMorseSOS();
  }


  // SCREAM / VOICE
  else if (
    command == "VOICE" ||
    command == "SCREAM"
  ) {
    animateVoice();
  } 


  // FALL / THUD
  else if (
    command == "FALL" ||
    command == "THUD"
  ) {

    animateSkull();
  }


  // FOOTSTEPS
  else if (command == "STEPS") {

    animateWater();
  }


  // GLASS BREAKING
  else if (
    command == "GLASS" ||
    command == "GLASS_BREAKING"
  ) {

    animateShatter();
  }


  // WATER
  else if (command == "WATER") {

    animateWater();
  }


  // CARBON MONOXIDE
  else if (
    command == "CO" ||
    command == "CARBON_MONOXIDE"
  ) {

    animateCO();
  }


  // ELECTRICAL BUZZING / SPARKING
  else if (
    command == "ELECTRICAL" ||
    command == "SPARKING"
  ) {

    animateLightning();
  }


  // GENERIC LOUD EVENT
  else if (
    command == "LOUD" ||
    command == "LOUD_SOUND"
  ) {

    animateLoud();
  }


  // SOS
  else if (command == "SOS") {

    animateSOS();
  }


  // OPTIONAL ARROWS
  else if (command == "LEFT") {

    animateLeft();
  }

  else if (command == "RIGHT") {

    animateRight();
  }


  // CLEAR MATRIX
  else if (
    command == "IDLE" ||
    command == "CLEAR"
  ) {

    clearMatrix();
  }

  // QUESTION MARK
  else if (command == "QUESTION_MARK") {

    animateQuestionMark();
  }


  // UNKNOWN EVENT
  else if (
    command == "UNKNOWN" ||
    command == "DANGER"
  ) {

    animateDanger();
  }


  // ANY UNRECOGNIZED EVENT
  else {

    Serial.print(
      "Unknown Sound Guardian event: "
    );

    Serial.println(command);

    animateDanger();
  }
}


// ============================================================
// ROUTER BRIDGE CALLBACK
// ============================================================
//
// App Lab:
//
// Bridge.notify("sound_event", "GLASS")
//
// becomes:
//
// soundEvent("GLASS")
//
// ============================================================

void soundEvent(String command) {

  Serial.print(
    "Router Bridge received: "
  );

  Serial.println(command);

  handleEvent(command);
}


// ============================================================
// SETUP
// ============================================================

void setup() {

  Serial.begin(115200);


  // ----------------------------------------------------------
  // START RGB MATRIX
  // ----------------------------------------------------------

  matrix.begin();

  matrix.setBrightness(
    BRIGHTNESS
  );


  // ----------------------------------------------------------
  // DEFINE COLORS
  // ----------------------------------------------------------

  RED =
    matrix.Color(255, 0, 0);

  GREEN =
    matrix.Color(0, 255, 0);

  BLUE =
    matrix.Color(0, 0, 255);

  CYAN =
    matrix.Color(0, 255, 255);

  YELLOW =
    matrix.Color(255, 255, 0);

  ORANGE =
    matrix.Color(255, 80, 0);

  PURPLE =
    matrix.Color(150, 0, 255);

  PINK =
    matrix.Color(255, 0, 100);

  WHITE =
    matrix.Color(255, 255, 255);


  clearMatrix();


  // ----------------------------------------------------------
  // START ROUTER BRIDGE
  // ----------------------------------------------------------

  Bridge.begin();

  Bridge.provide_safe(
    "sound_event",
    soundEvent
  );


  // ----------------------------------------------------------
  // DEBUG OUTPUT
  // ----------------------------------------------------------

  Serial.println();

  Serial.println(
    "================================"
  );

  Serial.println(
    " SOUND GUARDIAN"
  );

  Serial.println(
    "================================"
  );

  Serial.println(
    "8x8 RGB Matrix: READY"
  );

  Serial.println(
    "Router Bridge: READY"
  );

  Serial.println();


  // ----------------------------------------------------------
  // STARTUP INDICATOR
  // ----------------------------------------------------------

  fillMatrix(GREEN);
  delay(250);

  clearMatrix();
}


// ============================================================
// LOOP
// ============================================================

void loop() {

  // Nothing required here.
  //
  // App Lab sends events using Router Bridge:
  //
  // Bridge.notify("sound_event", "GLASS")
  //
  //              ↓
  //
  // soundEvent("GLASS")
  //
  //              ↓
  //
  // handleEvent("GLASS")
  //
  //              ↓
  //
  // animateShatter()
}