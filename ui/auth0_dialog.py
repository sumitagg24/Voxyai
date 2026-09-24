"""
Voxylis - Auth0 login dialog (OAuth device authorization flow).

Designed for a desktop app: no client secret is needed (public Native
application in Auth0 with the Device Code grant enabled). The user confirms
in their browser, this dialog polls Auth0, then exchanges the ID token with
the Voxylis backend for a regular Voxylis session.
"""

import requests
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import (
    QApplication,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
)


class _DevicePollWorker(QThread):
    approved = pyqtSignal(dict)  # token response containing id_token
    failed = pyqtSignal(str)

    def __init__(self, domain, client_id, device_code, interval, parent=None):
        super().__init__(parent)
        self.domain = domain
        self.client_id = client_id
        self.device_code = device_code
        self.interval = max(5, int(interval or 5))

    def run(self):
        import time

        wait = self.interval
        deadline = time.time() + 10 * 60
        while time.time() < deadline:
            if self.isInterruptionRequested():
                return
            time.sleep(wait)
            if self.isInterruptionRequested():
                return
            try:
                r = requests.post(
                    f"https://{self.domain}/oauth/token",
                    json={
                        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                        "device_code": self.device_code,
                        "client_id": self.client_id,
                    },
                    timeout=20,
                )
                data = r.json()
            except Exception:
                continue  # transient network error — keep polling
            if data.get("id_token"):
                self.approved.emit(data)
                return
            err = data.get("error", "")
            if err in ("authorization_pending", ""):
                continue
            if err == "slow_down":
                wait += 5
                continue
            if err == "expired_token":
                self.failed.emit("Code expired. Please try again.")
                return
            if err == "access_denied":
                self.failed.emit("Login was denied in the browser.")
                return
            self.failed.emit(data.get("error_description") or err or "Login failed.")
            return
        self.failed.emit("Login timed out. Please try again.")


