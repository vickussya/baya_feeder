/*
  Rabbit feeder - ESP32 + DS3231 + A4988/DRV8825 + NEMA17
  Libraries: RTClib (Adafruit). WiFi/NTP/Preferences come with the ESP32 core.

  Behaviour
   * feeds at FEED_HOUR/FEED_MIN slots (default 07:00 and 19:00)
   * homes the wheel on the reed switch, then advances N pockets (N = dose / grams-per-pocket)
   * skips a feeding when one already happened in the same hour (power-cycle safe, stored in NVS)
   * anti-jam: if homing fails, or the home pulse arrives at the wrong angle, reverse ~30 deg and retry
   * "Feed now" button (hold 1 s) = extra manual dose, same safety rules
*/
#include <WiFi.h>
#include <Wire.h>
#include <RTClib.h>
#include <Preferences.h>
#include <time.h>

// ---------- user settings ----------
const char* WIFI_SSID = "";            // leave empty to run on the RTC only
const char* WIFI_PASS = "";
const char* TZ_INFO   = "CET-1CEST,M3.5.0,M10.5.0/3";   // POSIX TZ string
const int   N_FEEDS = 2;
const int   FEED_HOUR[N_FEEDS] = {7, 19};
const int   FEED_MIN[N_FEEDS]  = {0, 0};
float DOSE_G[N_FEEDS]   = {20.0, 20.0}; // 10..40 g
float GRAMS_PER_POCKET  = 6.8;          // from README calibration (docs/checks.md computes 6.81 g)
float DOSE_MULTIPLIER   = 1.00;         // per-dose trim found during calibration

// ---------- hardware ----------
const int PIN_STEP = 25, PIN_DIR = 26, PIN_EN = 27;
const int PIN_HOME = 32;                // reed switch to GND (INPUT_PULLUP), LOW = pocket 0 at the top
const int PIN_BTN  = 33;                // feed-now button to GND
const int PIN_LED  = 2;                 // status LED
const int PIN_LOWFOOD = 35;             // sensor output, HIGH = hopper low (optional)
const int PIN_LED_LOW = 4;

const int  N_POCKETS = 6;
const long STEPS_PER_REV = 200L * 16;   // NEMA17, 1.8 deg, 1/16 microstepping
const float STEPS_PER_POCKET = STEPS_PER_REV / (float)N_POCKETS;   // 533.33
const int  STEP_US = 700;               // slow, high torque (pellets crumble: do not rush)
const int  DWELL_MS = 600;              // let the pocket empty over the chute
const int  JAM_BACKOFF_DEG = 30;
const int  JAM_RETRIES = 3;
const int  HOME_TOL_DEG = 15;

RTC_DS3231 rtc;
Preferences prefs;
bool haveRtc = false;
float stepAccum = 0;

// ---------- low level motion ----------
bool homeActive() { return digitalRead(PIN_HOME) == LOW; }

void stepOnce() {
  digitalWrite(PIN_STEP, HIGH); delayMicroseconds(STEP_US);
  digitalWrite(PIN_STEP, LOW);  delayMicroseconds(STEP_US);
}
void moveSteps(long n, bool forward) {
  digitalWrite(PIN_DIR, forward ? HIGH : LOW);
  for (long i = 0; i < n; i++) stepOnce();
}

// Rotate forward until the reed closes. Returns steps travelled, or -1 if not found in 1.2 revolutions.
long seekHome() {
  digitalWrite(PIN_DIR, HIGH);
  if (homeActive()) {                    // already on the magnet: leave it first for a repeatable edge
    moveSteps(STEPS_PER_REV / 12, true);
  }
  long n = 0;
  while (!homeActive()) {
    stepOnce();
    if (++n > STEPS_PER_REV * 12 / 10) return -1;
  }
  return n;
}

bool homeWheel() {
  for (int a = 0; a < JAM_RETRIES; a++) {
    if (seekHome() >= 0) { stepAccum = 0; return true; }
    Serial.println("homing failed -> anti-jam reverse");
    moveSteps(STEPS_PER_REV * JAM_BACKOFF_DEG / 360, false);
    delay(300);
  }
  return false;
}

// advance one pocket (60 deg), keeping the fractional step error
void advancePocket() {
  stepAccum += STEPS_PER_POCKET;
  long n = (long)stepAccum;
  stepAccum -= n;
  moveSteps(n, true);
  delay(DWELL_MS);
}

// ---------- feeding ----------
int pocketsForDose(float grams) {
  int n = (int)lroundf(grams * DOSE_MULTIPLIER / GRAMS_PER_POCKET);
  return constrain(n, 1, N_POCKETS);
}

bool feed(float grams, const char* why) {
  int n = pocketsForDose(grams);
  Serial.printf("FEED (%s): %.0f g -> %d pockets\n", why, grams, n);
  digitalWrite(PIN_EN, LOW);             // enable driver
  bool ok = false;
  for (int attempt = 0; attempt < JAM_RETRIES && !ok; attempt++) {
    if (!homeWheel()) continue;
    for (int i = 0; i < n; i++) advancePocket();
    // verify: finish the revolution back to the magnet; the remaining angle must match (6-n) pockets
    long expected = (long)((N_POCKETS - n) * STEPS_PER_POCKET);
    long tol = STEPS_PER_REV * HOME_TOL_DEG / 360;
    if (n == N_POCKETS) {
      ok = true;                          // full turn ends on the magnet; homing at the next feed re-checks
    } else {
      long seen = seekHome();
      ok = (seen >= 0 && labs(seen - expected) <= tol);
      if (!ok) Serial.printf("jam suspected (expected %ld, saw %ld)\n", expected, seen);
    }
    if (!ok) {
      Serial.printf("reverse %d deg and retry\n", JAM_BACKOFF_DEG);
      moveSteps(STEPS_PER_REV * JAM_BACKOFF_DEG / 360, false);
      delay(500);
    }
  }
  digitalWrite(PIN_EN, HIGH);            // release the motor (no heat, no buzzing near the rabbit)
  return ok;
}

