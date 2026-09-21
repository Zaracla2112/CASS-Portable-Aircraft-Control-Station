def parse_telemetry_line(raw_line):
  line = raw_line.strip()
  if not line:
    return None

  if line.startswith("ACK:"):
    return {"type": "ack", "value": line}

  parts = [part.strip() for part in line.split(";")]
  if len(parts) < 11:
    return None

  try:
    altitude = float(parts[0])
    latitude = float(parts[1])
    longitude = float(parts[2])
    satellites = int(parts[3])
    threshold = float(parts[4])
    fired = bool(int(parts[5]))
    sd_on = bool(int(parts[6]))
    sd_ok = bool(int(parts[7]))
    bme_ok = bool(int(parts[8]))
    gps_ok = bool(int(parts[9]))
    uptime_ms = int(parts[10])
    rssi = float(parts[11]) if len(parts) > 11 and parts[11] else None
    snr = float(parts[12]) if len(parts) > 12 and parts[12] else None
  except ValueError:
    return None

  return {
    "type": "telemetry",
    "altitude": altitude,
    "latitude": latitude,
    "longitude": longitude,
    "satellites": satellites,
    "threshold": threshold,
    "fired": fired,
    "sd_on": sd_on,
    "sd_ok": sd_ok,
    "bme_ok": bme_ok,
    "gps_ok": gps_ok,
    "uptime_ms": uptime_ms,
    "rssi": rssi,
    "snr": snr,
    "raw": line,
  }