class Auth0LoginDialog(QDialog):
    """Modal Auth0 login. On success, `result_data` holds the backend session."""

    def __init__(self, parent, api_base, desktop_client_id=None):
        super().__init__(parent)
        self.api_base = (api_base or "").rstrip("/")
        self.domain = ""
        self.client_id = desktop_client_id or ""
        self.device_code = ""
        self.result_data = None
        self.worker = None

        self.setWindowTitle("Sign in with Auth0")
        self.setModal(True)
        self.resize(380, 300)

        root = QVBoxLayout(self)
        root.setSpacing(10)

        self.title = QLabel("Sign in to Voxylis")
        self.title.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.title.setAlignment(Qt.AlignCenter)
        root.addWidget(self.title)

        self.hint = QLabel("Enter this code in the browser window\n" "that opens (or open the link manually):")
        self.hint.setAlignment(Qt.AlignCenter)
        self.hint.setWordWrap(True)
        root.addWidget(self.hint)

        self.code_label = QLabel("…")
        self.code_label.setAlignment(Qt.AlignCenter)
        self.code_label.setStyleSheet(
            "font-size: 30px; font-weight: bold; letter-spacing: 6px; "
            "padding: 10px; border: 1px solid #555; border-radius: 6px;"
        )
        self.code_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        root.addWidget(self.code_label)

        self.link_label = QLabel("")
        self.link_label.setAlignment(Qt.AlignCenter)
        self.link_label.setWordWrap(True)
        self.link_label.setOpenExternalLinks(True)
        self.link_label.setStyleSheet("color: #aaaaff; font-size: 11px;")
        root.addWidget(self.link_label)

        row = QHBoxLayout()
        self.browser_btn = QPushButton("Open browser")
        self.browser_btn.clicked.connect(self._open_browser)
        self.browser_btn.setEnabled(False)
        row.addWidget(self.browser_btn)
        self.copy_btn = QPushButton("Copy code")
        self.copy_btn.clicked.connect(self._copy_code)
        self.copy_btn.setEnabled(False)
        row.addWidget(self.copy_btn)
        root.addLayout(row)

        self.status = QLabel("Contacting Auth0…")
        self.status.setAlignment(Qt.AlignCenter)
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color: #888; font-size: 11px;")
        root.addWidget(self.status)

        btns = QHBoxLayout()
        btns.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        btns.addWidget(cancel)
        root.addLayout(btns)

        self.verify_uri = ""
        QTimer.singleShot(0, self._start)

    # ── flow ──────────────────────────────────────────────────────────

    def _start(self):
        try:
            if not self.client_id:
                cfg = requests.get(f"{self.api_base}/api/auth/auth0/config", timeout=10).json()
                if not cfg.get("enabled"):
                    self.status.setText(
                        "Auth0 is not configured on the server.\n"
                        "Set AUTH0_DOMAIN and AUTH0_CLIENT_ID in the backend .env."
                    )
                    return
                self.domain = cfg["domain"]
                self.client_id = cfg.get("desktopClientId") or cfg["clientId"]
            else:
                # Domain still comes from the backend config.
                cfg = requests.get(f"{self.api_base}/api/auth/auth0/config", timeout=10).json()
                self.domain = cfg.get("domain", "")
            if not self.domain or not self.client_id:
                self.status.setText("Auth0 is not configured on the server.")
                return

            r = requests.post(
                f"https://{self.domain}/oauth/device/code",
                json={
                    "client_id": self.client_id,
                    "scope": "openid profile email",
                },
                timeout=15,
            )
            data = r.json()
            if r.status_code != 200 or not data.get("device_code"):
                self.status.setText(
                    "Auth0 refused the request: "
                    + str(data.get("error_description") or data.get("error") or r.status_code)
                )
                return

            self.device_code = data["device_code"]
            self.verify_uri = data.get("verification_uri_complete") or data.get("verification_uri", "")
            self.code_label.setText(data.get("user_code", "…"))
            if self.verify_uri:
                self.link_label.setText(f'<a href="{self.verify_uri}" style="color:#aaaaff;">{self.verify_uri}</a>')
            self.browser_btn.setEnabled(True)
            self.copy_btn.setEnabled(True)
            self.status.setText("Waiting for browser approval…")
            self._open_browser()

            self.worker = _DevicePollWorker(
                self.domain,
                self.client_id,
                self.device_code,
                data.get("interval", 5),
                self,
            )
            self.worker.approved.connect(self._on_approved)
            self.worker.failed.connect(self._on_failed)
            self.worker.start()
        except Exception as e:
            self.status.setText(f"Could not reach login services: {e}")

    def _open_browser(self):
        if self.verify_uri:
            QDesktopServices.openUrl(QUrl(self.verify_uri))

    def _copy_code(self):
        QApplication.clipboard().setText(self.code_label.text().strip())
        self.status.setText("Code copied — paste it in the browser.")

    def _on_failed(self, message):
        self.status.setText(message)

    def _on_approved(self, tokens):
        self.status.setText("Browser approved — creating Voxylis session…")
        try:
            r = requests.post(
                f"{self.api_base}/api/auth/auth0",
                json={"id_token": tokens["id_token"]},
                timeout=20,
            )
            data = r.json()
        except Exception as e:
            self.status.setText(f"Backend unreachable: {e}")
            return
        if r.status_code != 200 or not data.get("session_id"):
            self.status.setText("Backend rejected the login: " + str(data.get("error") or r.status_code))
            return
        self.result_data = {
            "email": data.get("email_or_phone", ""),
            "name": data.get("name", ""),
            "session_id": data["session_id"],
            "tier": data.get("tier", "free"),
            "role": data.get("role", "user"),
        }
        self.accept()

    def reject(self):
        try:
            if self.worker and self.worker.isRunning():
                self.worker.requestInterruption()
                self.worker.wait(2000)
        except Exception:
            pass
        super().reject()
