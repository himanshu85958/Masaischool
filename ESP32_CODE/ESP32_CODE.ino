#include <SPI.h>
#include <MFRC522.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <Adafruit_GFX.h>
#include <Adafruit_ST7735.h>
#include <ArduinoJson.h>

// Pins Configuration
#define RST_PIN         22
#define SS_PIN          21
#define TFT_CS          5
#define TFT_DC          2
#define TFT_RST         4
#define GREEN_LED       33
#define RED_LED         32

// Network Configuration
const char* ssid = "Esp32";
const char* password = "harse123";
const char* serverBaseUrl = "http://127.0.0.1:5000";
const char* attendanceEndpoint = "/api/attendance";
const char* registerEndpoint = "/register_rfid";
const char* studentInfoEndpoint = "/api/student_info";

// Display Setup
Adafruit_ST7735 tft = Adafruit_ST7735(TFT_CS, TFT_DC, TFT_RST);
MFRC522 rfid(SS_PIN, RST_PIN);

// System Variables
String currentStudentName = "";
unsigned long lastCardReadTime = 0;
const unsigned long cardReadInterval = 2000;

void setup() {
  Serial.begin(115200);

  pinMode(GREEN_LED, OUTPUT);
  pinMode(RED_LED, OUTPUT);

  tft.initR(INITR_BLACKTAB);
  tft.setRotation(1);
  tft.fillScreen(ST77XX_BLACK);

  SPI.begin();
  rfid.PCD_Init();

  connectToWiFi();
  showHomeScreen();
}

void loop() {
  handleNormalOperation();
  delay(100);
}

void handleNormalOperation() {
  if (rfid.PICC_IsNewCardPresent() && rfid.PICC_ReadCardSerial()) {
    if (millis() - lastCardReadTime < cardReadInterval) {
      rfid.PICC_HaltA();
      return;
    }
    lastCardReadTime = millis();

    String uid = getRfidUid();
    Serial.println("UID:" + uid);

    currentStudentName = getStudentNameFromServer(uid);

    tft.fillScreen(ST77XX_BLACK);
    tft.setTextColor(ST77XX_WHITE);
    tft.setTextSize(1);
    tft.setCursor(10, 30);

    if (currentStudentName != "") {
      tft.print("Hello, " + currentStudentName);
    } else {
      tft.print("Processing...");
    }

    if (sendAttendance(uid)) {
      showSuccess("Attendance Recorded");
      digitalWrite(GREEN_LED, HIGH);
      delay(100);
      digitalWrite(GREEN_LED, LOW);
    } else {
      showError(currentStudentName != "" ? "Server Error" : "Not Registered");
      digitalWrite(RED_LED, HIGH);
      delay(100);
      digitalWrite(RED_LED, LOW);
    }

    rfid.PICC_HaltA();
    delay(2000);
    showHomeScreen();
  }
}

String getRfidUid() {
  String uid = "";
  for (byte i = 0; i < rfid.uid.size; i++) {
    if (rfid.uid.uidByte[i] < 0x10) uid += "0";
    uid += String(rfid.uid.uidByte[i], HEX);
  }
  uid.toUpperCase();
  return uid;
}

String getStudentNameFromServer(String uid) {
  if (WiFi.status() != WL_CONNECTED) {
    connectToWiFi();
    if (WiFi.status() != WL_CONNECTED) return "";
  }

  HTTPClient http;
  String url = String(serverBaseUrl) + String(studentInfoEndpoint) + "?uid=" + uid;
  http.begin(url);

  int httpCode = http.GET();
  String name = "";

  if (httpCode == HTTP_CODE_OK) {
    String payload = http.getString();
    DynamicJsonDocument doc(256);
    deserializeJson(doc, payload);
    name = doc["name"].as<String>();
  }

  http.end();
  return name;
}

bool sendAttendance(String uid) {
  if (WiFi.status() != WL_CONNECTED) {
    connectToWiFi();
    if (WiFi.status() != WL_CONNECTED) return false;
  }

  HTTPClient http;
  String url = String(serverBaseUrl) + String(attendanceEndpoint);
  http.begin(url);
  http.addHeader("Content-Type", "application/json");

  DynamicJsonDocument doc(128);
  doc["uid"] = uid;
  if (currentStudentName != "") {
    doc["name"] = currentStudentName;
  }

  String payload;
  serializeJson(doc, payload);

  int httpCode = http.POST(payload);
  http.end();

  return (httpCode == HTTP_CODE_OK);
}

void connectToWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;

  tft.fillScreen(ST77XX_BLACK);
  tft.setTextColor(ST77XX_WHITE);
  tft.setTextSize(1);
  tft.setCursor(10, 30);
  tft.print("Connecting to WiFi...");

  WiFi.begin(ssid, password);
  int attempts = 0;

  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    tft.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    tft.setCursor(10, 50);
    tft.print("Connected!");
    tft.setCursor(10, 70);
    tft.print("IP: " + WiFi.localIP().toString());
    delay(1000);
  } else {
    tft.setCursor(10, 50);
    tft.print("Connection Failed");
    delay(2000);
  }
}

void showHomeScreen() {
  tft.fillScreen(ST77XX_BLACK);
  tft.setTextColor(ST77XX_WHITE);
  tft.setTextSize(2);
  tft.setCursor(10, 30);
  tft.print("Attendance");
  tft.setCursor(10, 60);
  tft.print("System");

  tft.setTextSize(1);
  tft.setCursor(10, 90);
  tft.print("Scan RFID to begin");

  if (WiFi.status() == WL_CONNECTED) {
    tft.setCursor(10, 110);
    tft.print("IP: " + WiFi.localIP().toString());
  } else {
    tft.setCursor(10, 110);
    tft.print("WiFi Disconnected");
  }
}

void showSuccess(String message) {
  tft.fillScreen(ST77XX_GREEN);
  tft.setTextColor(ST77XX_WHITE);
  tft.setTextSize(1);
  tft.setCursor(10, 30);
  tft.print("SUCCESS");
  tft.setTextSize(2);
  tft.setCursor(10, 60);
  tft.print(message);

  if (currentStudentName != "") {
    tft.setTextSize(1);
    tft.setCursor(10, 90);
    tft.print(currentStudentName);
  }
}

void showError(String message) {
  tft.fillScreen(ST77XX_RED);
  tft.setTextColor(ST77XX_WHITE);
  tft.setTextSize(1);
  tft.setCursor(10, 30);
  tft.print("ERROR");
  tft.setTextSize(2);
  tft.setCursor(10, 60);
  tft.print(message);
}