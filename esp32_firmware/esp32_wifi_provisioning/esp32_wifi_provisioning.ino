/**
 * ESP32 WiFi 配网固件 (智能采样机械臂 WiFi 模块)
 *
 * 功能:
 *  1. 首次上电/无已存配置时, 进入 SoftAP 配网模式:
 *     - 热点名:  SmartArm-XXXX (XXXX 为芯片ID后4位)
 *     - 打开浏览器访问 192.168.4.1 打开配网页填写 WiFi 密码
 *  2. 配置保存到 NVS (Preferences), 重启自动连接 (STA 模式)
 *  3. 串口上报连接状态与 IP, 便于树莓派主控解析
 *  4. 长按 GPIO0 按键 5 秒可清除配置, 重新进入配网模式
 *
 * 部署说明: 见同目录 README.md
 * 平台: ESP32 / ESP32-S2 / ESP32-C3 (Arduino 框架)
 */

#include <WiFi.h>
#include <WebServer.h>
#include <Preferences.h>
#include <DNSServer.h>

// ---------------- 配置项 ----------------
const char *AP_PREFIX = "SmartArm-";
const int   AP_CHANNEL = 6;
const int   CONFIG_BUTTON_PIN = 0;      // BOOT 按键 (GPIO0)
const int   STATUS_LED_PIN = 2;         // 板载 LED (GPIO2)
const char *NVS_NAMESPACE = "smartarm";

// ---------------- 全局对象 ----------------
Preferences prefs;
WebServer server(80);
DNSServer dns;

String savedSSID = "";
String savedPass = "";

// ---------------- 工具函数 ----------------
String getChipId() {
  uint32_t id = (uint32_t)ESP.getEfuseMac();
  char buf[5];
  snprintf(buf, sizeof(buf), "%04X", id & 0xFFFF);
  return String(buf);
}

bool loadConfig() {
  prefs.begin(NVS_NAMESPACE, true);
  savedSSID = prefs.getString("ssid", "");
  savedPass = prefs.getString("pass", "");
  prefs.end();
  return savedSSID.length() > 0;
}

void saveConfig(const String &ssid, const String &pass) {
  prefs.begin(NVS_NAMESPACE, false);
  prefs.putString("ssid", ssid);
  prefs.putString("pass", pass);
  prefs.end();
  Serial.printf("[CONFIG] saved ssid=%s\n", ssid.c_str());
}

void clearConfig() {
  prefs.begin(NVS_NAMESPACE, false);
  prefs.remove("ssid");
  prefs.remove("pass");
  prefs.end();
  Serial.println("[CONFIG] cleared");
}

// ---------------- 配网页 ----------------
void handleProvisionRoot() {
  String html = R"HTML(
<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>智能采样机械臂 WiFi 配网</title>
<style>
body{font-family:sans-serif;max-width:480px;margin:0 auto;padding:20px;background:#f5f7fa}
h1{font-size:20px;color:#1565C0}
input{width:100%;padding:12px;margin:6px 0;box-sizing:border-box;border:1px solid #ccc;border-radius:6px}
button{width:100%;padding:12px;background:#1565C0;color:#fff;border:none;border-radius:6px;font-size:16px}
</style></head><body>
<h1>智能采样机械臂 WiFi 配网</h1>
<form action="/save" method="POST">
  <label>WiFi 名称 (SSID)</label><input name="ssid" required>
  <label>WiFi 密码</label><input type="password" name="pass">
  <button type="submit">保存并连接</button>
</form>
</body></html>
)HTML";
  server.send(200, "text/html; charset=utf-8", html);
}

void handleProvisionSave() {
  String ssid = server.arg("ssid");
  String pass = server.arg("pass");
  ssid.trim();
  if (ssid.length() == 0) {
    server.send(400, "text/plain; charset=utf-8", "SSID 不能为空");
    return;
  }
  saveConfig(ssid, pass);
  server.send(200, "text/html; charset=utf-8",
              "<html><body><h2 style='color:green'>已保存, 正在连接 ...</h2>"
              "<script>setTimeout(function(){window.close();},2000);</script></body></html>");
  delay(500);
  ESP.restart();
}

void startProvisionAP() {
  String apName = String(AP_PREFIX) + getChipId();
  WiFi.mode(WIFI_AP);
  WiFi.softAP(apName.c_str(), NULL, AP_CHANNEL);
  Serial.printf("[PROVISION] SoftAP: %s (192.168.4.1)\n", apName.c_str());

  server.on("/", handleProvisionRoot);
  server.on("/save", HTTP_POST, handleProvisionSave);
  server.begin();

  // DNS 重定向到配网页
  dns.start(53, "*", IPAddress(192, 168, 4, 1));
  Serial.println("[PROVISION] Open http://192.168.4.1 to configure");
}

void blink(int n, int ms) {
  for (int i = 0; i < n; i++) {
    digitalWrite(STATUS_LED_PIN, LOW);
    delay(ms);
    digitalWrite(STATUS_LED_PIN, HIGH);
    delay(ms);
  }
}

bool connectToAP() {
  Serial.printf("[STA] connecting to %s ...\n", savedSSID.c_str());
  WiFi.mode(WIFI_STA);
  WiFi.begin(savedSSID.c_str(), savedPass.c_str());
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED) {
    if (millis() - start > 15000) return false;   // 15s 超时
    delay(300);
    Serial.print(".");
  }
  Serial.println();
  Serial.printf("[STA] connected, IP=%s\n", WiFi.localIP().toString().c_str());
  blink(3, 150);
  return true;
}

void checkConfigButton() {
  if (digitalRead(CONFIG_BUTTON_PIN) == LOW) {
    unsigned long start = millis();
    while (digitalRead(CONFIG_BUTTON_PIN) == LOW) {
      if (millis() - start > 5000) {            // 长按 5s
        Serial.println("[BUTTON] long-press detected, clearing config");
        clearConfig();
        blink(5, 100);
        ESP.restart();
      }
      delay(100);
    }
  }
}

// ---------------- 主流程 ----------------
void setup() {
  Serial.begin(115200);
  pinMode(STATUS_LED_PIN, OUTPUT);
  digitalWrite(STATUS_LED_PIN, HIGH);
  pinMode(CONFIG_BUTTON_PIN, INPUT_PULLUP);

  delay(200);
  Serial.println("\n=== Smart Sampling Arm WiFi Module ===");

  bool hasConfig = loadConfig();
  if (hasConfig && connectToAP()) {
    // 已连接: 通知主控 (树莓派可通过 AT 或串口解析)
    Serial.printf("WIFI CONNECTED\r\nSSID=%s\r\nIP=%s\r\n",
                  savedSSID.c_str(), WiFi.localIP().toString().c_str());
    while (true) {
      checkConfigButton();
      delay(100);
    }
  } else {
    // 无配置或连接失败: 进入配网模式
    if (hasConfig) Serial.println("[STA] connect failed, entering provision mode");
    startProvisionAP();
  }
}

void loop() {
  dns.processNextRequest();
  server.handleClient();
  checkConfigButton();
}