// ---------- time & log ----------
DateTime nowTime() {
  if (haveRtc) return rtc.now();
  time_t t = time(nullptr);
  struct tm tmv; localtime_r(&t, &tmv);
  return DateTime(tmv.tm_year + 1900, tmv.tm_mon + 1, tmv.tm_mday, tmv.tm_hour, tmv.tm_min, tmv.tm_sec);
}

void syncFromNtp() {
  if (!strlen(WIFI_SSID)) return;
  WiFi.mode(WIFI_STA); WiFi.begin(WIFI_SSID, WIFI_PASS);
  for (int i = 0; i < 30 && WiFi.status() != WL_CONNECTED; i++) delay(500);
  if (WiFi.status() == WL_CONNECTED) {
    configTzTime(TZ_INFO, "pool.ntp.org", "time.nist.gov");
    struct tm tmv;
    if (getLocalTime(&tmv, 8000) && haveRtc) {
      rtc.adjust(DateTime(tmv.tm_year + 1900, tmv.tm_mon + 1, tmv.tm_mday, tmv.tm_hour, tmv.tm_min, tmv.tm_sec));
      Serial.println("RTC synced from NTP (local time)");
    }
  }
  WiFi.disconnect(true); WiFi.mode(WIFI_OFF);
}

// the RTC stores LOCAL time, so a "same hour" stamp is local-hours since 1970 (good enough as an id)
uint32_t hourStamp(const DateTime& d) { return d.unixtime() / 3600; }

void logFeed(const char* why, float g, bool ok) {
  DateTime d = nowTime();
  uint8_t idx = prefs.getUChar("idx", 0);
  char key[8]; snprintf(key, sizeof key, "L%02u", idx);
  char buf[64]; snprintf(buf, sizeof buf, "%04d-%02d-%02d %02d:%02d %s %.0fg %s",
                         d.year(), d.month(), d.day(), d.hour(), d.minute(), why, g, ok ? "OK" : "JAM");
  prefs.putString(key, buf);
  prefs.putUChar("idx", (idx + 1) % 50);   // ring buffer of 50 entries
  if (ok) prefs.putUInt("last", hourStamp(d));
  Serial.println(buf);
}

void blink(int n) { for (int i = 0; i < n; i++) { digitalWrite(PIN_LED, HIGH); delay(120); digitalWrite(PIN_LED, LOW); delay(120); } }

void setup() {
  Serial.begin(115200);
  pinMode(PIN_STEP, OUTPUT); pinMode(PIN_DIR, OUTPUT); pinMode(PIN_EN, OUTPUT); digitalWrite(PIN_EN, HIGH);
  pinMode(PIN_HOME, INPUT_PULLUP); pinMode(PIN_BTN, INPUT_PULLUP);
  pinMode(PIN_LED, OUTPUT); pinMode(PIN_LED_LOW, OUTPUT); pinMode(PIN_LOWFOOD, INPUT);
  prefs.begin("feeder", false);
  Wire.begin(21, 22);
  haveRtc = rtc.begin();
  if (haveRtc && rtc.lostPower()) rtc.adjust(DateTime(F(__DATE__), F(__TIME__)));
  setenv("TZ", TZ_INFO, 1); tzset();
  syncFromNtp();
  Serial.printf("clock: %s\n", nowTime().timestamp().c_str());
  blink(2);
}

void loop() {
  DateTime d = nowTime();
  // scheduled feedings (window = the first 2 minutes of the slot)
  for (int i = 0; i < N_FEEDS; i++) {
    if (d.hour() == FEED_HOUR[i] && d.minute() >= FEED_MIN[i] && d.minute() < FEED_MIN[i] + 2) {
      if (hourStamp(d) == prefs.getUInt("last", 0)) continue;      // already fed this hour: skip
      bool ok = feed(DOSE_G[i], "sched");
      logFeed("sched", DOSE_G[i], ok);
      if (!ok) blink(10);
    }
  }
  // manual feed: hold the button for 1 s
  if (digitalRead(PIN_BTN) == LOW) {
    unsigned long t0 = millis();
    while (digitalRead(PIN_BTN) == LOW && millis() - t0 < 1000) delay(10);
    if (millis() - t0 >= 1000) {
      bool ok = feed(DOSE_G[0], "manual");
      logFeed("manual", DOSE_G[0], ok);
      while (digitalRead(PIN_BTN) == LOW) delay(10);
    }
  }
  digitalWrite(PIN_LED_LOW, digitalRead(PIN_LOWFOOD) ? HIGH : LOW);   // low-food indicator
  digitalWrite(PIN_LED, (millis() / 1000) % 10 == 0);                // heartbeat blip every 10 s
  delay(50);
}
