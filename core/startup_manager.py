"""
Voxylis Startup Manager
Handles auto-startup on system boot and hotkey activation
"""

import sys
import platform
import subprocess
from pathlib import Path
from utils.logger import log_info, log_error, log_warning


class StartupManager:
    """Manages application startup and auto-launch"""

    def __init__(self):
        self.app_name = "Voxylis"
        self.system = platform.system().lower()
        self._update_app_path()

    def _update_app_path(self):
        """Set the correct path depending on source vs frozen."""
        if getattr(sys, "frozen", False):
            self.app_path = Path(sys.executable)
        else:
            self.app_path = Path(__file__).parent.parent / "start_voxylis.py"

    def enable_auto_startup(self) -> bool:
        """Enable auto-startup on system boot"""
        try:
            if self.system == "windows":
                return self._enable_windows_startup()
            elif self.system == "darwin":  # macOS
                return self._enable_macos_startup()
            elif self.system == "linux":
                return self._enable_linux_startup()
            else:
                log_warning(f"Auto-startup not supported on {self.system}")
                return False
        except Exception as e:
            log_error(f"Failed to enable auto-startup: {e}")
            return False

    def disable_auto_startup(self) -> bool:
        """Disable auto-startup on system boot"""
        try:
            if self.system == "windows":
                return self._disable_windows_startup()
            elif self.system == "darwin":  # macOS
                return self._disable_macos_startup()
            elif self.system == "linux":
                return self._disable_linux_startup()
            else:
                log_warning(f"Auto-startup not supported on {self.system}")
                return False
        except Exception as e:
            log_error(f"Failed to disable auto-startup: {e}")
            return False

    def is_auto_startup_enabled(self) -> bool:
        """Check if auto-startup is enabled"""
        try:
            if self.system == "windows":
                return self._check_windows_startup()
            elif self.system == "darwin":  # macOS
                return self._check_macos_startup()
            elif self.system == "linux":
                return self._check_linux_startup()
            else:
                return False
        except Exception as e:
            log_error(f"Failed to check auto-startup status: {e}")
            return False

    # ─── Windows Implementation ───

    def _enable_windows_startup(self) -> bool:
        """Enable Windows startup via registry"""
        try:
            import winreg

            # Create startup entry in registry
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE
            )

            if getattr(sys, "frozen", False):
                # Frozen exe — launch directly
                command = f'"{str(self.app_path.absolute())}" --minimized'
            else:
                # Source — launch via python
                command = f'"{sys.executable}" "{str(self.app_path.absolute())}" --minimized'

            winreg.SetValueEx(key, self.app_name, 0, winreg.REG_SZ, command)
            winreg.CloseKey(key)

            log_info("Windows auto-startup enabled")
            return True

        except ImportError:
            log_error("winreg module not available")
            return False
        except Exception as e:
            log_error(f"Windows startup error: {e}")
            return False

    def _disable_windows_startup(self) -> bool:
        """Disable Windows startup"""
        try:
            import winreg

            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE
            )

            try:
                winreg.DeleteValue(key, self.app_name)
                log_info("Windows auto-startup disabled")
                return True
            except FileNotFoundError:
                # Entry doesn't exist
                return True
            finally:
                winreg.CloseKey(key)

        except ImportError:
            log_error("winreg module not available")
            return False
        except Exception as e:
            log_error(f"Windows startup disable error: {e}")
            return False

    def _check_windows_startup(self) -> bool:
        """Check Windows startup status"""
        try:
            import winreg

            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ)

            try:
                value, _ = winreg.QueryValueEx(key, self.app_name)
                return bool(value)
            except FileNotFoundError:
                return False
            finally:
                winreg.CloseKey(key)

        except ImportError:
            return False
        except Exception:
            return False

    # ─── macOS Implementation ───

    def _enable_macos_startup(self) -> bool:
        """Enable macOS startup via LaunchAgent"""
        try:
            # Create LaunchAgent plist
            plist_dir = Path.home() / "Library" / "LaunchAgents"
            plist_dir.mkdir(exist_ok=True)

            plist_file = plist_dir / f"com.voxylis.{self.app_name.lower()}.plist"

            python_exe = sys.executable
            script_path = str(self.app_path.absolute())

            plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">  # noqa: E501
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.voxylis.{self.app_name.lower()}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python_exe}</string>
        <string>{script_path}</string>
        <string>--minimized</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
