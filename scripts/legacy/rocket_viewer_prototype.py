import sys
import math

from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QGroupBox
)

from PyQt5.QtOpenGL import QGLWidget

from OpenGL.GL import *
from OpenGL.GLU import *


class RocketViewer(QGLWidget):

    def __init__(self):
        super().__init__()

        # ==========================================
        # REFERENCIA GPS
        # ==========================================

        self.lat0 = 32.603000
        self.lon0 = -115.387000
        self.alt0 = 0

        # ==========================================
        # POSICIÓN DEL COHETE
        # ==========================================

        self.x = 0
        self.y = 0
        self.z = 0

        # ==========================================
        # CÁMARA
        # ==========================================

        self.camera_x = 0
        self.camera_y = -10
        self.camera_z = 1.7

        # Orientación
        self.yaw = 90
        self.pitch = -10

        # Mouse
        self.last_mouse_x = 0
        self.last_mouse_y = 0
        self.mouse_pressed = False

        # Lock de cámara
        self.camera_locked = False

        self.setMinimumSize(
            800,
            600
        )


    # ==================================================
    # OPENGL
    # ==================================================

    def initializeGL(self):

        glEnable(
            GL_DEPTH_TEST
        )

        glClearColor(
            0.05,
            0.05,
            0.08,
            1
        )


    def resizeGL(
        self,
        width,
        height
    ):

        if height == 0:
            height = 1

        glViewport(
            0,
            0,
            width,
            height
        )

        glMatrixMode(
            GL_PROJECTION
        )

        glLoadIdentity()

        gluPerspective(
            60,
            width / height,
            0.1,
            1000
        )

        glMatrixMode(
            GL_MODELVIEW
        )


    # ==================================================
    # RENDER
    # ==================================================

    def paintGL(self):

        glClear(
            GL_COLOR_BUFFER_BIT |
            GL_DEPTH_BUFFER_BIT
        )

        glLoadIdentity()

        # ==========================================
        # LOCK DE CÁMARA
        # ==========================================

        if self.camera_locked:

            dx = (
                self.x -
                self.camera_x
            )

            dy = (
                self.y -
                self.camera_y
            )

            dz = (
                self.z -
                self.camera_z
            )

            horizontal_distance = math.sqrt(
                dx * dx +
                dy * dy
            )

            self.yaw = math.degrees(
                math.atan2(
                    dy,
                    dx
                )
            )

            self.pitch = math.degrees(
                math.atan2(
                    dz,
                    horizontal_distance
                )
            )

        # ==========================================
        # DIRECCIÓN DE LA CÁMARA
        # ==========================================

        yaw_rad = math.radians(
            self.yaw
        )

        pitch_rad = math.radians(
            self.pitch
        )

        direction_x = (
            math.cos(pitch_rad) *
            math.cos(yaw_rad)
        )

        direction_y = (
            math.cos(pitch_rad) *
            math.sin(yaw_rad)
        )

        direction_z = math.sin(
            pitch_rad
        )

        # ==========================================
        # PUNTO AL QUE MIRA
        # ==========================================

        look_x = (
            self.camera_x +
            direction_x
        )

        look_y = (
            self.camera_y +
            direction_y
        )

        look_z = (
            self.camera_z +
            direction_z
        )

        gluLookAt(
            self.camera_x,
            self.camera_y,
            self.camera_z,

            look_x,
            look_y,
            look_z,

            0,
            0,
            1
        )

        # ==========================================
        # ESCENA
        # ==========================================

        self.draw_grid()

        self.draw_axes()

        self.draw_rocket()


    # ==================================================
    # MOUSE
    # ==================================================

    def mousePressEvent(
        self,
        event
    ):

        self.last_mouse_x = event.x()
        self.last_mouse_y = event.y()

        self.mouse_pressed = True


    def mouseReleaseEvent(
        self,
        event
    ):

        self.mouse_pressed = False


    def mouseMoveEvent(
        self,
        event
    ):

        if not self.mouse_pressed:
            return

        if self.camera_locked:
            return

        dx = (
            event.x() -
            self.last_mouse_x
        )

        dy = (
            event.y() -
            self.last_mouse_y
        )

        # Movimiento horizontal
        self.yaw += (
            dx * 0.4
        )

        # Movimiento vertical
        self.pitch -= (
            dy * 0.4
        )

        # Evitar que la cámara se voltee
        self.pitch = max(
            -89,
            min(
                89,
                self.pitch
            )
        )

        self.last_mouse_x = event.x()
        self.last_mouse_y = event.y()

        self.update()


    # ==================================================
    # ZOOM
    # ==================================================

    def wheelEvent(
        self,
        event
    ):

        delta = (
            event.angleDelta().y()
        )

        yaw_rad = math.radians(
            self.yaw
        )

        pitch_rad = math.radians(
            self.pitch
        )

        direction_x = (
            math.cos(pitch_rad) *
            math.cos(yaw_rad)
        )

        direction_y = (
            math.cos(pitch_rad) *
            math.sin(yaw_rad)
        )

        direction_z = math.sin(
            pitch_rad
        )

        distance = (
            delta / 120
        )

        self.camera_x += (
            direction_x *
            distance
        )

        self.camera_y += (
            direction_y *
            distance
        )

        self.camera_z += (
            direction_z *
            distance
        )

        self.update()


    # ==================================================
    # GPS → X Y Z
    # ==================================================

    def set_gps(
        self,
        lat,
        lon,
        altitude
    ):

        lat0_rad = math.radians(
            self.lat0
        )

        # ------------------------------------------
        # Y = Norte / Sur
        # ------------------------------------------

        self.y = (
            lat -
            self.lat0
        ) * 111320

        # ------------------------------------------
        # X = Este / Oeste
        # ------------------------------------------

        self.x = (
            lon -
            self.lon0
        ) * 111320 * math.cos(
            lat0_rad
        )

        # ------------------------------------------
        # Z = Altura
        # ------------------------------------------

        self.z = (
            altitude -
            self.alt0
        )

        self.update()


    # ==================================================
    # RESET
    # ==================================================

    def reset_position(
        self,
        lat,
        lon,
        altitude
    ):

        # ==========================================
        # NUEVO ORIGEN
        # ==========================================

        self.lat0 = lat
        self.lon0 = lon
        self.alt0 = altitude

        # ==========================================
        # COHETE EN EL ORIGEN
        # ==========================================

        self.x = 0
        self.y = 0
        self.z = 0

        # ==========================================
        # CÁMARA
        # ==========================================

        self.camera_x = 0
        self.camera_y = -10
        self.camera_z = 1.7

        # Mirar hacia el origen
        self.yaw = 90
        self.pitch = -10

        # Desactivar lock
        self.camera_locked = False

        self.update()


    # ==================================================
    # LOCK CÁMARA
    # ==================================================

    def toggle_camera_lock(
        self
    ):

        self.camera_locked = (
            not self.camera_locked
        )

        self.update()


    # ==================================================
    # GRID
    # ==================================================

    def draw_grid(self):

        glColor3f(
            0.25,
            0.25,
            0.25
        )

        glLineWidth(1)

        glBegin(
            GL_LINES
        )

        size = 100

        for i in range(
            -size,
            size + 1
        ):

            # Líneas X
            glVertex3f(
                i,
                -size,
                0
            )

            glVertex3f(
                i,
                size,
                0
            )

            # Líneas Y
            glVertex3f(
                -size,
                i,
                0
            )

            glVertex3f(
                size,
                i,
                0
            )

        glEnd()


    # ==================================================
    # EJES
    # ==================================================

    def draw_axes(self):

        glLineWidth(3)

        glBegin(
            GL_LINES
        )

        # ==========================================
        # X
        # ==========================================

        glColor3f(
            1,
            0,
            0
        )

        glVertex3f(
            0,
            0,
            0
        )

        glVertex3f(
            10,
            0,
            0
        )

        # ==========================================
        # Y
        # ==========================================

        glColor3f(
            0,
            1,
            0
        )

        glVertex3f(
            0,
            0,
            0
        )

        glVertex3f(
            0,
            10,
            0
        )

        # ==========================================
        # Z
        # ==========================================

        glColor3f(
            0,
            0,
            1
        )

        glVertex3f(
            0,
            0,
            0
        )

        glVertex3f(
            0,
            0,
            10
        )

        glEnd()


    # ==================================================
    # COHETE
    # ==================================================

    def draw_rocket(self):

        glPushMatrix()

        glTranslatef(
            self.x,
            self.y,
            self.z
        )

        # ==========================================
        # CUERPO
        # ==========================================

        glColor3f(
            0.8,
            0.8,
            0.8
        )

        quadric = gluNewQuadric()

        gluCylinder(
            quadric,
            0.5,
            0.5,
            3,
            20,
            10
        )

        # ==========================================
        # PUNTA
        # ==========================================

        glTranslatef(
            0,
            0,
            3
        )

        glColor3f(
            0.9,
            0.1,
            0.1
        )

        gluCylinder(
            quadric,
            0.5,
            0,
            1,
            20,
            10
        )

        gluDeleteQuadric(
            quadric
        )

        # ==========================================
        # ALETAS
        # ==========================================

        glTranslatef(
            0,
            0,
            -3
        )

        glColor3f(
            0.7,
            0.1,
            0.1
        )

        self.draw_fin()

        glRotatef(
            90,
            0,
            0,
            1
        )

        self.draw_fin()

        glRotatef(
            90,
            0,
            0,
            1
        )

        self.draw_fin()

        glRotatef(
            90,
            0,
            0,
            1
        )

        self.draw_fin()

        glPopMatrix()


    # ==================================================
    # ALETA
    # ==================================================

    def draw_fin(self):

        glBegin(
            GL_TRIANGLES
        )

        glVertex3f(
            0.4,
            0,
            0
        )

        glVertex3f(
            1.2,
            0,
            0
        )

        glVertex3f(
            0.4,
            0,
            1.2
        )

        glEnd()


