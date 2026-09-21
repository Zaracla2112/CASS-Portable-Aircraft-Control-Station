STYLE_SHEET = """
QWidget {
  background: #0c1220;
  color: #e6edf7;
  font-family: "Segoe UI";
  font-size: 12px;
}
QMainWindow {
  background: #0a101b;
}
QFrame#HeroCard {
  background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #17233b, stop:1 #0c1220);
  border: 1px solid #2b4268;
  border-radius: 20px;
}
QFrame#VisualCard {
  background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #121b2e, stop:1 #0d1526);
  border: 1px solid #253a5f;
  border-radius: 18px;
}
QLabel[role="title"] {
  font-size: 24px;
  font-weight: 700;
  color: #f4f7fb;
}
QLabel[role="section"] {
  font-size: 13px;
  font-weight: 700;
  color: #93a8c9;
  letter-spacing: 0.5px;
}
QLabel[role="metricValue"] {
  font-size: 17px;
  font-weight: 700;
  color: #f9fbff;
}
QLabel[role="metricLabel"] {
  font-size: 11px;
  color: #7f93b3;
}
QLabel[role="statusGood"] {
  background: #14311f;
  color: #7ee2a8;
  border: 1px solid #245c3a;
  border-radius: 10px;
  padding: 4px 10px;
  font-weight: 700;
}
QLabel[role="statusWarn"] {
  background: #382814;
  color: #f6c66d;
  border: 1px solid #6f5128;
  border-radius: 10px;
  padding: 4px 10px;
  font-weight: 700;
}
QLabel[role="placeholderTitle"] {
  font-size: 20px;
  font-weight: 700;
}
QLineEdit, QComboBox, QPlainTextEdit {
  background: #08101d;
  border: 1px solid #263856;
  border-radius: 10px;
  padding: 8px 10px;
}
QComboBox::drop-down {
  border: none;
}
QPushButton {
  background: #1d7df2;
  color: white;
  border: none;
  border-radius: 10px;
  padding: 6px 10px;
  font-weight: 700;
  font-size: 11px;
}
QPushButton:hover {
  background: #3790ff;
}
QPushButton[variant="ghost"] {
  background: #132039;
  border: 1px solid #29426a;
}
QPushButton[variant="danger"] {
  background: #bf3f3f;
}
QPushButton[variant="danger"]:hover {
  background: #db5858;
}
QPlainTextEdit {
  font-family: "Cascadia Mono";
  font-size: 11px;
}
QLabel[role="kvKey"] {
  color: #7f93b3;
  font-size: 11px;
  font-weight: 600;
}
QLabel[role="kvValue"] {
  color: #eef4ff;
  font-size: 13px;
  font-weight: 700;
}
QLabel[role="statusDanger"] {
  background: #3f1010;
  color: #ff8f8f;
  border: 1px solid #7f2a2a;
  border-radius: 10px;
  padding: 4px 10px;
  font-weight: 700;
}
QLabel[role="statusNeutral"] {
  background: #132039;
  color: #b8cae6;
  border: 1px solid #29426a;
  border-radius: 10px;
  padding: 4px 10px;
  font-weight: 700;
}
"""