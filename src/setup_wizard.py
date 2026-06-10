import sys
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
    QTextEdit, QPushButton, QFrame
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal
from PySide6.QtGui import QFont, QColor


class SetupWorker(QThread):
    log_msg = Signal(str)
    step_progress = Signal(int)
    step_finished = Signal(bool)

    def __init__(self, step_func, *args, **kwargs):
        super().__init__()
        self.step_func = step_func
        self.args = args
        self.kwargs = kwargs

    def run(self):
        def log_cb(msg):
            self.log_msg.emit(msg)

        def prog_cb(pct):
            self.step_progress.emit(pct)

        result = self.step_func(log_callback=log_cb, progress_callback=prog_cb, *self.args, **self.kwargs)
        self.step_finished.emit(result)


class SetupWizard(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("NEXUS — Configuracion Inicial")
        self.setFixedSize(520, 420)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self._success = False
        self._current_step = 0
        self._steps = []
        self._build_steps()
        self._setup_ui()
        self._run_next_step()

    def _build_steps(self):
        steps = []
        if not getattr(sys, 'frozen', False):
            steps.append(("Instalando dependencias pip...", self._run_pip_install))
        steps.append(("Descargando datos iniciales...", self._run_download))
        steps.append(("Extrayendo archivos...", self._run_extract))
        self._steps = steps

    def _setup_ui(self):
        self.setStyleSheet("""
            QDialog { background-color: #0c101a; }
            QLabel { color: #e2e8f0; }
            QProgressBar {
                border: 1px solid #1e293b; border-radius: 4px;
                background-color: #1e293b; text-align: center;
                color: #e2e8f0; height: 22px;
            }
            QProgressBar::chunk {
                background-color: #e63946; border-radius: 3px;
            }
            QTextEdit {
                background-color: #05080f; color: #94a3b8;
                border: 1px solid #1e293b; border-radius: 4px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 12px;
            }
            QPushButton {
                background-color: #1e293b; color: #e2e8f0;
                border: 1px solid #334155; border-radius: 4px;
                padding: 8px 20px; font-weight: bold;
            }
            QPushButton:hover { background-color: #334155; }
            QPushButton:disabled { color: #475569; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        title = QLabel("NEXUS — Primer Arranque")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title.setStyleSheet("color: #e63946;")
        layout.addWidget(title)

        self.lbl_step = QLabel("Preparando...")
        self.lbl_step.setFont(QFont("Segoe UI", 11))
        layout.addWidget(self.lbl_step)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(180)
        layout.addWidget(self.log_view, 1)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)

    def _log(self, msg):
        self.log_view.append(msg)
        self.log_view.verticalScrollBar().setValue(
            self.log_view.verticalScrollBar().maximum()
        )

    def _run_next_step(self):
        if self._current_step >= len(self._steps):
            self._on_all_done()
            return

        label, func = self._steps[self._current_step]
        self.lbl_step.setText(f"Paso {self._current_step + 1}/{len(self._steps)}: {label}")
        self.progress.setValue(0)
        self._log(f"--- {label} ---")
        func()

    def _run_pip_install(self):
        from setup import instalar_dependencias
        self._run_worker(instalar_dependencias)

    def _run_download(self):
        from setup import descargar_datos
        self._run_worker(descargar_datos)

    def _run_extract(self):
        from setup import extraer_datos
        self._run_worker(extraer_datos)

    def _run_worker(self, func):
        self.worker = SetupWorker(func)
        self.worker.log_msg.connect(self._log)
        self.worker.step_progress.connect(self.progress.setValue)
        self.worker.step_finished.connect(self._on_step_finished)
        self.btn_cancel.setEnabled(False)
        self.worker.start()

    def _on_step_finished(self, success):
        self.btn_cancel.setEnabled(True)
        self.progress.setValue(100)
        if not success:
            self._log("ERROR: El paso fallo. Verifica tu conexion e intenta de nuevo.")
            self.lbl_step.setText("Error en la configuracion")
            self.lbl_step.setStyleSheet("color: #e63946;")
            return

        self._current_step += 1
        QTimer.singleShot(300, self._run_next_step)

    def _on_all_done(self):
        self._success = True
        self._log("\nConfiguracion inicial completada.")
        self.lbl_step.setText("Todo listo.")
        self.lbl_step.setStyleSheet("color: #22c55e;")
        self.btn_cancel.setText("Iniciar NEXUS")
        self.btn_cancel.clicked.disconnect()
        self.btn_cancel.clicked.connect(self.accept)

    @property
    def success(self):
        return self._success