# ======================================================
# MAIN WINDOW
# ======================================================

class MainWindow(QMainWindow):

    def __init__(self):

        super().__init__()

        self.setWindowTitle(
            "CASS Rocket 3D Simulator"
        )

        self.resize(
            1200,
            750
        )

        # ==========================================
        # VISUALIZADOR
        # ==========================================

        self.viewer = RocketViewer()

        # ==========================================
        # ENTRADAS
        # ==========================================

        self.lat_input = QLineEdit(
            "32.603000"
        )

        self.lon_input = QLineEdit(
            "-115.387000"
        )

        self.alt_input = QLineEdit(
            "10"
        )

        # ==========================================
        # BOTÓN ACTUALIZAR
        # ==========================================

        update_button = QPushButton(
            "Actualizar"
        )

        update_button.clicked.connect(
            self.update_position
        )

        # ==========================================
        # BOTÓN RESET
        # ==========================================

        reset_button = QPushButton(
            "Reset"
        )

        reset_button.clicked.connect(
            self.reset_simulator
        )

        # ==========================================
        # BOTÓN LOCK
        # ==========================================

        self.lock_button = QPushButton(
            "Lock cámara"
        )

        self.lock_button.setCheckable(
            True
        )

        self.lock_button.clicked.connect(
            self.toggle_camera
        )

        # ==========================================
        # INFORMACIÓN
        # ==========================================

        self.x_label = QLabel(
            "X: 0.00 m"
        )

        self.y_label = QLabel(
            "Y: 0.00 m"
        )

        self.z_label = QLabel(
            "Z: 10.00 m"
        )

        # ==========================================
        # PANEL
        # ==========================================

        panel = QGroupBox(
            "Telemetría"
        )

        panel_layout = QVBoxLayout()

        panel_layout.addWidget(
            QLabel(
                "Latitud"
            )
        )

        panel_layout.addWidget(
            self.lat_input
        )

        panel_layout.addWidget(
            QLabel(
                "Longitud"
            )
        )

        panel_layout.addWidget(
            self.lon_input
        )

        panel_layout.addWidget(
            QLabel(
                "Altura (m)"
            )
        )

        panel_layout.addWidget(
            self.alt_input
        )

        panel_layout.addSpacing(
            10
        )

        panel_layout.addWidget(
            update_button
        )

        panel_layout.addWidget(
            reset_button
        )

        panel_layout.addWidget(
            self.lock_button
        )

        panel_layout.addSpacing(
            20
        )

        panel_layout.addWidget(
            QLabel(
                "Posición local"
            )
        )

        panel_layout.addWidget(
            self.x_label
        )

        panel_layout.addWidget(
            self.y_label
        )

        panel_layout.addWidget(
            self.z_label
        )

        panel_layout.addStretch()

        panel.setLayout(
            panel_layout
        )

        # ==========================================
        # LAYOUT PRINCIPAL
        # ==========================================

        main_layout = QHBoxLayout()

        main_layout.addWidget(
            panel,
            1
        )

        main_layout.addWidget(
            self.viewer,
            5
        )

        central = QWidget()

        central.setLayout(
            main_layout
        )

        self.setCentralWidget(
            central
        )

        # ==========================================
        # POSICIÓN INICIAL
        # ==========================================

        self.update_position()


    # ==================================================
    # ACTUALIZAR
    # ==================================================

    def update_position(self):

        try:

            lat = float(
                self.lat_input.text()
            )

            lon = float(
                self.lon_input.text()
            )

            alt = float(
                self.alt_input.text()
            )

            self.viewer.set_gps(
                lat,
                lon,
                alt
            )

            self.update_labels()

        except ValueError:

            print(
                "Valores inválidos"
            )


    # ==================================================
    # RESET
    # ==================================================

    def reset_simulator(self):

        try:

            lat = float(
                self.lat_input.text()
            )

            lon = float(
                self.lon_input.text()
            )

            alt = float(
                self.alt_input.text()
            )

            self.viewer.reset_position(
                lat,
                lon,
                alt
            )

            self.lock_button.setChecked(
                False
            )

            self.update_labels()

        except ValueError:

            print(
                "Valores inválidos"
            )


    # ==================================================
    # LOCK
    # ==================================================

    def toggle_camera(self):

        self.viewer.toggle_camera_lock()

        if self.viewer.camera_locked:

            self.lock_button.setText(
                "Unlock cámara"
            )

        else:

            self.lock_button.setText(
                "Lock cámara"
            )


    # ==================================================
    # ACTUALIZAR LABELS
    # ==================================================

    def update_labels(self):

        self.x_label.setText(
            f"X: {self.viewer.x:.2f} m"
        )

        self.y_label.setText(
            f"Y: {self.viewer.y:.2f} m"
        )

        self.z_label.setText(
            f"Z: {self.viewer.z:.2f} m"
        )


# ======================================================
# APPLICATION
# ======================================================

app = QApplication(
    sys.argv
)

window = MainWindow()

window.show()

sys.exit(
    app.exec_()
)