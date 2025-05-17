Class Attendance System with RFID, ESP32, Ultrasonic Sensor & OLED

Table of Contents

Project Overview:-

-Components Required

1.Circuit Diagram

2.Installation & Setup

3.Code Explanation

Future Improvements

License

🔍 Project Overview
This project automates class attendance using:
✅ RFID (RC522) – Scan student ID cards
✅ ESP32 – Process data & Wi-Fi connectivity
✅ Ultrasonic Sensor (HC-SR04) – Detect student presence
✅ OLED Display (1.8-inch) – Show attendance status
✅ Buzzer – Audio feedback

Data can be stored in Google Sheets for remote access.

📋 Components Required
Component	Quantity
ESP32	1
RFID-RC522 Module	1
Ultrasonic Sensor (HC-SR04)	1
1.8-inch OLED Display (I2C)	1
Buzzer	1
Breadboard & Jumper Wires	As needed
Micro-USB Cable	1
🔌 Circuit Diagram
Circuit Diagram (Replace with actual diagram)

Wiring Summary
ESP32 Pin	Connected To
3.3V	RFID VCC, OLED VCC
GND	RFID GND, Ultrasonic GND, OLED GND
GPIO5	RFID SDA
GPIO18	RFID SCK
GPIO23	RFID MOSI
GPIO19	RFID MISO
GPIO12	Ultrasonic Trig
GPIO14	Ultrasonic Echo
GPIO21	OLED SDA
GPIO22	OLED SCL
GPIO13	Buzzer (+)
(Note: Use a voltage divider (5V→3.3V) if using 5V components.)

⚙️ Installation & Setup
1. Install Required Libraries
bash
# For Arduino IDE
1. MFRC522 (RFID) → `Tools > Manage Libraries > Search "MFRC522"`
2. Adafruit SSD1306 (OLED) → `Search "Adafruit SSD1306"`
3. Ultrasonic HC-SR04 → `Search "Ultrasonic"`
4. ESP32 Board Support → `File > Preferences > Add URL: https://dl.espressif.com/dl/package_esp32_index.json`
2. Upload Code
Open attendance_system.ino in Arduino IDE.

Select ESP32 Dev Module in Tools > Board.

Set correct COM Port and upload.

3. Register RFID Cards
Scan your RFID cards and note their UIDs.

Update registeredUIDs[] in the code.

💻 Code Explanation
Key Functions
setup() → Initializes RFID, OLED, Ultrasonic.

loop() → Checks for RFID scans & ultrasonic distance.

sendToGoogleSheets() → (Optional) Logs data via Wi-Fi.

(See full comments in code.)

☁️ Google Sheets Integration (Optional)
Steps
Create a Google Sheet and enable Google Apps Script.

Deploy as a Web App (GET/POST enabled).

Update ESP32 code with:

Wi-Fi SSID & Password

Google Script URL

Data will auto-sync when a student scans their card.

(See google_sheets_integration.ino for full code.)


📌 How it works:

Student taps RFID card.

Ultrasonic confirms presence.

OLED shows "Attendance Marked!"

Data logs to Google Sheets (if enabled).

🚀 Future Improvements
Face Recognition (ESP32-CAM)

Mobile App (BLE/Blynk)

Voice Feedback (DFPlayer Mini)

Low Power Mode (Battery-operated)

📜 License
MIT License - Free for personal and educational use.

Adafruit SSD1306

(Replace yourusername with your GitHub handle.)

Would you like me to add a FAQ section or troubleshooting guide? 😊

New chat
