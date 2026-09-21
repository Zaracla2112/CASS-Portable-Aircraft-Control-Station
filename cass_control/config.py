import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SiteConfig:
  name: str
  latitude: float
  longitude: float


@dataclass(frozen=True)
class MissionConfig:
  name: str
  vehicle_type: str
  aircraft_family: str
  notes: str


@dataclass(frozen=True)
class SerialConfig:
  default_port: str
  default_baudrate: int


@dataclass(frozen=True)
class SafetyConfig:
  fire_confirm_window_ms: int


@dataclass(frozen=True)
class UIConfig:
  refresh_ms: int
  visualizer_card_height: int
  bottom_card_min_height: int
  bottom_card_max_height: int


@dataclass(frozen=True)
class PathConfig:
  project_root: Path
  resources_root: Path
  tiles_dir: Path
  models_dir: Path
  images_dir: Path
  outputs_root: Path
  local_logs_dir: Path
  telemetry_logs_dir: Path
  notes_dir: Path


@dataclass(frozen=True)
class AppConfig:
  application_name: str
  host: str
  site: SiteConfig
  mission: MissionConfig
  serial: SerialConfig
  safety: SafetyConfig
  ui: UIConfig
  paths: PathConfig

  @property
  def default_center(self):
    return (self.site.latitude, self.site.longitude)


def _resolve_path(project_root, relative_path):
  return (project_root / relative_path).resolve()


def load_app_config():
  project_root = Path(__file__).resolve().parents[1]
  config_path = project_root / "config" / "app_config.json"
  raw = json.loads(config_path.read_text(encoding="utf-8"))

  paths = raw["paths"]
  path_config = PathConfig(
    project_root=project_root,
    resources_root=_resolve_path(project_root, paths["resources_root"]),
    tiles_dir=_resolve_path(project_root, paths["tiles_dir"]),
    models_dir=_resolve_path(project_root, paths["models_dir"]),
    images_dir=_resolve_path(project_root, paths["images_dir"]),
    outputs_root=_resolve_path(project_root, paths["outputs_root"]),
    local_logs_dir=_resolve_path(project_root, paths["local_logs_dir"]),
    telemetry_logs_dir=_resolve_path(project_root, paths["telemetry_logs_dir"]),
    notes_dir=_resolve_path(project_root, paths["notes_dir"]),
  )

  return AppConfig(
    application_name=raw["application_name"],
    host=raw["host"],
    site=SiteConfig(**raw["site"]),
    mission=MissionConfig(**raw["mission"]),
    serial=SerialConfig(**raw["serial"]),
    safety=SafetyConfig(**raw["safety"]),
    ui=UIConfig(**raw["ui"]),
    paths=path_config,
  )


def ensure_runtime_directories(config):
  directories = [
    config.paths.resources_root,
    config.paths.tiles_dir,
    config.paths.models_dir,
    config.paths.images_dir,
    config.paths.outputs_root,
    config.paths.local_logs_dir,
    config.paths.telemetry_logs_dir,
    config.paths.notes_dir,
  ]
  for directory in directories:
    directory.mkdir(parents=True, exist_ok=True)