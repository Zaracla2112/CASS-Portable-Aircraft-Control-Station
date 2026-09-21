import math

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget
from PyQt5.QtWebEngineWidgets import QWebEnginePage

try:
  from PyQt5.QtOpenGL import QGLWidget
  from OpenGL.GL import (
    GL_COLOR_BUFFER_BIT,
    GL_DEPTH_BUFFER_BIT,
    GL_DEPTH_TEST,
    GL_LINE_LOOP,
    GL_LINES,
    GL_MODELVIEW,
    GL_PROJECTION,
    GL_QUADS,
    GL_TRIANGLES,
    glBegin,
    glClear,
    glClearColor,
    glColor3f,
    glEnable,
    glEnd,
    glLineWidth,
    glLoadIdentity,
    glMatrixMode,
    glPopMatrix,
    glPushMatrix,
    glRotatef,
    glTranslatef,
    glVertex3f,
    glViewport,
  )
  from OpenGL.GLU import gluCylinder, gluDeleteQuadric, gluLookAt, gluNewQuadric, gluPerspective
  OPENGL_AVAILABLE = True
except ImportError:
  OPENGL_AVAILABLE = False


class MapBridgePage(QWebEnginePage):
  focusMapRequested = pyqtSignal()

  def javaScriptConsoleMessage(self, _level, message, _line_number, _source_id):
    if message == "__CASS_FOCUS_MAP__":
      self.focusMapRequested.emit()
      return
    super().javaScriptConsoleMessage(_level, message, _line_number, _source_id)


class TimeSeriesChart(QWidget):
  def __init__(self, title, color_hex, parent=None):
    super().__init__(parent)
    self.title = title
    self.color = QColor(color_hex)
    self.values = []
    self.setMinimumHeight(74)

  def set_values(self, values):
    self.values = values
    self.update()

  def paintEvent(self, _event):
    painter = QPainter(self)
    painter.setRenderHint(QPainter.Antialiasing)
    rect = self.rect().adjusted(8, 8, -8, -8)

    painter.fillRect(rect, QColor("#0a1324"))
    painter.setPen(QPen(QColor("#203454"), 1))
    painter.drawRoundedRect(rect, 10, 10)

    painter.setPen(QPen(QColor("#91a8cc"), 1))
    painter.drawText(rect.adjusted(8, 6, -8, -6), Qt.AlignTop | Qt.AlignLeft, self.title)

    plot_rect = rect.adjusted(8, 26, -8, -8)
    if len(self.values) < 2:
      painter.setPen(QPen(QColor("#5e7497"), 1))
      painter.drawText(plot_rect, Qt.AlignCenter, "Sin datos")
      return

    min_value = min(self.values)
    max_value = max(self.values)
    if abs(max_value - min_value) < 1e-6:
      min_value -= 1
      max_value += 1

    painter.setPen(QPen(QColor("#1d2f4a"), 1))
    for step in range(1, 4):
      y = plot_rect.top() + step * plot_rect.height() / 4
      painter.drawLine(int(plot_rect.left()), int(y), int(plot_rect.right()), int(y))

    points = []
    count = len(self.values)
    for index, value in enumerate(self.values):
      x = plot_rect.left() + (plot_rect.width() * index / (count - 1))
      ratio = (value - min_value) / (max_value - min_value)
      y = plot_rect.bottom() - ratio * plot_rect.height()
      points.append((x, y))

    painter.setPen(QPen(self.color, 2))
    for index in range(len(points) - 1):
      x1, y1 = points[index]
      x2, y2 = points[index + 1]
      painter.drawLine(int(x1), int(y1), int(x2), int(y2))

    painter.setPen(QPen(QColor("#bcd0ed"), 1))
    painter.drawText(plot_rect.adjusted(0, 0, 0, -2), Qt.AlignBottom | Qt.AlignRight, f"{self.values[-1]:.2f}")


