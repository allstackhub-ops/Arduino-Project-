// =========================================================
// EYE TRACKING MOTOR CONTROLLER
// 
// This Arduino code listens to the Python script over USB.
// - Receives '1' -> Turns Motor ON
// - Receives '0' -> Turns Motor OFF
// =========================================================

// --- Pin Definitions ---
// Assuming you are using an L298N Motor Driver or similar
const int motorPin1 = 9;   // IN1 on L298N
const int motorPin2 = 10;  // IN2 on L298N
const int enablePin = 11;  // ENA on L298N (optional, for speed)

void setup() {
  // Start Serial communication at 9600 baud
  Serial.begin(9600);
  
  // Configure motor pins as outputs
  pinMode(motorPin1, OUTPUT);
  pinMode(motorPin2, OUTPUT);
  pinMode(enablePin, OUTPUT);
  
  // Make sure motor is OFF on startup
  digitalWrite(motorPin1, LOW);
  digitalWrite(motorPin2, LOW);
  
  // Set motor speed to max (if ENA is connected)
  analogWrite(enablePin, 255); 
}

void loop() {
  // Check if Python sent a command
  if (Serial.available() > 0) {
    char command = Serial.read();
    
    if (command == '1') {
      // EYES OPEN -> Turn Motor ON (Spin forward)
      digitalWrite(motorPin1, HIGH);
      digitalWrite(motorPin2, LOW);
      
    } else if (command == '0') {
      // EYES CLOSED / OFFLINE -> Turn Motor OFF
      digitalWrite(motorPin1, LOW);
      digitalWrite(motorPin2, LOW);
    }
  }
}
