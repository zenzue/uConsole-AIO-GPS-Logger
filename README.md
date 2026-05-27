# uConsole AIO GPS Logger

**Author:** Aung Myat Thu

A Python GPS logging script for **ClockworkPi uConsole CM4** with **HackerGadgets AIO / AIO V2 GPS** support.  
The script reads NMEA GPS data from a serial GPS module, parses location and fix information, displays a live terminal status dashboard, and exports GPS logs in multiple formats.

---

## Overview

This tool is designed for GPS testing, field logging, hardware validation, and authorized research on a uConsole device. It can capture raw GPS NMEA sentences, convert latitude and longitude into decimal format, evaluate basic GPS signal quality, and generate files that can be analyzed later.

The script supports:

- Raw NMEA capture
- Parsed GPS point logging
- KML track generation for Google Earth
- JSON summary reporting
- GPS power control on AIO V2 through GPIO 27
- Basic GPS reliability risk scoring

---

## Features

- Auto-detects common uConsole GPS serial ports
- Reads GPS data from a serial interface
- Parses common NMEA sentence types:
  - `GGA`
  - `RMC`
  - `VTG`
  - `GSA`
  - `GSV`
- Converts NMEA latitude and longitude into decimal coordinates
- Validates NMEA checksum values
- Tracks GPS fix status, satellites, HDOP, speed, altitude, and course
- Generates a live terminal dashboard
- Saves output as:
  - `.nmea`
  - `.csv`
  - `.kml`
  - `.json`
- Supports optional GPIO-based GPS power control
- Includes optional Bluetooth package detection

---

## Supported Hardware

Recommended hardware:

- ClockworkPi uConsole CM4
- HackerGadgets AIO / AIO V2 board
- GPS module connected through serial
- GPS antenna with clear sky access

Default serial ports checked by the script:

```text
/dev/ttyS0
/dev/ttyAMA0
```

If neither exists, the script falls back to:

```text
/dev/ttyS0
```

---

## Requirements

### System Packages

Install the required Python serial package:

```bash
sudo apt update
sudo apt install python3-serial
```

For GPIO GPS power control:

```bash
sudo apt install python3-libgpiod
```

For optional Bluetooth support:

```bash
sudo apt install python3-bluez
```

### Python Version

Python 3.10 or newer is recommended because the script uses modern type syntax such as:

```python
float | None
```

---

## Installation

Create a working directory:

```bash
mkdir -p ~/script/gps
cd ~/script/gps
```

Save the script as:

```bash
gps_logger.py
```

Make it executable:

```bash
chmod +x gps_logger.py
```

---

## Usage

### Run with Auto-Detected GPS Port

```bash
python3 gps_logger.py
```

### Run for a Fixed Duration

Example: capture for 60 seconds.

```bash
python3 gps_logger.py --seconds 60
```

### Use a Specific Serial Port

```bash
python3 gps_logger.py --port /dev/ttyS0
```

or:

```bash
python3 gps_logger.py --port /dev/ttyAMA0
```

### Use a Custom Baud Rate

```bash
python3 gps_logger.py --baud 9600
```

### Save Output to a Custom Folder

```bash
python3 gps_logger.py --out ./my_gps_logs
```

### Full Example

```bash
python3 gps_logger.py --port /dev/ttyS0 --baud 9600 --seconds 300 --out ./uconsole_gps_logs
```

---

## Command-Line Options

| Option | Default | Description |
|---|---:|---|
| `--port` | `auto` | Serial GPS port. Use `auto`, `/dev/ttyS0`, `/dev/ttyAMA0`, or another valid serial device. |
| `--baud` | `9600` | GPS serial baud rate. |
| `--out` | `./uconsole_gps_logs` | Directory where output files will be saved. |
| `--seconds` | `0` | Capture duration in seconds. `0` means run until manually stopped. |
| `--enable-bt` | disabled | Enables the Bluetooth option flag. Bluetooth scanning is not fully implemented in the current script. |

---

## Output Files

The script creates timestamped output files in the selected output directory.

Example output:

```text
uconsole_gps_logs/
├── gps_raw_20260527_155351.nmea
├── gps_points_20260527_155351.csv
├── gps_track_20260527_155351.kml
└── gps_summary_20260527_155351.json
```

---

## Output File Details

### Raw NMEA File

```text
gps_raw_YYYYMMDD_HHMMSS.nmea
```

Stores raw GPS sentences exactly as received from the serial GPS module.

Example NMEA sentence:

```text
$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47
```

---

### CSV GPS Points

```text
gps_points_YYYYMMDD_HHMMSS.csv
```

CSV fields:

| Field | Description |
|---|---|
| `timestamp_utc` | Host system UTC timestamp |
| `status` | GPS status such as `ACTIVE`, `NO_FIX`, or `UNKNOWN` |
| `risk` | GPS quality risk level |
| `fix_quality` | GPS fix quality from NMEA |
| `latitude` | Decimal latitude |
| `longitude` | Decimal longitude |
| `altitude_m` | Altitude in meters |
| `satellites_used` | Number of satellites used for GPS fix |
| `hdop` | Horizontal dilution of precision |
| `speed_kmh` | Speed in kilometers per hour |
| `raw_sentence` | Original NMEA sentence |