if OPENGL_AVAILABLE:
  class RocketViewer(QGLWidget):
    def __init__(self, site_latitude, site_longitude):
      super().__init__()
      self.lat0 = site_latitude
      self.lon0 = site_longitude
      self.alt0 = 0.0

      self.x = 0.0
      self.y = 0.0
      self.z = 0.0

      self.camera_x = 0.0
      self.camera_y = -10.0
      self.camera_z = 1.7
      self.yaw = 90.0
      self.pitch = -10.0

      self.last_mouse_x = 0
      self.last_mouse_y = 0
      self.mouse_pressed = False
      self.camera_locked = False

      self.setMinimumSize(420, 300)

    def initializeGL(self):
      glEnable(GL_DEPTH_TEST)
      glClearColor(0.05, 0.05, 0.08, 1)

    def resizeGL(self, width, height):
      if height == 0:
        height = 1
      glViewport(0, 0, width, height)
      glMatrixMode(GL_PROJECTION)
      glLoadIdentity()
      gluPerspective(60, width / height, 0.1, 1000)
      glMatrixMode(GL_MODELVIEW)

    def paintGL(self):
      glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
      glLoadIdentity()

      if self.camera_locked:
        dx = self.x - self.camera_x
        dy = self.y - self.camera_y
        dz = self.z - self.camera_z
        horizontal_distance = math.sqrt(dx * dx + dy * dy)
        self.yaw = math.degrees(math.atan2(dy, dx))
        self.pitch = math.degrees(math.atan2(dz, horizontal_distance))

      yaw_rad = math.radians(self.yaw)
      pitch_rad = math.radians(self.pitch)
      direction_x = math.cos(pitch_rad) * math.cos(yaw_rad)
      direction_y = math.cos(pitch_rad) * math.sin(yaw_rad)
      direction_z = math.sin(pitch_rad)

      look_x = self.camera_x + direction_x
      look_y = self.camera_y + direction_y
      look_z = self.camera_z + direction_z
      gluLookAt(self.camera_x, self.camera_y, self.camera_z, look_x, look_y, look_z, 0, 0, 1)

      self.draw_grid()
      self.draw_axes()
      self.draw_rocket()

    def mousePressEvent(self, event):
      self.last_mouse_x = event.x()
      self.last_mouse_y = event.y()
      self.mouse_pressed = True

    def mouseReleaseEvent(self, _event):
      self.mouse_pressed = False

    def mouseMoveEvent(self, event):
      if not self.mouse_pressed or self.camera_locked:
        return

      dx = event.x() - self.last_mouse_x
      dy = event.y() - self.last_mouse_y
      self.yaw += dx * 0.4
      self.pitch -= dy * 0.4
      self.pitch = max(-89, min(89, self.pitch))
      self.last_mouse_x = event.x()
      self.last_mouse_y = event.y()
      self.update()

    def wheelEvent(self, event):
      delta = event.angleDelta().y()
      yaw_rad = math.radians(self.yaw)
      pitch_rad = math.radians(self.pitch)
      direction_x = math.cos(pitch_rad) * math.cos(yaw_rad)
      direction_y = math.cos(pitch_rad) * math.sin(yaw_rad)
      direction_z = math.sin(pitch_rad)
      distance = delta / 120

      self.camera_x += direction_x * distance
      self.camera_y += direction_y * distance
      self.camera_z += direction_z * distance
      self.update()

    def set_gps(self, lat, lon, altitude):
      lat0_rad = math.radians(self.lat0)
      self.y = (lat - self.lat0) * 111320
      self.x = (lon - self.lon0) * 111320 * math.cos(lat0_rad)
      self.z = altitude - self.alt0
      self.update()

    def reset_position(self, lat, lon, altitude):
      self.lat0 = lat
      self.lon0 = lon
      self.alt0 = altitude
      self.x = 0.0
      self.y = 0.0
      self.z = 0.0
      self.camera_x = 0.0
      self.camera_y = -10.0
      self.camera_z = 1.7
      self.yaw = 90.0
      self.pitch = -10.0
      self.camera_locked = False
      self.update()

    def toggle_camera_lock(self):
      self.camera_locked = not self.camera_locked
      self.update()

    def set_camera_original(self):
      self.camera_x = self.x
      self.camera_y = self.y - 10.0
      self.camera_z = self.z + 1.7
      self.camera_locked = True
      self.update()

    def set_camera_topdown(self):
      self.camera_x = self.x
      self.camera_y = self.y
      self.camera_z = self.z + 12.0
      self.camera_locked = True
      self.update()

    def set_camera_side_lock(self):
      self.camera_x = self.x + 50.0
      self.camera_y = self.y
      self.camera_z = self.z + 10.0
      self.camera_locked = True
      self.update()

    def draw_grid(self):
      self.draw_ground()
      glColor3f(0.25, 0.25, 0.25)
      glLineWidth(1)
      glBegin(GL_LINES)
      size = 100
      for index in range(-size, size + 1):
        glVertex3f(index, -size, 0)
        glVertex3f(index, size, 0)
        glVertex3f(-size, index, 0)
        glVertex3f(size, index, 0)
      glEnd()

      half = 2.5
      glColor3f(1.0, 0.9, 0.1)
      glLineWidth(2)
      glBegin(GL_LINE_LOOP)
      glVertex3f(-half, -half, 0.01)
      glVertex3f(half, -half, 0.01)
      glVertex3f(half, half, 0.01)
      glVertex3f(-half, half, 0.01)
      glEnd()

    def draw_ground(self):
      size = 120
      glColor3f(0.10, 0.32, 0.12)
      glBegin(GL_QUADS)
      glVertex3f(-size, -size, -0.001)
      glVertex3f(size, -size, -0.001)
      glVertex3f(size, size, -0.001)
      glVertex3f(-size, size, -0.001)
      glEnd()

    def draw_axes(self):
      glLineWidth(3)
      glBegin(GL_LINES)
      glColor3f(1, 0, 0)
      glVertex3f(0, 0, 0)
      glVertex3f(10, 0, 0)
      glColor3f(0, 1, 0)
      glVertex3f(0, 0, 0)
      glVertex3f(0, 10, 0)
      glColor3f(0, 0, 1)
      glVertex3f(0, 0, 0)
      glVertex3f(0, 0, 10)
      glEnd()

    def draw_rocket(self):
      glPushMatrix()
      glTranslatef(self.x, self.y, self.z)
      glColor3f(0.8, 0.8, 0.8)
      quadric = gluNewQuadric()
      gluCylinder(quadric, 0.5, 0.5, 3, 20, 10)
      glTranslatef(0, 0, 3)
      glColor3f(0.9, 0.1, 0.1)
      gluCylinder(quadric, 0.5, 0, 1, 20, 10)
      gluDeleteQuadric(quadric)
      glTranslatef(0, 0, -3)
      glColor3f(0.7, 0.1, 0.1)
      self.draw_fin()
      glRotatef(90, 0, 0, 1)
      self.draw_fin()
      glRotatef(90, 0, 0, 1)
      self.draw_fin()
      glRotatef(90, 0, 0, 1)
      self.draw_fin()
      glPopMatrix()

    def draw_fin(self):
      glBegin(GL_TRIANGLES)
      glVertex3f(0.4, 0, 0)
      glVertex3f(1.2, 0, 0)
      glVertex3f(0.4, 0, 1.2)
      glEnd()
else:
  class RocketViewer(QWidget):
    def __init__(self, _site_latitude, _site_longitude):
      super().__init__()
      self.x = 0.0
      self.y = 0.0
      self.z = 0.0
      self.camera_locked = False
      self._status = QLabel("OpenGL no disponible: instala PyOpenGL")
      self._status.setAlignment(Qt.AlignCenter)
      self._status.setStyleSheet("color: #f6c66d;")
      layout = QVBoxLayout(self)
      layout.addWidget(self._status)

    def set_gps(self, lat, lon, altitude):
      self.x = lon
      self.y = lat
      self.z = altitude

    def reset_position(self, _lat, _lon, _altitude):
      self.x = 0.0
      self.y = 0.0
      self.z = 0.0

    def toggle_camera_lock(self):
      self.camera_locked = not self.camera_locked

    def set_camera_original(self):
      self.camera_locked = True

    def set_camera_topdown(self):
      self.camera_locked = True

    def set_camera_side_lock(self):
      self.camera_locked = True


def make_card(_title_text):
  card = QFrame()
  card.setObjectName("Card")
  layout = QVBoxLayout(card)
  layout.setContentsMargins(18, 16, 18, 16)
  layout.setSpacing(12)
  return card, layout