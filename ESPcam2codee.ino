#include "esp_camera.h"
#include <WiFi.h>
#include <WebServer.h>

// =========================
// Wi-Fi
// =========================
const char* ssid = "REDMI Note 15 5G";
const char* password = "123321123";

// =========================
// Flash LED
// =========================
#define FLASH_LED_PIN 4

// =========================
// AI Thinker ESP32-CAM pins
// =========================
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27

#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

WebServer server(80);

// =========================
// Capture image with FLASH
// =========================
void handleCapture() {

  Serial.println("Preparing camera...");

  // Turn flash ON
  digitalWrite(FLASH_LED_PIN, HIGH);

  // Small delay so illumination stabilizes
  delay(00);

  camera_fb_t *fb = esp_camera_fb_get();

  // Turn flash OFF immediately
  digitalWrite(FLASH_LED_PIN, LOW);

  if (!fb) {

    Serial.println("ERROR: Camera capture failed");

    server.send(
      500,
      "text/plain",
      "Camera capture failed"
    );

    return;
  }

  Serial.print("SUCCESS - Frame captured! Size: ");
  Serial.print(fb->len);
  Serial.println(" bytes");

  server.sendHeader(
    "Content-Disposition",
    "inline; filename=leaf_capture.jpg"
  );

  server.send_P(
    200,
    "image/jpeg",
    (const char *)fb->buf,
    fb->len
  );

  esp_camera_fb_return(fb);
}

// =========================
// Home page
// =========================
void handleRoot() {

  String html = "";

  html += "<html>";
  html += "<head>";
  html += "<title>Plant Disease Detection</title>";
  html += "</head>";

  html += "<body>";
  html += "<h1>ESP32-CAM Plant Disease Detection</h1>";

  html += "<p>Flash: ON during capture</p>";

  html += "<p>";
  html += "<a href='/capture'>";
  html += "<button style='font-size:25px;padding:15px'>";
  html += "CAPTURE LEAF";
  html += "</button>";
  html += "</a>";
  html += "</p>";

  html += "</body>";
  html += "</html>";

  server.send(200, "text/html", html);
}

// =========================
// Setup
// =========================
void setup() {

  Serial.begin(115200);
  delay(1000);

  Serial.println();
  Serial.println("==============================");
  Serial.println("PLANT DISEASE CAMERA SYSTEM");
  Serial.println("==============================");

  // Flash setup
  pinMode(FLASH_LED_PIN, OUTPUT);
  digitalWrite(FLASH_LED_PIN, LOW);

  // =========================
  // Camera configuration
  // =========================

  camera_config_t config;

  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;

  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;

  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;

  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;

  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;

  config.xclk_freq_hz = 20000000;

  config.pixel_format = PIXFORMAT_JPEG;

  // VGA gives a good balance for our laptop YOLO pipeline
  config.frame_size = FRAMESIZE_VGA;

  config.jpeg_quality = 12;

  config.fb_count = 1;

  // =========================
  // Camera initialization
  // =========================

  esp_err_t err = esp_camera_init(&config);

  if (err != ESP_OK) {

    Serial.print("Camera initialization failed: 0x");
    Serial.println(err, HEX);

    return;
  }

  Serial.println("Camera initialized successfully!");

  // =========================
  // Wi-Fi
  // =========================

  WiFi.begin(ssid, password);

  Serial.println("Connecting to Wi-Fi...");

  while (WiFi.status() != WL_CONNECTED) {

    delay(500);
    Serial.print(".");
  }

  Serial.println();
  Serial.println("Wi-Fi connected!");

  Serial.print("ESP32-CAM IP address: ");
  Serial.println(WiFi.localIP());

  // =========================
  // Web server
  // =========================

  server.on("/", handleRoot);

  server.on("/capture", HTTP_GET, handleCapture);

  server.begin();

  Serial.println("Web server started!");

  Serial.println("==============================");
  Serial.println("READY FOR LEAF CAPTURE");
  Serial.println("==============================");
}

// =========================
// Loop
// =========================
void loop() {

  server.handleClient();

}