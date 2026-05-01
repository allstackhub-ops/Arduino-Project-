#define CLK_PIN 11
#define CS_PIN 10
#define DOUT_PIN 12

// Buffer for custom design, starts with the smiley face
byte customPattern[8] = {
  B00111100, B01000010, B10100101, B10000001,
  B10100101, B10011001, B01000010, B00111100
};

// Send a 16-bit command to the MAX7219 (Address + Data)
void sendCommand(byte address, byte data) {
  digitalWrite(CS_PIN, LOW);
  shiftOut(DOUT_PIN, CLK_PIN, MSBFIRST, address);
  shiftOut(DOUT_PIN, CLK_PIN, MSBFIRST, data);
  digitalWrite(CS_PIN, HIGH);
}

void displayPattern(const byte pattern[8]) {
  for (int i = 0; i < 8; i++) {
    sendCommand(i + 1, pattern[i]);
  }
}

void setup() {
  pinMode(CLK_PIN, OUTPUT);
  pinMode(CS_PIN, OUTPUT);
  pinMode(DOUT_PIN, OUTPUT);
  
  digitalWrite(CS_PIN, HIGH);
  digitalWrite(CLK_PIN, LOW);
  digitalWrite(DOUT_PIN, LOW);

  // MAX7219 Initialization
  sendCommand(0x09, 0x00);  // Decode mode: none
  sendCommand(0x0A, 0x08);  // Intensity: 8 (out of 15)
  sendCommand(0x0B, 0x07);  // Scan limit: All 8 rows
  sendCommand(0x0C, 0x01);  // Shutdown register: Normal operation
  sendCommand(0x0F, 0x00);  // Display test off
  
  // Clear display initially
  for (int i = 1; i <= 8; i++) {
    sendCommand(i, 0);
  }
  
  // Display initial pattern
  displayPattern(customPattern);
  
  // Start Serial communication for Python GUI
  Serial.begin(9600);
}

void loop() {
  // Check if Python has sent exactly 8 bytes of new pattern data
  if (Serial.available() >= 8) {
    for (int i = 0; i < 8; i++) {
      customPattern[i] = Serial.read();
    }
    // Update the display ONLY when new data arrives
    displayPattern(customPattern);
  }
}
