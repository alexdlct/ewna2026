#include <Arduino_LED_Matrix.h>

Arduino_LED_Matrix matrix;

const int ROWS = 8;
const int COLS = 13;


// ============================================================
// ORIGINAL LEFT ARROW
// ============================================================

uint8_t arrow_left[104] = {

  0,0,0,1,1,0,0,0,0,0,0,0,0,
  0,0,1,1,0,0,0,0,0,0,0,0,0,
  0,1,1,0,0,0,0,0,0,0,0,0,0,
  1,1,1,1,1,1,1,1,1,1,1,1,1,
  1,1,1,1,1,1,1,1,1,1,1,1,1,
  0,1,1,0,0,0,0,0,0,0,0,0,0,
  0,0,1,1,0,0,0,0,0,0,0,0,0,
  0,0,0,1,1,0,0,0,0,0,0,0,0

};


// ============================================================
// ORIGINAL RIGHT ARROW
// ============================================================

uint8_t arrow_right[104] = {

  0,0,0,0,0,0,0,0,1,1,0,0,0,
  0,0,0,0,0,0,0,0,0,1,1,0,0,
  0,0,0,0,0,0,0,0,0,0,1,1,0,
  1,1,1,1,1,1,1,1,1,1,1,1,1,
  1,1,1,1,1,1,1,1,1,1,1,1,1,
  0,0,0,0,0,0,0,0,0,0,1,1,0,
  0,0,0,0,0,0,0,0,0,1,1,0,0,
  0,0,0,0,0,0,0,0,1,1,0,0,0

};


// Temporary frame
uint8_t frame[104];


// ============================================================
// DRAW LEFT ARROW WITH OFFSET
//
// offset = 0  -> original
// offset = 1  -> moved left 1 pixel
// offset = 2  -> moved left 2 pixels
// ...
// ============================================================

void drawLeftShifted(int offset) {

  // Clear frame
  for (int i = 0; i < 104; i++) {
    frame[i] = 0;
  }


  for (int row = 0; row < ROWS; row++) {

    for (int col = 0; col < COLS; col++) {

      int newCol = col - offset;

      if (newCol >= 0 && newCol < COLS) {

        frame[row * COLS + newCol] =
          arrow_left[row * COLS + col];

      }
    }
  }


  matrix.draw(frame);
}


// ============================================================
// DRAW RIGHT ARROW WITH OFFSET
// ============================================================

void drawRightShifted(int offset) {

  // Clear frame
  for (int i = 0; i < 104; i++) {
    frame[i] = 0;
  }


  for (int row = 0; row < ROWS; row++) {

    for (int col = 0; col < COLS; col++) {

      int newCol = col + offset;

      if (newCol >= 0 && newCol < COLS) {

        frame[row * COLS + newCol] =
          arrow_right[row * COLS + col];

      }
    }
  }


  matrix.draw(frame);
}


// ============================================================
// LEFT ANIMATION
// ============================================================

void animateLeft() {

  // Move 13 pixels left
  for (int offset = 0; offset <= 13; offset++) {

    drawLeftShifted(offset);

    delay(100);
  }


  matrix.clear();

}


// ============================================================
// RIGHT ANIMATION
// ============================================================

void animateRight() {

  // Move 13 pixels right
  for (int offset = 0; offset <= 13; offset++) {

    drawRightShifted(offset);

    delay(100);
  }


  matrix.clear();

}


// ============================================================
// SETUP
// ============================================================

void setup() {

  matrix.begin();

  matrix.setGrayscaleBits(1);

  matrix.clear();

}


// ============================================================
// LOOP
// ============================================================

void loop() {

  // Arrow moves completely LEFT
  animateLeft();

  delay(500);


  // Arrow moves completely RIGHT
  animateRight();

  delay(500);

}
