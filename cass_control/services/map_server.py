import http.server
import json
import re
import socketserver
import threading
from urllib.parse import unquote


BLANK_PNG = (
  b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
  b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\x0bIDATx\x9cc\x00\x01"
  b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def make_map_html(bounds, host, port):
  config_json = json.dumps(bounds)
  return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <link rel=\"stylesheet\" href=\"https://unpkg.com/leaflet@1.9.4/dist/leaflet.css\" />
  <script src=\"https://unpkg.com/leaflet@1.9.4/dist/leaflet.js\"></script>
  <style>
    html, body, #map {{ height: 100%; margin: 0; }}
    body {{ background: #e5ecf4; }}
    #map {{ background: linear-gradient(180deg, #dce7f3 0%, #f4f6fb 100%); }}
    .rocket-dot {{
      width: 10px;
      height: 10px;
      border-radius: 50%;
      background: #ff6a3d;
      border: 1px solid #80230b;
      box-shadow: 0 0 0 2px rgba(255, 106, 61, 0.18);
    }}
    .leaflet-control-zoom a {{
      color: #0d1526;
    }}
  </style>
</head>
<body>
  <div id=\"map\"></div>
  <script>
    const cfg = {config_json};
    const map = L.map('map', {{
      zoomControl: true,
      minZoom: cfg.min_zoom,
      maxZoom: cfg.max_zoom,
      maxBounds: [[cfg.south, cfg.west], [cfg.north, cfg.east]],
      maxBoundsViscosity: 1.0,
      doubleClickZoom: false,
      worldCopyJump: false,
      preferCanvas: true,
    }});

    L.tileLayer('http://{host}:{port}/{{z}}/{{x}}/{{y}}.png', {{
      minZoom: cfg.min_zoom,
      maxZoom: cfg.max_zoom,
      noWrap: true,
      attribution: 'Tiles locales CASS'
    }}).addTo(map);

    map.fitBounds([[cfg.south, cfg.west], [cfg.north, cfg.east]], {{ padding: [24, 24] }});
    map.on('dblclick', () => {{
      console.log('__CASS_FOCUS_MAP__');
    }});

    const rocketIcon = L.divIcon({{
      className: 'rocket-dot',
      iconSize: [10, 10],
      iconAnchor: [5, 5]
    }});

    let marker = null;
    let followMode = false;

    function activateFollowMode() {{
      followMode = true;
      if (marker) {{
        map.setView(marker.getLatLng(), cfg.max_zoom);
      }}
    }}

    function deactivateFollowMode() {{
      followMode = false;
    }}

    function showFollowMenu(latlng) {{
      const popup = L.popup({{ closeButton: true, autoClose: true, closeOnClick: true }})
        .setLatLng(latlng)
        .setContent(`
          <div style="display:flex;flex-direction:column;gap:6px;min-width:120px;">
            <div style="font-weight:700;color:#0d1526;">Cohete</div>
            <button id="follow-rocket-btn" style="cursor:pointer;border:none;border-radius:8px;padding:8px 10px;background:#1d7df2;color:#fff;font-weight:700;">
              Seguirlo
            </button>
            <button id="unfollow-rocket-btn" style="cursor:pointer;border:none;border-radius:8px;padding:8px 10px;background:#2f415f;color:#fff;font-weight:700;">
              Dejar de seguirlo
            </button>
          </div>
        `);

      popup.openOn(map);
      window.setTimeout(() => {{
        const button = document.getElementById('follow-rocket-btn');
        const unfollowButton = document.getElementById('unfollow-rocket-btn');
        if (button) {{
          button.onclick = () => {{
            activateFollowMode();
            map.closePopup();
          }};
        }}
        if (unfollowButton) {{
          unfollowButton.onclick = () => {{
            deactivateFollowMode();
            map.closePopup();
          }};
        }}
      }}, 0);
    }}

    async function refreshPosition() {{
      try {{
        const response = await fetch('http://{host}:{port}/position', {{ cache: 'no-store' }});
        const data = await response.json();
        if (!data.ok) {{
          if (marker) {{
            map.removeLayer(marker);
            marker = null;
          }}
          return;
        }}

        const latLng = [data.lat, data.lon];
        if (!marker) {{
          marker = L.marker(latLng, {{ icon: rocketIcon }}).addTo(map);
          map.setView(latLng, cfg.max_zoom);
          marker.on('contextmenu', (event) => {{
            showFollowMenu(event.latlng);
          }});
        }} else {{
          marker.setLatLng(latLng);
          if (followMode) {{
            map.setView(latLng, cfg.max_zoom);
          }}
        }}
      }} catch (error) {{
      }}
    }}

    setInterval(refreshPosition, 300);
    refreshPosition();
  </script>
</body>
</html>
"""


class LocalRequestHandler(http.server.BaseHTTPRequestHandler):
  server_version = "CASSControl/1.0"

  def _write_json(self, payload):
    body = json.dumps(payload).encode("utf-8")
    self.send_response(200)
    self.send_header("Content-Type", "application/json; charset=utf-8")
    self.send_header("Content-Length", str(len(body)))
    self.send_header("Cache-Control", "no-store")
    self.end_headers()
    self.wfile.write(body)

  def _write_html(self, html_text):
    body = html_text.encode("utf-8")
    self.send_response(200)
    self.send_header("Content-Type", "text/html; charset=utf-8")
    self.send_header("Content-Length", str(len(body)))
    self.end_headers()
    self.wfile.write(body)

  def _write_png(self, png_bytes):
    self.send_response(200)
    self.send_header("Content-Type", "image/png")
    self.send_header("Content-Length", str(len(png_bytes)))
    self.end_headers()
    self.wfile.write(png_bytes)

  def do_GET(self):
    if self.path == "/" or self.path.startswith("/?"):
      self._write_html(self.server.html_text)
      return

    if self.path.startswith("/position"):
      self._write_json(self.server.state.get_position_payload())
      return

    match = re.match(r"^/(\d+)/(\d+)/(\d+)\.png$", unquote(self.path))
    if not match:
      self.send_error(404, "File not found")
      return

    zoom = int(match.group(1))
    x_value = int(match.group(2))
    y_value = int(match.group(3))
    tile_path = self._resolve_tile_path(zoom, x_value, y_value)

    if tile_path is None:
      self._write_png(BLANK_PNG)
      return

    try:
      self._write_png(tile_path.read_bytes())
    except OSError:
      self._write_png(BLANK_PNG)

  def _resolve_tile_path(self, zoom, x_value, y_value):
    direct_path = self.server.tiles_dir / str(zoom) / str(x_value) / f"{y_value}.png"
    if direct_path.exists():
      return direct_path
    return None

  def log_message(self, format_text, *args):
    return


class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
  daemon_threads = True
  allow_reuse_address = True


def start_map_server(state, tiles_dir, bounds, host):
  httpd = ThreadedHTTPServer((host, 0), LocalRequestHandler)
  httpd.tiles_dir = tiles_dir
  httpd.state = state
  httpd.html_text = make_map_html(bounds, host, httpd.server_port)

  server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
  server_thread.start()
  return httpd