# UI/UX Decisions to Simplify Development

> Goal: reduce widget count, state complexity, and custom code.
> Everything here favours standard Qt patterns that DeepSeek V4 Pro
> generates reliably.

---

## 1. Single window, QStackedWidget — no multi-window

| Approach | Complexity |
|----------|-----------|
| Multiple top-level windows | High — focus, z-order, cross-window state, macOS menu bar per window |
| **Single QMainWindow + QStackedWidget** | **Low — one window, swap pages in place** |

All 11 screens live as pages in one `QStackedWidget`. The bottom nav just
calls `stack.setCurrentIndex(n)`. No window tracking, no `show()`/`hide()`,
no focus stealing.

The only exception: the "Add Service Entry" form can be a `QDialog` modal
(blocking, self-contained, no stack manipulation).

---

## 2. Qt Widgets, not QML

| Approach | DeepSeek V4 quality | PyInstaller | Mobile feel |
|----------|---------------------|-------------|-------------|
| QML / Qt Quick | Mediocre — struggles with QML syntax | Larger bundle, needs QML runtime | Excellent |
| **Qt Widgets + QSS** | **Excellent — standard Python classes** | Smaller, no QML engine | Good enough |

The dark theme is done entirely in QSS (Qt Style Sheets) — a single
`app.setStyleSheet(...)` call with ~50 lines of CSS-like rules.
No custom `paintEvent` overrides needed for theming.

```python
app.setStyleSheet("""
    QMainWindow { background: #1a1a2e; }
    QPushButton { background: #1C69D4; color: white; border-radius: 8px; padding: 12px; }
    QPushButton:hover { background: #0653B6; }
    QPushButton:disabled { background: #444; color: #888; }
    QLabel { color: #e0e0e0; }
    ...
""")
```

---

## 3. Inline expansion, not sub-page navigation

| Pattern | Implementation | State to manage |
|---------|---------------|-----------------|
| Navigate to detail page | Push/pop stack, back button, breadcrumb | Page stack, back-navigation state |
| **Inline expand/collapse on the same page** | **QWidget.setVisible(True/False)** | **One boolean per card** |

For DTC detail, coding option detail, and service entry detail: click the
card → the card expands downward to show detail content. Click again →
collapses. No page stack, no back button, no breadcrumb.

```python
class ExpandableCard(QWidget):
    def __init__(self, summary_widget, detail_widget):
        self.detail = detail_widget
        self.detail.setVisible(False)  # hidden by default
        layout = QVBoxLayout()
        layout.addWidget(summary_widget)
        layout.addWidget(self.detail)

    def mousePressEvent(self, event):
        self.detail.setVisible(not self.detail.isVisible())
```

The coding option detail (Screen 8) uses this: click "Angel Eyes Brightness"
→ the card expands to show radio buttons. Click again → collapses.

---

## 4. One reusable `CarWorker` thread pattern

Every car operation (read DTCs, write coding, read service history) follows
the exact same pattern. Build one base class, subclass per task.

```python
from PySide6.QtCore import QThread, Signal

class CarWorker(QThread):
    started    = Signal()
    progress   = Signal(str)      # status message for spinner
    finished   = Signal(object)    # result data
    error      = Signal(str)       # user-facing error message

    def run(self):
        self.started.emit()
        try:
            result = self.do_work()   # override in subclass
            self.finished.emit(result)
        except TimeoutError:
            self.error.emit(f"{self.ecu_name} is not responding...")
        except Exception as e:
            self.error.emit(str(e))

class DtcReadWorker(CarWorker):
    def __init__(self, connection, ecus):
        self.connection = connection
        self.ecus = ecus
    def do_work(self):
        dtcs = []
        for i, ecu in enumerate(self.ecus):
            self.progress.emit(f"Reading {ecu.name}... ({i+1}/{len(self.ecus)})")
            dtcs += read_dtcs(self.connection, ecu.addr)
        return dtcs
```

UI code becomes dead simple:

```python
def on_diagnostics_tab_entered(self):
    self.show_spinner("Reading fault codes...")
    self.worker = DtcReadWorker(self.conn, self.ecus)
    self.worker.progress.connect(self.spinner.set_label)
    self.worker.finished.connect(self.show_dtc_list)
    self.worker.error.connect(self.show_error)
    self.worker.start()
```

---

## 5. Bottom nav: QButtonGroup + QStackedWidget

Not a QTabWidget. QTabWidget draws tabs at the top/sides natively, which
fights custom styling. Instead:

```python
# Four QPushButtons in a horizontal layout at the bottom
nav_layout = QHBoxLayout()
for i, (icon, label) in enumerate([
    ("🏠", "Vehicle"), ("🔍", "Diagnostics"), ("🛠️", "Coding"), ("📋", "History")
]):
    btn = QPushButton(f"{icon}\n{label}")
    btn.setCheckable(True)
    btn.setEnabled(False)  # disabled until connected
    self.nav_group.addButton(btn, i)
    nav_layout.addWidget(btn)

# Connect button group to stacked widget
self.nav_group.idClicked.connect(self.stack.setCurrentIndex)
```

When connected: `[btn.setEnabled(True) for btn in self.nav_group.buttons()]`.

---

## 6. QDialog for forms, not sub-pages

The "Add Service Entry" form has its own state (checkboxes, date pickers,
text fields). Putting it in the page stack means saving/restoring state on
navigation. Instead:

```python
def on_add_service_clicked(self):
    dialog = AddServiceDialog(self)  # QDialog subclass
    if dialog.exec() == QDialog.Accepted:
        data = dialog.get_data()
        worker = ServiceWriteWorker(self.conn, data)
        worker.start()
```

`QDialog.exec()` is modal — blocks the main window, returns Accept/Reject,
no page stack manipulation. The dialog is self-contained, the form data
is collected once, and the dialog is garbage-collected after use.

---

## 7. QScrollArea + QVBoxLayout for every list

The same pattern for DTC list, coding categories, ECU trees, service entries,
and backup entries:

```python
scroll = QScrollArea()
scroll.setWidgetResizable(True)
container = QWidget()
layout = QVBoxLayout(container)

for item in data:
    card = self.make_card(item)   # ExpandableCard from #3
    layout.addWidget(card)

layout.addStretch()
scroll.setWidget(container)
```

No QListView, no QAbstractListModel, no model/view/delegate complexity.
Just add QWidgets to a scrollable vertical layout. For 88K DTCs or 2K coding
options, performance is fine — Qt only paints visible widgets.

---

## 8. Theme: one QSS file, no per-widget styling

All visual styling in `theme.qss`, loaded once:

```python
with open("assets/theme.qss") as f:
    app.setStyleSheet(f.read())
```

No inline `setStyleSheet()` calls, no per-widget color constants.
If the theme changes, edit one file.

---

## 9. QSettings for persistence — no config file parsing

```python
settings = QSettings("BMWTool", "BMWTool")

# Write
settings.setValue("last_vin", vin)
settings.setValue("backup_path", path)
settings.setValue("window_geometry", self.saveGeometry())

# Read
vin = settings.value("last_vin", "")
path = settings.value("backup_path", default_backup_path())
```

Cross-platform, auto-stored in the right OS location (plist on macOS, registry
on Windows), no JSON/config parsing code needed.

---

## 10. Avoid these things entirely

| Avoid | Because | Use instead |
|-------|---------|-------------|
| QML / Qt Quick | DeepSeek weaker, adds QML runtime to bundle | Qt Widgets + QSS |
| QListView + custom models | Model/view is powerful but verbose | QScrollArea + QWidget children |
| Multiple top-level windows | Focus, z-order, macOS menu issues | QStackedWidget |
| Custom paintEvent | Hard to get right, theme-inconsistent | QSS styling |
| Manual config file I/O | Platform differences, escaping bugs | QSettings |
| Sub-page navigation (push/pop) | Stack management, back-button logic | Inline expand/collapse + QDialog for forms |
| asyncio mixed with Qt | Two event loops, subtle bugs | QThread (or asyncio-only with qasync, but QThread is simpler) |
| SVG/PNG icons | Asset management, HiDPI variants | Unicode emoji (🏠🔍🛠️📋⚠️✅) or Qt built-in icons |

---

## Summary: widgets used in the entire app

| Widget | Count | Purpose |
|--------|-------|---------|
| `QMainWindow` | 1 | App shell |
| `QStackedWidget` | 2 | Main content pages + coding sub-tabs |
| `QPushButton` | ~25 | Nav, connect, write, clear, back, actions |
| `QLabel` | ~60 | Text everywhere, icons, status |
| `QVBoxLayout` / `QHBoxLayout` | ~30 | Layout |
| `QScrollArea` | 8 | Every list: DTCs, history, ECUs, categories, options, backups |
| `QDialog` | 2 | Add service entry, write-confirmation |
| `QCheckBox` | ~15 | Service form checkboxes |
| `QRadioButton` | ~10 | Coding option selections |
| `QLineEdit` | ~5 | Hex input, search, notes |
| `QDateEdit` | 2 | Service form date pickers |
| `QSpinBox` | 2 | Service form mileage |
| `QThread` subclass | ~6 | One per car operation type |

No custom widgets. No QAbstractItemModel. No QML. No OpenGL.