</dict>
</plist>"""

            plist_file.write_text(plist_content)

            # Load the LaunchAgent
            subprocess.run(["launchctl", "load", str(plist_file)], check=True)

            log_info("macOS auto-startup enabled")
            return True

        except Exception as e:
            log_error(f"macOS startup error: {e}")
            return False

    def _disable_macos_startup(self) -> bool:
        """Disable macOS startup"""
        try:
            plist_dir = Path.home() / "Library" / "LaunchAgents"
            plist_file = plist_dir / f"com.voxylis.{self.app_name.lower()}.plist"

            if plist_file.exists():
                # Unload the LaunchAgent
                subprocess.run(["launchctl", "unload", str(plist_file)], check=False)

                # Remove the plist file
                plist_file.unlink()

            log_info("macOS auto-startup disabled")
            return True

        except Exception as e:
            log_error(f"macOS startup disable error: {e}")
            return False

    def _check_macos_startup(self) -> bool:
        """Check macOS startup status"""
        try:
            plist_dir = Path.home() / "Library" / "LaunchAgents"
            plist_file = plist_dir / f"com.voxylis.{self.app_name.lower()}.plist"
            return plist_file.exists()
        except Exception:
            return False

    # ─── Linux Implementation ───

    def _enable_linux_startup(self) -> bool:
        """Enable Linux startup via .desktop file"""
        try:
            # Create autostart directory
            autostart_dir = Path.home() / ".config" / "autostart"
            autostart_dir.mkdir(parents=True, exist_ok=True)

            desktop_file = autostart_dir / f"{self.app_name.lower()}.desktop"

            python_exe = sys.executable
            script_path = str(self.app_path.absolute())

            desktop_content = f"""[Desktop Entry]
Type=Application
Name={self.app_name}
Comment=AI Voice Assistant
Exec={python_exe} {script_path} --minimized
Icon=microphone
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
"""

            desktop_file.write_text(desktop_content)
            desktop_file.chmod(0o755)

            log_info("Linux auto-startup enabled")
            return True

        except Exception as e:
            log_error(f"Linux startup error: {e}")
            return False

    def _disable_linux_startup(self) -> bool:
        """Disable Linux startup"""
        try:
            autostart_dir = Path.home() / ".config" / "autostart"
            desktop_file = autostart_dir / f"{self.app_name.lower()}.desktop"

            if desktop_file.exists():
                desktop_file.unlink()

            log_info("Linux auto-startup disabled")
            return True

        except Exception as e:
            log_error(f"Linux startup disable error: {e}")
            return False

    def _check_linux_startup(self) -> bool:
        """Check Linux startup status"""
        try:
            autostart_dir = Path.home() / ".config" / "autostart"
            desktop_file = autostart_dir / f"{self.app_name.lower()}.desktop"
            return desktop_file.exists()
        except Exception:
            return False

    # ─── Utility Methods ───

    def create_startup_script(self) -> Path:
        """Create a startup script for the application"""
        try:
            if getattr(sys, "frozen", False):
                run_cmd = f'"{str(self.app_path.absolute())}"'
            else:
                run_cmd = f'"{sys.executable}" "{str(self.app_path.absolute())}"'

            if self.system == "windows":
                script_path = Path.home() / "voxylis_startup.bat"
                script_content = f"""@echo off
cd /d "{self.app_path.parent}"
{run_cmd} --minimized
"""
            else:
                script_path = Path.home() / "voxylis_startup.sh"
                script_content = f"""#!/bin/bash
cd "{self.app_path.parent}"
{run_cmd} --minimized
"""

            script_path.write_text(script_content)

            if self.system != "windows":
                script_path.chmod(0o755)

            log_info(f"Startup script created: {script_path}")
            return script_path

        except Exception as e:
            log_error(f"Failed to create startup script: {e}")
            return None


# Global startup manager instance
startup_manager = StartupManager()