---

### KML Track

```text
gps_track_YYYYMMDD_HHMMSS.kml
```

The KML file can be opened with:

- Google Earth
- QGIS
- GPS visualizer tools
- Other KML-compatible mapping software

The KML file contains a line track using recorded GPS coordinates.

---

### JSON Summary

```text
gps_summary_YYYYMMDD_HHMMSS.json
```

The summary file contains:

- Hardware name
- Serial port
- Capture duration
- Total number of NMEA sentences
- Number of bad checksums
- Final parsed GPS state

Example structure:

```json
{
  "hardware": "uConsole CM4 + HackerGadgets AIO",
  "port": "/dev/ttyS0",
  "duration_seconds": 300.0,
  "total_sentences": 1200,
  "bad_checksum": 0,
  "final_state": {}
}
```

---

## Live Dashboard

During capture, the script prints a live status line in the terminal.

Example:

```text
[15s] Status=ACTIVE Risk=LOW Sats=8/12 HDOP=1.2 Lat=13.756331 Lon=100.501762
```

Dashboard fields:

| Field | Meaning |
|---|---|
| Time | Elapsed capture time |
| Status | GPS fix status |
| Risk | Basic GPS quality rating |
| Sats | Satellites used / satellites in view |
| HDOP | Horizontal accuracy quality indicator |
| Lat | Current latitude |
| Lon | Current longitude |

---

## GPS Risk Level

The script calculates a simple GPS reliability risk level.

| Risk Level | Condition |
|---|---|
| `HIGH` | No fix, unknown status, fewer than 4 satellites, or HDOP greater than 10 |
| `MEDIUM` | Fewer than 6 satellites or HDOP greater than 5 |
| `LOW` | GPS fix appears stable with acceptable satellite count and HDOP |

This risk value is intended for quick testing and field diagnostics. It should not be treated as a scientific accuracy score.

---

## GPS Power Control

If `gpiod` is installed, the script tries to enable GPS power using GPIO 27:

```python
line = chip.get_line(27)
line.set_value(1)
```

If GPIO control fails, the script continues running and prints a warning.

Example:

```text
[WARN] Could not control GPS power: ...
```

If `gpiod` is not installed:

```text
[INFO] gpiod not available - skipping GPIO power control
```

---

## Troubleshooting

### 1. Serial Package Missing

Error:

```text
[ERROR] Install: sudo apt install python3-serial
```

Fix:

```bash
sudo apt install python3-serial
```

---

### 2. Permission Denied on Serial Port

Fix by adding your user to the `dialout` group:

```bash
sudo usermod -aG dialout $USER
```

Then log out and log in again.

Check the serial device:

```bash
ls -lah /dev/ttyS0 /dev/ttyAMA0 /dev/ttyUSB* /dev/ttyACM* 2>/dev/null
```

---

### 3. No GPS Fix

Possible fixes:

- Move outside or near a window
- Connect a GPS antenna
- Wait a few minutes for first GPS lock
- Confirm the serial port is correct
- Confirm the baud rate is correct
- Confirm GPS power is enabled
- Check that the AIO board is properly connected

---

### 4. KML File Has No Track

This usually means the GPS did not produce valid latitude and longitude values.

Check the CSV file:

```bash
head gps_points_*.csv
```

Check whether latitude and longitude are empty.

---

### 5. Bad Checksum Count Is High

A high bad checksum count may indicate:

- Noisy serial connection
- Wrong baud rate
- Weak GPS module connection
- Damaged or incomplete NMEA sentences

Try using the standard GPS baud rate:

```bash
python3 gps_logger.py --baud 9600
```

---

## Example Testing Workflow

Start a 2-minute capture:

```bash
python3 gps_logger.py --seconds 120 --out ./test_logs
```

Check generated files:

```bash
ls -lah ./test_logs
```

View CSV data:

```bash
column -s, -t < ./test_logs/gps_points_*.csv | less -S
```

Open the KML track in Google Earth:

```bash
./test_logs/gps_track_YYYYMMDD_HHMMSS.kml
```

---

## Security and Privacy Notice

GPS data can reveal sensitive location information. Handle all generated logs carefully.

Use this script only for:

- Your own device testing
- Authorized GPS research
- Hardware validation
- Educational labs
- Field diagnostics with permission

Do not use this tool to track people, vehicles, or devices without clear authorization.

---

## Known Limitations

- Bluetooth scanning is declared but not fully implemented.
- GSV satellite detail parsing only updates satellite count, not full per-satellite metadata.
- KML output records coordinates only when latitude and longitude are available.
- Risk scoring is basic and should be used only as a quick diagnostic indicator.
- The script assumes common uConsole serial paths and may need manual port selection on other devices.

---

## License

Add your preferred license before publishing.

Example:

```text
MIT License
```

---

## Disclaimer

This project is provided for educational, research, and authorized testing purposes only.  
The author is not responsible for misuse, privacy violations, or unauthorized tracking.
