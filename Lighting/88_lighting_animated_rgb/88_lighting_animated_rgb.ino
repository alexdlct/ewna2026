#include <Adafruit_NeoPixel.h>

// ============================================================
// ADAFRUIT 8x8 NEOPIXEL MATRIX
// ============================================================

#define LED_PIN     6
#define ROWS        8
#define COLS        8
#define NUM_PIXELS  64

// If colors look wrong, try NEO_RGB instead of NEO_GRB.
Adafruit_NeoPixel matrix(
  NUM_PIXELS,
  LED_PIN,
  NEO_GRB + NEO_KHZ800
);


// ============================================================
// BRIGHTNESS
// ============================================================

// 0 - 255
// Start low. 64 NeoPixels can draw significant current.
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


// DANGER
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


// SHATTER 1
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


// SHATTER 2
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


// SHATTER 3
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
// ============================================================
//
// Many Adafruit 8x8 NeoPixel matrices use a zig-zag/serpentine
// physical layout.
//
// row 0:  0  1  2  3  4  5  6  7
// row 1: 15 14 13 12 11 10  9  8
// row 2: 16 17 18 19 20 21 22 23
//
// If your matrix displays strangely, this is the first
// function to check.
//

int XY(int x, int y) {

  if (y % 2 == 0) {
    return y * 8 + x;
  }
  else {
    return y * 8 + (7 - x);
  }
}


// ============================================================
// BASIC DRAW FUNCTIONS
// ============================================================

void clearMatrix() {

  matrix.clear();
  matrix.show();
}


void drawPattern(const uint8_t pattern[], uint32_t color) {

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


// ============================================================
// SHIFTED PATTERN
// ============================================================

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
// VOICE
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
// DANGER
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
// LIGHTNING
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
// SHATTER
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
// SKULL
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
// CO
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
// SOS
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
// LOUD - RGB FLASH
// ============================================================

void fillMatrix(uint32_t color) {

  for (int i = 0; i < NUM_PIXELS; i++) {

    matrix.setPixelColor(
      i,
      color
    );
  }

  matrix.show();
}


void animateLoud() {

  // RED
  fillMatrix(RED);
  delay(150);

  // YELLOW
  fillMatrix(YELLOW);
  delay(150);

  // GREEN
  fillMatrix(GREEN);
  delay(150);

  // CYAN
  fillMatrix(CYAN);
  delay(150);

  // BLUE
  fillMatrix(BLUE);
  delay(150);

  // PURPLE
  fillMatrix(PURPLE);
  delay(150);

  // WHITE
  fillMatrix(WHITE);
  delay(200);

  // Repeat
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
// COMMAND HANDLER
// ============================================================

void handleCommand(String command) {

  command.trim();
  command.toLowerCase();


  if (command == "left") {

    Serial.println("LEFT");

    animateLeft();
  }


  else if (command == "right") {

    Serial.println("RIGHT");

    animateRight();
  }


  else if (command == "voice") {

    Serial.println("VOICE");

    animateVoice();
  }


  else if (command == "water") {

    Serial.println("WATER");

    animateWater();
  }


  else if (command == "danger") {

    Serial.println("DANGER");

    animateDanger();
  }


  else if (command == "lightning") {

    Serial.println("LIGHTNING");

    animateLightning();
  }


  else if (command == "shatter") {

    Serial.println("SHATTER");

    animateShatter();
  }


  else if (command == "skull") {

    Serial.println("SKULL");

    animateSkull();
  }


  else if (command == "co") {

    Serial.println("CO");

    animateCO();
  }


  else if (command == "sos") {

    Serial.println("SOS");

    animateSOS();
  }


  else if (command == "clear") {

    Serial.println("CLEAR");

    clearMatrix();
  }


  else if (command == "loud") {

    Serial.println("LOUD");

    animateLoud();
  }


  else {

    Serial.print("Unknown command: ");

    Serial.println(command);
  }
}


// ============================================================
// SETUP
// ============================================================

void setup() {

  Serial.begin(115200);


  // Start NeoPixel matrix
  matrix.begin();

  matrix.setBrightness(
    BRIGHTNESS
  );

  clearMatrix();


  // Define colors
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


  Serial.println();

  Serial.println(
    "================================"
  );

  Serial.println(
    " ADAFRUIT RGB 8x8 MATRIX READY"
  );

  Serial.println(
    "================================"
  );


  Serial.println("Commands:");

  Serial.println("left");
  Serial.println("right");
  Serial.println("voice");
  Serial.println("water");
  Serial.println("danger");
  Serial.println("lightning");
  Serial.println("shatter");
  Serial.println("skull");
  Serial.println("co");
  Serial.println("sos");
  Serial.println("clear");
  Serial.println("loud");

  Serial.println();
}


// ============================================================
// LOOP
// ============================================================

void loop() {

  if (Serial.available() > 0) {

    String command =
      Serial.readStringUntil('\n');

    handleCommand(command);
  }
}