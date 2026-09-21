import math


def tile_to_latlon(zoom, x_tile, y_tile):
  n = 2.0 ** zoom
  lon_deg = x_tile / n * 360.0 - 180.0
  lat_rad = math.atan(math.sinh(math.pi * (1.0 - 2.0 * y_tile / n)))
  lat_deg = math.degrees(lat_rad)
  return lat_deg, lon_deg


def build_tile_index(tiles_dir):
  tile_index = {}
  if not tiles_dir.exists():
    return tile_index

  for zoom_dir in tiles_dir.iterdir():
    if not zoom_dir.is_dir() or not zoom_dir.name.isdigit():
      continue

    zoom = int(zoom_dir.name)
    x_map = {}
    for x_dir in zoom_dir.iterdir():
      if not x_dir.is_dir() or not x_dir.name.isdigit():
        continue

      y_values = []
      for y_file in x_dir.glob("*.png"):
        if y_file.stem.isdigit():
          y_values.append(int(y_file.stem))

      if y_values:
        x_map[int(x_dir.name)] = sorted(y_values)

    if x_map:
      tile_index[zoom] = x_map

  return tile_index


def compute_bounds(tile_index):
  if not tile_index:
    return None

  best_zoom = max(tile_index.keys())
  x_values = sorted(tile_index[best_zoom].keys())
  y_values = []
  for x_value in x_values:
    y_values.extend(tile_index[best_zoom][x_value])

  if not x_values or not y_values:
    return None

  x_min = min(x_values)
  x_max = max(x_values)
  y_min = min(y_values)
  y_max = max(y_values)
  north, west = tile_to_latlon(best_zoom, x_min, y_min)
  south, east = tile_to_latlon(best_zoom, x_max + 1, y_max + 1)

  return {
    "min_zoom": min(tile_index.keys()),
    "max_zoom": max(tile_index.keys()),
    "best_zoom": best_zoom,
    "north": north,
    "south": south,
    "west": west,
    "east": east,
  }