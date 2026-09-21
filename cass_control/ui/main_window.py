import time
from collections import deque

from PyQt5.QtCore import QEvent, QTimer, Qt, QUrl
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
  QCheckBox,
  QComboBox,
  QFileDialog,
  QFrame,
  QGridLayout,
  QHBoxLayout,
  QLabel,
  QLineEdit,
  QMainWindow,
  QPlainTextEdit,
  QPushButton,
  QSizePolicy,
  QVBoxLayout,
  QWidget,
)
from PyQt5.QtWebEngineWidgets import QWebEngineView

from cass_control.services.serial_bridge import list_serial_ports
from cass_control.ui.styles import STYLE_SHEET
from cass_control.ui.widgets import MapBridgePage, RocketViewer, TimeSeriesChart, make_card


class FlightControlWindow(QMainWindow):
  def __init__(self, config, state, serial_bridge, map_url):
    super().__init__()
    self.config = config
    self.state = state
    self.serial_bridge = serial_bridge
    self.telemetry_labels = {}
    self.altitude_history = deque(maxlen=180)
    self.rssi_history = deque(maxlen=180)
    self.snr_history = deque(maxlen=180)
    self.fire_arm_enabled = False
    self.fire_press_count = 0
    self.first_fire_press_ms = 0
    self.is_borderless_fullscreen = False
    self.focus_mode = None
    self.camera_mode = 0

    self.setWindowTitle(config.application_name)
    self.resize(1600, 920)
    self.setStyleSheet(STYLE_SHEET)

    root = QWidget(self)
    root_layout = QVBoxLayout(root)
    root_layout.setContentsMargins(16, 16, 16, 16)
    root_layout.setSpacing(14)

    root_layout.addWidget(self._build_visualizers_row())
    root_layout.addWidget(self._build_bottom_dashboard(), stretch=1)

    self.setCentralWidget(root)

    self.ui_timer = QTimer(self)
    self.ui_timer.timeout.connect(self.refresh_ui)
    self.ui_timer.start(config.ui.refresh_ms)

    self.web_view.setUrl(QUrl(map_url))
    self.refresh_ports()
    self.refresh_ui()

  def enter_borderless_fullscreen(self):
    if self.is_borderless_fullscreen:
      return
    self.setWindowFlag(Qt.FramelessWindowHint, True)
    self.showFullScreen()
    self.is_borderless_fullscreen = True

  def exit_borderless_fullscreen(self):
    if not self.is_borderless_fullscreen:
      return
    self.setWindowFlag(Qt.FramelessWindowHint, False)
    self.showMaximized()
    self.is_borderless_fullscreen = False

  def keyPressEvent(self, event):
    if event.key() == Qt.Key_Escape and self.is_borderless_fullscreen:
      self.exit_borderless_fullscreen()
      event.accept()
      return
    super().keyPressEvent(event)

  def _build_visualizers_row(self):
    self.visualizers_container = QWidget()
    layout = QHBoxLayout(self.visualizers_container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(14)

    self.map_card = self._build_map_card()
    self.placeholder_card = self._build_placeholder_3d()

    for card in [self.map_card, self.placeholder_card]:
      card.setObjectName("VisualCard")
      card.setFixedHeight(self.config.ui.visualizer_card_height)
      card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    layout.addWidget(self.map_card, stretch=1)
    layout.addWidget(self.placeholder_card, stretch=1)
    return self.visualizers_container

  def _build_bottom_dashboard(self):
    self.bottom_dashboard = QWidget()
    layout = QHBoxLayout(self.bottom_dashboard)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(14)

    self.status_card = self._build_status_card()
    self.connection_card = self._build_connection_card()
    self.status_card.setMinimumHeight(self.config.ui.bottom_card_min_height)
    self.connection_card.setMinimumHeight(self.config.ui.bottom_card_min_height)
    self.status_card.setMaximumHeight(self.config.ui.bottom_card_max_height)
    self.connection_card.setMaximumHeight(self.config.ui.bottom_card_max_height)

    layout.addWidget(self.status_card, stretch=3)
    layout.addWidget(self.connection_card, stretch=3)
    layout.addWidget(self._build_terminal_and_charts_card(), stretch=4)
    return self.bottom_dashboard

  def _build_map_card(self):
    card, layout = make_card("Mapa de vuelo")
    title = QLabel("Mapa de vuelo")
    title.setProperty("role", "section")
    layout.addWidget(title)

    self.web_view = QWebEngineView(self)
    self.map_page = MapBridgePage(self.web_view)
    self.map_page.focusMapRequested.connect(lambda: self.toggle_focus_mode("map"))
    self.web_view.setPage(self.map_page)
    self.web_view.setMinimumHeight(320)
    self.web_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    self.web_view.setStyleSheet("border-radius: 14px; background: #dfe7f2;")
    layout.addWidget(self.web_view, stretch=1)
    return card

  def _build_placeholder_3d(self):
    card, layout = make_card("Visualizador 3D")
    title = QLabel("Visualizador 3D")
    title.setProperty("role", "section")
    layout.addWidget(title)

    content_row = QHBoxLayout()
    content_row.setSpacing(10)

    panel = QFrame()
    panel.setStyleSheet("background: #0b1323; border: 1px solid #1f314d; border-radius: 12px;")
    panel_layout = QVBoxLayout(panel)
    panel_layout.setContentsMargins(10, 10, 10, 10)
    panel_layout.setSpacing(6)

    update_button = QPushButton("Actualizar")
    update_button.setProperty("variant", "ghost")
    update_button.clicked.connect(self.update_rocket_viewer_from_inputs)
    reset_button = QPushButton("Reset")
    reset_button.setProperty("variant", "ghost")
    reset_button.clicked.connect(self.reset_rocket_viewer)
    self.viewer_lock_button = QPushButton("Lock camara")
    self.viewer_lock_button.setCheckable(True)
    self.viewer_lock_button.setProperty("variant", "ghost")
    self.viewer_lock_button.clicked.connect(self.toggle_rocket_camera_lock)
    self.viewer_camera_button = QPushButton("Cambiar camara")
    self.viewer_camera_button.setProperty("variant", "ghost")
    self.viewer_camera_button.clicked.connect(self.cycle_rocket_camera)

    panel_layout.addWidget(update_button)
    panel_layout.addWidget(reset_button)
    panel_layout.addWidget(self.viewer_lock_button)
    panel_layout.addWidget(self.viewer_camera_button)

    self.viewer_camera_mode_label = QLabel("Camara: Original")
    self.viewer_camera_mode_label.setProperty("role", "metricLabel")
    panel_layout.addWidget(self.viewer_camera_mode_label)

    self.viewer_x_label = QLabel("X: 0.00 m")
    self.viewer_y_label = QLabel("Y: 0.00 m")
    self.viewer_z_label = QLabel("Z: 0.00 m")
    self.viewer_x_label.setProperty("role", "kvValue")
    self.viewer_y_label.setProperty("role", "kvValue")
    self.viewer_z_label.setProperty("role", "kvValue")
    panel_layout.addWidget(self.viewer_x_label)
    panel_layout.addWidget(self.viewer_y_label)
    panel_layout.addWidget(self.viewer_z_label)
    panel_layout.addStretch(1)

    self.rocket_viewer = RocketViewer(self.config.site.latitude, self.config.site.longitude)
    self.rocket_viewer.setStyleSheet("background: #0a1324; border: 1px solid #1f314d; border-radius: 12px;")
    self.rocket_viewer.installEventFilter(self)

    content_row.addWidget(panel, stretch=1)
    content_row.addWidget(self.rocket_viewer, stretch=3)
    layout.addLayout(content_row, stretch=1)
    return card

  def _build_status_card(self):
    card, layout = make_card("Estado y telemetria")

    top_row = QHBoxLayout()
    title = QLabel("Estado y telemetria")
    title.setProperty("role", "section")
    self.packet_badge = QLabel("Sin telemetria")
    self.packet_badge.setProperty("role", "statusWarn")
    top_row.addWidget(title)
    top_row.addWidget(self.packet_badge)
    layout.addLayout(top_row)

    mission_row = QHBoxLayout()
    self.mission_phase_badge = QLabel("Sin telemetria")
    self.mission_phase_badge.setProperty("role", "statusWarn")
    self.fire_state_badge = QLabel("FIRE sin ejecutar")
    self.fire_state_badge.setProperty("role", "statusNeutral")
    mission_row.addWidget(self.mission_phase_badge)
    mission_row.addWidget(self.fire_state_badge)
    layout.addLayout(mission_row)

    modules = QGridLayout()
    self.sd_badge = QLabel("SD --")
    self.bme_badge = QLabel("BME --")
    self.gps_badge = QLabel("GPS --")
    self.lora_badge = QLabel("LoRa --")
    for widget in [self.sd_badge, self.bme_badge, self.gps_badge, self.lora_badge]:
      widget.setProperty("role", "statusWarn")
    modules.addWidget(self.sd_badge, 0, 0)
    modules.addWidget(self.bme_badge, 0, 1)
    modules.addWidget(self.gps_badge, 1, 0)
    modules.addWidget(self.lora_badge, 1, 1)
    layout.addLayout(modules)

    metrics = QGridLayout()
    metrics.setHorizontalSpacing(12)
    metrics.setVerticalSpacing(4)
    fields = [
      ("ALT", "Altitud", "0.00 m"),
      ("LAT", "Latitud", "--"),
      ("LON", "Longitud", "--"),
      ("SAT", "Satelites", "0"),
      ("THR", "Threshold", "0 m"),
      ("FIR", "Disparo", "NO"),
      ("SDO", "SD Guardando", "OFF"),
      ("SDK", "SD Estado", "NO OK"),
      ("BME", "BME280", "NO OK"),
      ("GPS", "GPS", "NO OK"),
      ("TIM", "Uptime", "0 s"),
      ("RF ", "RSSI / SNR", "-- / --"),
    ]

    for index, (key, label_text, default_text) in enumerate(fields):
      key_label = QLabel(label_text)
      key_label.setProperty("role", "kvKey")
      value_label = QLabel(default_text)
      value_label.setProperty("role", "kvValue")
      self.telemetry_labels[key] = value_label
      row = index // 2
      column = (index % 2) * 2
      metrics.addWidget(key_label, row, column)
      metrics.addWidget(value_label, row, column + 1)

    layout.addLayout(metrics)
    return card

  def _build_terminal_and_charts_card(self):
    card, layout = make_card("Terminal y graficas")
    title_row = QHBoxLayout()
    title = QLabel("Terminal y graficas")
    title.setProperty("role", "section")
    self.latest_packet_badge = QLabel("Sin ACK")
    self.latest_packet_badge.setProperty("role", "statusWarn")
    title_row.addWidget(title)
    title_row.addWidget(self.latest_packet_badge)
    layout.addLayout(title_row)

    self.terminal = QPlainTextEdit()
    self.terminal.setReadOnly(True)
    self.terminal.setMinimumHeight(130)
    self.terminal.setFont(QFont("Cascadia Mono", 10))
    layout.addWidget(self.terminal, stretch=1)

    command_row = QHBoxLayout()
    self.custom_command_edit = QLineEdit()
    self.custom_command_edit.setPlaceholderText("Comando manual, por ejemplo: STATUS o THR:150")
    send_button = QPushButton("Enviar")
    send_button.clicked.connect(self.send_custom_command)
    command_row.addWidget(self.custom_command_edit, stretch=1)
    command_row.addWidget(send_button)
    layout.addLayout(command_row)

    charts_row = QHBoxLayout()
    charts_row.setSpacing(10)
    self.altitude_chart = TimeSeriesChart("Altitud (m)", "#42d6a4")
    self.rssi_chart = TimeSeriesChart("RSSI (dBm)", "#61a0ff")
    self.snr_chart = TimeSeriesChart("SNR (dB)", "#ffb44f")
    charts_row.addWidget(self.altitude_chart)
    charts_row.addWidget(self.rssi_chart)
    charts_row.addWidget(self.snr_chart)
    layout.addLayout(charts_row)
    return card

  def _build_connection_card(self):
    card, layout = make_card("Conexion y control")

    status_row = QHBoxLayout()
    title = QLabel("Conexion y control")
    title.setProperty("role", "section")
    self.connection_badge = QLabel("Desconectado")
    self.connection_badge.setProperty("role", "statusWarn")
    status_row.addWidget(title)
    status_row.addWidget(self.connection_badge)
    layout.addLayout(status_row)

    form = QGridLayout()
    form.setHorizontalSpacing(8)
    form.setVerticalSpacing(4)

    form.addWidget(QLabel("Puerto"), 0, 0)
    self.port_combo = QComboBox()
    form.addWidget(self.port_combo, 0, 1)

    refresh_ports_button = QPushButton("Refrescar")
    refresh_ports_button.setProperty("variant", "ghost")
    refresh_ports_button.clicked.connect(self.refresh_ports)
    form.addWidget(refresh_ports_button, 0, 2)

    form.addWidget(QLabel("Baudrate"), 1, 0)
    self.baud_edit = QLineEdit(str(self.config.serial.default_baudrate))
    form.addWidget(self.baud_edit, 1, 1, 1, 2)

    self.connect_button = QPushButton("Conectar")
    self.connect_button.clicked.connect(self.toggle_connection)
    self.disconnect_button = QPushButton("Desconectar")
    self.disconnect_button.setProperty("variant", "ghost")
    self.disconnect_button.clicked.connect(self.disconnect_serial)
    form.addWidget(self.connect_button, 2, 1)
    form.addWidget(self.disconnect_button, 2, 2)

    layout.addLayout(form)

    logging_frame = QFrame()
    logging_frame.setStyleSheet("background: #0f192c; border: 1px solid #29426a; border-radius: 12px;")
    logging_layout = QVBoxLayout(logging_frame)
    logging_layout.setContentsMargins(10, 10, 10, 10)
    logging_layout.setSpacing(6)

    logging_header = QHBoxLayout()
    logging_label = QLabel("Logging local (.txt)")
    logging_label.setProperty("role", "metricLabel")
    self.logging_switch = QCheckBox("OFF")
    self.logging_switch.stateChanged.connect(self.toggle_local_logging)
    logging_header.addWidget(logging_label)
    logging_header.addStretch(1)
    logging_header.addWidget(self.logging_switch)
    logging_layout.addLayout(logging_header)

    self.log_file_edit = QLineEdit(str(self.config.paths.local_logs_dir / self._default_log_name()))
    self.log_file_edit.setPlaceholderText("Ruta del archivo .txt para logs")
    logging_layout.addWidget(self.log_file_edit)

    log_buttons_row = QHBoxLayout()
    self.select_log_button = QPushButton("Seleccionar")
    self.select_log_button.setProperty("variant", "ghost")
    self.select_log_button.clicked.connect(self.select_log_file)
    self.create_log_button = QPushButton("Crear .txt")
    self.create_log_button.setProperty("variant", "ghost")
    self.create_log_button.clicked.connect(self.create_log_file)
    self.apply_log_button = QPushButton("Aplicar")
    self.apply_log_button.clicked.connect(self.apply_log_file_path)
    log_buttons_row.addWidget(self.select_log_button)
    log_buttons_row.addWidget(self.create_log_button)
    log_buttons_row.addWidget(self.apply_log_button)
    logging_layout.addLayout(log_buttons_row)

    layout.addWidget(logging_frame)

    fire_guard = QFrame()
    fire_guard.setStyleSheet("background: #120d15; border: 1px solid #4b2b58; border-radius: 12px;")
    fire_guard_layout = QVBoxLayout(fire_guard)
    fire_guard_layout.setContentsMargins(10, 10, 10, 10)
    fire_guard_layout.setSpacing(6)

    self.fire_arm_checkbox = QCheckBox("Habilitar envio FIRE")
    self.fire_arm_checkbox.stateChanged.connect(self.toggle_fire_arm)
    self.fire_arm_checkbox.setStyleSheet("color: #f2d0ff;")
    fire_guard_layout.addWidget(self.fire_arm_checkbox)

    fire_row = QHBoxLayout()
    self.fire_progress_badge = QLabel("Confirmacion FIRE: 0/3")
    self.fire_progress_badge.setProperty("role", "statusNeutral")
    self.fire_send_button = QPushButton("Enviar FIRE")
    self.fire_send_button.setProperty("variant", "danger")
    self.fire_send_button.clicked.connect(self.send_fire)
    self.fire_send_button.setEnabled(False)
    fire_row.addWidget(self.fire_progress_badge)
    fire_row.addWidget(self.fire_send_button)
    fire_guard_layout.addLayout(fire_row)
    layout.addWidget(fire_guard)

    threshold_row = QHBoxLayout()
    self.threshold_edit = QLineEdit("1000")
    self.threshold_edit.setPlaceholderText("Threshold")
    threshold_button = QPushButton("Enviar THR")
    threshold_button.clicked.connect(self.send_threshold)
    threshold_row.addWidget(self.threshold_edit)
    threshold_row.addWidget(threshold_button)
    layout.addLayout(threshold_row)

    commands_grid = QGridLayout()
    commands_grid.setHorizontalSpacing(8)
    commands_grid.setVerticalSpacing(4)

    buttons = [
      ("STATUS", self.send_status, "ghost"),
      ("PAUSE", self.send_pause, "ghost"),
      ("RESUME", self.send_resume, "ghost"),
      ("PRUEBA", self.send_prueba, "ghost"),
      ("RFIRE", self.send_rfire, "ghost"),
      ("RESET", self.send_reset, "danger"),
    ]

    for index, (text, handler, variant) in enumerate(buttons):
      button = QPushButton(text)
      button.setProperty("variant", variant)
      button.clicked.connect(handler)
      commands_grid.addWidget(button, index // 2, index % 2)

    layout.addLayout(commands_grid)
    return card

  def _default_log_name(self):
    return f"cass_log_{time.strftime('%Y%m%d_%H%M%S')}.txt"

  def refresh_ports(self):
    current = self.port_combo.currentText()
    self.port_combo.clear()
    ports = list_serial_ports(self.config.serial.default_port)
    self.port_combo.addItems(ports)

    if current and current in ports:
      self.port_combo.setCurrentText(current)
    elif self.config.serial.default_port in ports:
      self.port_combo.setCurrentText(self.config.serial.default_port)

  def select_log_file(self):
    file_path, _ = QFileDialog.getOpenFileName(
      self,
      "Seleccionar archivo de log",
      str(self.config.paths.local_logs_dir),
      "Text files (*.txt);;All files (*.*)",
    )
    if file_path:
      self.log_file_edit.setText(file_path)
      self.state.set_logging_file_path(file_path)
      self.state.push_log("SYS", f"Archivo de log seleccionado: {file_path}")

  def create_log_file(self):
    default_path = str(self.config.paths.local_logs_dir / self._default_log_name())
    file_path, _ = QFileDialog.getSaveFileName(
      self,
      "Crear archivo de log",
      default_path,
      "Text files (*.txt);;All files (*.*)",
    )
    if file_path:
      try:
        with open(file_path, "a", encoding="utf-8"):
          pass
      except OSError as error:
        self.state.push_log("ERR", f"No se pudo crear archivo de log: {error}")
        return

      self.log_file_edit.setText(file_path)
      self.state.set_logging_file_path(file_path)
      self.state.push_log("SYS", f"Archivo de log creado: {file_path}")

  def apply_log_file_path(self):
    file_path = self.log_file_edit.text().strip()
    if not file_path:
      self.state.push_log("ERR", "Ruta de log vacia")
      return

    if not file_path.lower().endswith(".txt"):
      file_path += ".txt"
      self.log_file_edit.setText(file_path)

    try:
      with open(file_path, "a", encoding="utf-8"):
        pass
    except OSError as error:
      self.state.push_log("ERR", f"No se pudo abrir archivo de log: {error}")
      return

    self.state.set_logging_file_path(file_path)
    self.state.push_log("SYS", f"Ruta de log aplicada: {file_path}")

  def toggle_local_logging(self, state):
    enabled = state == Qt.Checked

    if enabled:
      file_path = self.log_file_edit.text().strip()
      if not file_path:
        file_path = str(self.config.paths.local_logs_dir / self._default_log_name())
        self.log_file_edit.setText(file_path)

      if not file_path.lower().endswith(".txt"):
        file_path += ".txt"
        self.log_file_edit.setText(file_path)

      try:
        with open(file_path, "a", encoding="utf-8"):
          pass
      except OSError as error:
        self.logging_switch.blockSignals(True)
        self.logging_switch.setChecked(False)
        self.logging_switch.setText("OFF")
        self.logging_switch.blockSignals(False)
        self.state.push_log("ERR", f"No se pudo activar logging: {error}")
        return

      self.state.set_logging_file_path(file_path)

    self.state.set_logging_enabled(enabled)
    self.logging_switch.setText("ON" if enabled else "OFF")
    self.state.push_log("SYS", "Logging local activado" if enabled else "Logging local desactivado")

  def toggle_connection(self):
    port = self.port_combo.currentText().strip()
    try:
      baudrate = int(self.baud_edit.text().strip())
    except ValueError:
      self.state.push_log("ERR", "Baudrate invalido")
      return

    self.serial_bridge.connect(port, baudrate)

  def disconnect_serial(self):
    self.serial_bridge.disconnect()
    self.state.push_log("SYS", "Conexion serial cerrada por usuario")

  def send_custom_command(self):
    if self.serial_bridge.send_command(self.custom_command_edit.text()):
      self.custom_command_edit.clear()

  def send_threshold(self):
    value = self.threshold_edit.text().strip()
    self.serial_bridge.send_command(f"THR:{value}")

  def send_status(self):
    self.serial_bridge.send_command("STATUS")

  def send_pause(self):
    self.serial_bridge.send_command("PAUSE")

  def send_resume(self):
    self.serial_bridge.send_command("RESUME")

  def send_prueba(self):
    self.serial_bridge.send_command("PRUEBA")

  def send_fire(self):
    if not self.fire_arm_enabled:
      self.state.push_log("SAFE", "Bloqueado: habilita FIRE antes de enviar")
      return

    now_ms = int(time.time() * 1000)
    if self.fire_press_count == 0 or (now_ms - self.first_fire_press_ms) > self.config.safety.fire_confirm_window_ms:
      self.first_fire_press_ms = now_ms
      self.fire_press_count = 0

    if self.serial_bridge.send_command("FIRE"):
      self.fire_press_count += 1
      if self.fire_press_count >= 3:
        self.fire_press_count = 0
      self._update_fire_progress_badge()

  def send_rfire(self):
    self.serial_bridge.send_command("RFIRE")
    self.fire_press_count = 0
    self._update_fire_progress_badge()

  def send_reset(self):
    self.serial_bridge.send_command("RESET")

  def refresh_ui(self):
    snapshot = self.state.get_snapshot()
    connection_text = snapshot["connection_status"]
    self.connection_badge.setText(connection_text)
    self.connection_badge.setProperty(
      "role",
      "statusGood" if connection_text.startswith("Conectado") else "statusWarn",
    )
    self.connection_badge.style().unpolish(self.connection_badge)
    self.connection_badge.style().polish(self.connection_badge)

    has_telemetry = snapshot["telemetry"] is not None
    self.packet_badge.setText("Telemetria viva" if has_telemetry else "Sin telemetria")
    self.packet_badge.setProperty("role", "statusGood" if has_telemetry else "statusWarn")
    self.packet_badge.style().unpolish(self.packet_badge)
    self.packet_badge.style().polish(self.packet_badge)

    ack_text = snapshot["latest_ack"]
    self.latest_packet_badge.setText(ack_text)
    self.latest_packet_badge.setProperty("role", "statusWarn" if ack_text != "Sin ACK" else "statusNeutral")
    self.latest_packet_badge.style().unpolish(self.latest_packet_badge)
    self.latest_packet_badge.style().polish(self.latest_packet_badge)
    self._flush_logs()
    self._refresh_telemetry(snapshot["telemetry"])
    self._refresh_fire_progress_window()

  def eventFilter(self, watched, event):
    if event.type() == QEvent.MouseButtonDblClick:
      if watched is self.rocket_viewer:
        self.toggle_focus_mode("3d")
        return True
    return super().eventFilter(watched, event)

  def toggle_focus_mode(self, target):
    if self.focus_mode == target:
      self.focus_mode = None
      self.bottom_dashboard.show()
      self.map_card.show()
      self.placeholder_card.show()
      for card in [self.map_card, self.placeholder_card]:
        card.setFixedHeight(self.config.ui.visualizer_card_height)
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
      self.status_card.setMinimumHeight(self.config.ui.bottom_card_min_height)
      self.connection_card.setMinimumHeight(self.config.ui.bottom_card_min_height)
      self.status_card.setMaximumHeight(self.config.ui.bottom_card_max_height)
      self.connection_card.setMaximumHeight(self.config.ui.bottom_card_max_height)
      self.state.push_log("SYS", "Modo enfoque desactivado")
      return

    self.focus_mode = target
    self.bottom_dashboard.hide()
    if target == "map":
      self.placeholder_card.hide()
      self.map_card.show()
      self.map_card.setMinimumHeight(600)
      self.map_card.setMaximumHeight(16777215)
      self.map_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
      self.state.push_log("SYS", "Modo enfoque: mapa")
    else:
      self.map_card.hide()
      self.placeholder_card.show()
      self.placeholder_card.setMinimumHeight(600)
      self.placeholder_card.setMaximumHeight(16777215)
      self.placeholder_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
      self.state.push_log("SYS", "Modo enfoque: visualizador 3D")

  def _flush_logs(self):
    for line in self.state.pop_logs():
      self.terminal.appendPlainText(line)
    self.terminal.verticalScrollBar().setValue(self.terminal.verticalScrollBar().maximum())

  def _refresh_telemetry(self, telemetry):
    if telemetry is None:
      return

    self.telemetry_labels["ALT"].setText(f"{telemetry['altitude']:.2f} m")
    self.telemetry_labels["LAT"].setText(f"{telemetry['latitude']:.6f}")
    self.telemetry_labels["LON"].setText(f"{telemetry['longitude']:.6f}")
    self.telemetry_labels["SAT"].setText(str(telemetry["satellites"]))
    self.telemetry_labels["THR"].setText(f"{telemetry['threshold']:.0f} m")
    self.telemetry_labels["FIR"].setText("SI" if telemetry["fired"] else "NO")
    self.telemetry_labels["SDO"].setText("ON" if telemetry["sd_on"] else "OFF")
    self.telemetry_labels["SDK"].setText("OK" if telemetry["sd_ok"] else "NO OK")
    self.telemetry_labels["BME"].setText("OK" if telemetry["bme_ok"] else "NO OK")
    self.telemetry_labels["GPS"].setText("OK" if telemetry["gps_ok"] else "NO OK")
    self.telemetry_labels["TIM"].setText(f"{telemetry['uptime_ms'] / 1000:.0f} s")

    if telemetry["rssi"] is None or telemetry["snr"] is None:
      self.telemetry_labels["RF "].setText("-- / --")
    else:
      self.telemetry_labels["RF "].setText(f"{telemetry['rssi']:.0f} / {telemetry['snr']:.2f}")

    self.altitude_history.append(telemetry["altitude"])
    if telemetry["rssi"] is not None:
      self.rssi_history.append(telemetry["rssi"])
    if telemetry["snr"] is not None:
      self.snr_history.append(telemetry["snr"])

    self.altitude_chart.set_values(list(self.altitude_history))
    self.rssi_chart.set_values(list(self.rssi_history))
    self.snr_chart.set_values(list(self.snr_history))

    self._sync_rocket_viewer_with_telemetry(telemetry)
    self._refresh_mission_state(telemetry)

  def update_rocket_viewer_from_inputs(self):
    snapshot = self.state.get_snapshot()
    telemetry = snapshot["telemetry"]
    if telemetry is None:
      self.state.push_log("ERR", "No hay telemetria para actualizar visualizador 3D")
      return

    self.rocket_viewer.set_gps(telemetry["latitude"], telemetry["longitude"], telemetry["altitude"])
    self._update_rocket_local_labels()

  def reset_rocket_viewer(self):
    snapshot = self.state.get_snapshot()
    telemetry = snapshot["telemetry"]
    if telemetry is None:
      self.state.push_log("ERR", "No hay telemetria para reset del visualizador 3D")
      return

    self.rocket_viewer.reset_position(telemetry["latitude"], telemetry["longitude"], telemetry["altitude"])
    self.viewer_lock_button.setChecked(False)
    self.viewer_lock_button.setText("Lock camara")
    self._update_rocket_local_labels()

  def toggle_rocket_camera_lock(self):
    self.rocket_viewer.toggle_camera_lock()
    if getattr(self.rocket_viewer, "camera_locked", False):
      self.viewer_lock_button.setText("Unlock camara")
    else:
      self.viewer_lock_button.setText("Lock camara")

  def _sync_rocket_viewer_with_telemetry(self, telemetry):
    self.rocket_viewer.set_gps(telemetry["latitude"], telemetry["longitude"], telemetry["altitude"])
    self._update_rocket_local_labels()

  def cycle_rocket_camera(self):
    self.camera_mode = (self.camera_mode + 1) % 3
    if self.camera_mode == 0:
      self.rocket_viewer.set_camera_original()
      self.viewer_camera_mode_label.setText("Camara: Original")
    elif self.camera_mode == 1:
      self.rocket_viewer.set_camera_topdown()
      self.viewer_camera_mode_label.setText("Camara: Cohete hacia abajo")
    else:
      self.rocket_viewer.set_camera_side_lock()
      self.viewer_camera_mode_label.setText("Camara: Lateral +50m X")

    self.viewer_lock_button.setChecked(True)
    self.viewer_lock_button.setText("Unlock camara")

  def _update_rocket_local_labels(self):
    self.viewer_x_label.setText(f"X: {getattr(self.rocket_viewer, 'x', 0.0):.2f} m")
    self.viewer_y_label.setText(f"Y: {getattr(self.rocket_viewer, 'y', 0.0):.2f} m")
    self.viewer_z_label.setText(f"Z: {getattr(self.rocket_viewer, 'z', 0.0):.2f} m")

  def _refresh_mission_state(self, telemetry):
    if telemetry["fired"]:
      self.fire_state_badge.setText("FIRE ejecutado")
      self.fire_state_badge.setProperty("role", "statusDanger")
    else:
      self.fire_state_badge.setText("FIRE sin ejecutar")
      self.fire_state_badge.setProperty("role", "statusNeutral")
    self.fire_state_badge.style().unpolish(self.fire_state_badge)
    self.fire_state_badge.style().polish(self.fire_state_badge)

    if telemetry["sd_on"]:
      phase_text = "Fase SD_WRITE"
      phase_role = "statusWarn"
    else:
      phase_text = "Fase RF_PHASE"
      phase_role = "statusGood"
    self.mission_phase_badge.setText(phase_text)
    self.mission_phase_badge.setProperty("role", phase_role)
    self.mission_phase_badge.style().unpolish(self.mission_phase_badge)
    self.mission_phase_badge.style().polish(self.mission_phase_badge)

    self._set_module_badge(self.sd_badge, "SD", telemetry["sd_ok"])
    self._set_module_badge(self.bme_badge, "BME", telemetry["bme_ok"])
    self._set_module_badge(self.gps_badge, "GPS", telemetry["gps_ok"])
    lora_ok = telemetry["rssi"] is not None and telemetry["snr"] is not None
    self._set_module_badge(self.lora_badge, "LoRa", lora_ok)

  def _set_module_badge(self, label, name, is_ok):
    label.setText(f"{name} {'OK' if is_ok else 'NO OK'}")
    label.setProperty("role", "statusGood" if is_ok else "statusWarn")
    label.style().unpolish(label)
    label.style().polish(label)

  def toggle_fire_arm(self, state):
    self.fire_arm_enabled = state == Qt.Checked
    self.fire_send_button.setEnabled(self.fire_arm_enabled)
    if self.fire_arm_enabled:
      self.state.push_log("SAFE", "FIRE habilitado por operador")
    else:
      self.state.push_log("SAFE", "FIRE bloqueado")
      self.fire_press_count = 0
    self._update_fire_progress_badge()

  def _refresh_fire_progress_window(self):
    if self.fire_press_count == 0:
      return
    now_ms = int(time.time() * 1000)
    if (now_ms - self.first_fire_press_ms) > self.config.safety.fire_confirm_window_ms:
      self.fire_press_count = 0
      self._update_fire_progress_badge()

  def _update_fire_progress_badge(self):
    self.fire_progress_badge.setText(f"Confirmacion FIRE: {self.fire_press_count}/3")
    if not self.fire_arm_enabled:
      role = "statusWarn"
    elif self.fire_press_count == 0:
      role = "statusNeutral"
    else:
      role = "statusDanger"
    self.fire_progress_badge.setProperty("role", role)
    self.fire_progress_badge.style().unpolish(self.fire_progress_badge)
    self.fire_progress_badge.style().polish(self.fire_progress_badge)

  def closeEvent(self, event):
    self.ui_timer.stop()
    super().closeEvent(event)