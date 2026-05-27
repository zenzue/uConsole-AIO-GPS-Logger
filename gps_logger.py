import argparse
import csv
import json
import math
import os
import select
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

try:
    import serial
except ImportError:
    print("[ERROR] Install: sudo apt install python3-serial")
    sys.exit(1)

# Optional: Bluetooth scanning
try:
    import bluetooth
    BT_AVAILABLE = True
except ImportError:
    BT_AVAILABLE = False

# GPIO for GPS power on AIO V2
try:
    import gpiod
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False


@dataclass
class GPSState:
    host_time_utc: str = ""
    nmea_time: str = ""
    nmea_date: str = ""
    fix_quality: int = 0
    fix_type: int = 0
    status: str = "UNKNOWN"
    latitude: float | None = None
    longitude: float | None = None
    altitude_m: float | None = None
    satellites_used: int = 0
    satellites_in_view: int = 0
    hdop: float | None = None
    vdop: float | None = None
    pdop: float | None = None
    speed_kmh: float | None = None
    course_deg: float | None = None
    geoid_sep_m: float | None = None
    true_course: float | None = None
    last_sentence_type: str = ""
    checksum_ok: bool = True
    satellites: list = None  # Will hold list of dicts from GSV


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def safe_float(v):
    try:
        return float(v) if v not in ("", None) else None
    except:
        return None


def safe_int(v):
    try:
        return int(float(v)) if v not in ("", None) else 0
    except:
        return 0


def validate_nmea_checksum(sentence):
    if not sentence.startswith("$") or "*" not in sentence:
        return False
    body, chk = sentence[1:].split("*", 1)
    calc = 0
    for c in body:
        calc ^= ord(c)
    return f"{calc:02X}" == chk.upper()[:2]


def nmea_latlon_to_decimal(raw, direction, is_lon=False):
    if not raw or not direction:
        return None
    try:
        deg_len = 3 if is_lon else 2
        deg = float(raw[:deg_len])
        minutes = float(raw[deg_len:])
        decimal = deg + minutes / 60.0
        if direction in "SW":
            decimal = -decimal
        return round(decimal, 8)
    except:
        return None


def risk_level(state):
    if state.fix_quality == 0 or state.status in ("NO_FIX", "UNKNOWN"):
        return "HIGH"
    if state.satellites_used < 4 or (state.hdop and state.hdop > 10):
        return "HIGH"
    if state.satellites_used < 6 or (state.hdop and state.hdop > 5):
        return "MEDIUM"
    return "LOW"


def parse_nmea(sentence, state: GPSState):
    sentence = sentence.strip()
    state.checksum_ok = validate_nmea_checksum(sentence)
    if not sentence.startswith("$"):
        return state, None

    body = sentence[1:].split("*", 1)[0]
    parts = body.split(",")
    talker = parts[0]
    stype = talker[-3:]
    state.last_sentence_type = talker
    state.host_time_utc = utc_now()

    if stype == "GGA":
        if len(parts) >= 14:
            state.nmea_time = parts[1]
            state.latitude = nmea_latlon_to_decimal(parts[2], parts[3])
            state.longitude = nmea_latlon_to_decimal(parts[4], parts[5], True)
            state.fix_quality = safe_int(parts[6])
            state.satellites_used = safe_int(parts[7])
            state.hdop = safe_float(parts[8])
            state.altitude_m = safe_float(parts[9])
            state.geoid_sep_m = safe_float(parts[11])

    elif stype == "RMC":
        if len(parts) >= 12:
            state.nmea_time = parts[1]
            state.status = "ACTIVE" if parts[2] == "A" else "NO_FIX"
            state.latitude = nmea_latlon_to_decimal(parts[3], parts[4])
            state.longitude = nmea_latlon_to_decimal(parts[5], parts[6], True)
            speed_knots = safe_float(parts[7])
            state.speed_kmh = round(speed_knots * 1.852, 2) if speed_knots else None
            state.course_deg = safe_float(parts[8])
            state.nmea_date = parts[9]

    elif stype == "VTG":
        if len(parts) >= 9:
            state.speed_kmh = safe_float(parts[7])  # km/h
            state.true_course = safe_float(parts[1])
            if state.true_course:
                state.course_deg = state.true_course

    elif stype == "GSA":
        if len(parts) >= 18:
            state.fix_type = safe_int(parts[2])
            state.pdop = safe_float(parts[15])
            state.hdop = safe_float(parts[16])
            state.vdop = safe_float(parts[17])

    elif stype == "GSV":
        if len(parts) >= 4:
            state.satellites_in_view = safe_int(parts[3])

    return state, None


class GPSCapture:
    def __init__(self, port, baud, out_dir, duration, **kwargs):
        self.port = port
        self.baud = baud
        self.out_dir = Path(out_dir)
        self.duration = duration
        self.stale_seconds = kwargs.get("stale_seconds", 10)
        self.weak_sats = kwargs.get("weak_sats", 4)
        self.poor_hdop = kwargs.get("poor_hdop", 5.0)
        self.enable_bt = kwargs.get("enable_bt", False)
        self.bt_interval = kwargs.get("bt_interval", 45)

        self.state = GPSState()
        self.start_ts = time.time()
        self.last_sentence_ts = None
        self.total_sentences = 0
        self.bad_checksum = 0

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.raw_path = self.out_dir / f"gps_raw_{ts}.nmea"
        self.points_path = self.out_dir / f"gps_points_{ts}.csv"
        self.kml_path = self.out_dir / f"gps_track_{ts}.kml"
        self.summary_path = self.out_dir / f"gps_summary_{ts}.json"

        self.out_dir.mkdir(parents=True, exist_ok=True)

        # Enable GPS power on AIO V2
        self.enable_gps_power()

    def enable_gps_power(self):
        if not GPIO_AVAILABLE:
            print("[INFO] gpiod not available - skipping GPIO power control")
            return
        try:
            chip = gpiod.Chip('gpiochip0')
            line = chip.get_line(27)
            line.request(consumer="uconsole_gps", type=gpiod.LINE_REQ_DIR_OUT)
            line.set_value(1)
            print("[+] GPS power enabled via GPIO 27 (AIO V2)")
        except Exception as e:
            print(f"[WARN] Could not control GPS power: {e}")

    def write_kml_point(self, kml_file):
        if self.state.latitude and self.state.longitude:
            kml_file.write(f"    {self.state.longitude},{self.state.latitude},{self.state.altitude_m or 0}\n")

    def run(self):
        print(f"[+] uConsole AIO GPS Logger")
        print(f"[+] Port: {self.port} @ {self.baud} baud")
        print(f"[+] Outputs: {self.out_dir}\n")

        point_fields = ["timestamp_utc", "status", "risk", "fix_quality", "latitude", "longitude",
                        "altitude_m", "satellites_used", "hdop", "speed_kmh", "raw_sentence"]

        with serial.Serial(self.port, self.baud, timeout=1) as ser, \
             open(self.raw_path, "a") as raw_f, \
             open(self.points_path, "w", newline="") as pts_f, \
             open(self.kml_path, "w") as kml_f:

            # Simple KML header
            kml_f.write("""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
<Document>
  <name>uConsole GPS Track</name>
  <Style id="track">
    <LineStyle><color>ff0000ff</color><width>4</width></LineStyle>
  </Style>
  <Placemark>
    <name>Track</name>
    <styleUrl>#track</styleUrl>
    <LineString>
      <coordinates>\n""")

            writer = csv.DictWriter(pts_f, fieldnames=point_fields)
            writer.writeheader()

            while True:
                if self.duration and time.time() - self.start_ts > self.duration:
                    break

                try:
                    raw = ser.readline().decode(errors="ignore").strip()
                except:
                    time.sleep(0.5)
                    continue

                if raw:
                    self.last_sentence_ts = time.time()
                    self.total_sentences += 1
                    raw_f.write(raw + "\n")

                    if not validate_nmea_checksum(raw):
                        self.bad_checksum += 1

                    self.state, _ = parse_nmea(raw, self.state)

                    row = {
                        "timestamp_utc": self.state.host_time_utc,
                        "status": self.state.status,
                        "risk": risk_level(self.state),
                        "fix_quality": self.state.fix_quality,
                        "latitude": self.state.latitude,
                        "longitude": self.state.longitude,
                        "altitude_m": self.state.altitude_m,
                        "satellites_used": self.state.satellites_used,
                        "hdop": self.state.hdop,
                        "speed_kmh": self.state.speed_kmh,
                        "raw_sentence": raw
                    }
                    writer.writerow(row)
                    self.write_kml_point(kml_f)

                # Dashboard
                elapsed = int(time.time() - self.start_ts)
                print(f"\r[{elapsed}s] Status={self.state.status} Risk={risk_level(self.state)} "
                      f"Sats={self.state.satellites_used}/{self.state.satellites_in_view} "
                      f"HDOP={self.state.hdop} Lat={self.state.latitude} Lon={self.state.longitude} ", end="", flush=True)

        # Finalize KML
        with open(self.kml_path, "a") as kml_f:
            kml_f.write("""      </coordinates>
    </LineString>
  </Placemark>
</Document>
</kml>""")

        # Summary
        summary = {
            "hardware": "uConsole CM4 + HackerGadgets AIO",
            "port": self.port,
            "duration_seconds": round(time.time() - self.start_ts, 1),
            "total_sentences": self.total_sentences,
            "bad_checksum": self.bad_checksum,
            "final_state": asdict(self.state)
        }
        with open(self.summary_path, "w") as f:
            json.dump(summary, f, indent=2)

        print(f"\n\n[+] Done! Files saved to {self.out_dir}")
        print(f"[+] KML ready for Google Earth: {self.kml_path}")


def auto_detect_port():
    # CM4 preference
    if os.path.exists("/dev/ttyS0"):
        return "/dev/ttyS0"
    if os.path.exists("/dev/ttyAMA0"):
        return "/dev/ttyAMA0"
    return "/dev/ttyS0"


def main():
    parser = argparse.ArgumentParser(description="Powerful uConsole + HackerGadgets AIO GPS Logger")
    parser.add_argument("--port", default="auto", help="Serial port")
    parser.add_argument("--baud", type=int, default=9600)
    parser.add_argument("--out", default="./uconsole_gps_logs")
    parser.add_argument("--seconds", type=int, default=0)
    parser.add_argument("--enable-bt", action="store_true", help="Enable BT scanning (use responsibly)")
    args = parser.parse_args()

    port = auto_detect_port() if args.port == "auto" else args.port

    capture = GPSCapture(port=port, baud=args.baud, out_dir=args.out, duration=args.seconds, enable_bt=args.enable_bt)
    try:
        capture.run()
    except KeyboardInterrupt:
        print("\n[+] Stopped by user.")


if __name__ == "__main__":
    main()
