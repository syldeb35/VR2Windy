import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.install_proxy_launcher import exec_argument, install_launcher


ROOT = Path(__file__).resolve().parents[1]


class ProxyLauncherTests(unittest.TestCase):
    def test_installs_launcher_with_real_paths_and_window_class(self):
        with tempfile.TemporaryDirectory() as temporary:
            data_home = Path(temporary) / "data with spaces"
            launcher = install_launcher(data_home, Path(sys.executable), ROOT)
            content = launcher.read_text(encoding="utf-8")
            self.assertIn(f"Exec={exec_argument(sys.executable)} {exec_argument(ROOT / 'proxy_control.py')}\n", content)
            self.assertIn(f"Icon={ROOT / 'proxy_icon.png'}\n", content)
            self.assertIn("StartupWMClass=Vr2windy proxy\n", content)
            self.assertIn("Terminal=false\n", content)

    def test_exec_argument_escapes_desktop_entry_special_characters(self):
        self.assertEqual(exec_argument('/a b/$x%/a"b'), '"/a b/\\\\$x%%/a\\\\"b"')

    def test_missing_icon_does_not_create_launcher(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / "proxy_control.py").touch()
            with self.assertRaises(FileNotFoundError):
                install_launcher(directory / "data", Path(sys.executable), directory)
            self.assertFalse((directory / "data/applications").exists())

    def test_relative_data_home_is_rejected(self):
        with self.assertRaises(ValueError):
            install_launcher(Path("relative"), Path(sys.executable), ROOT)

    def test_cli_writes_valid_launcher_to_xdg_data_home(self):
        with tempfile.TemporaryDirectory() as temporary:
            environment = {**os.environ, "XDG_DATA_HOME": temporary}
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts/install_proxy_launcher.py")],
                env=environment, capture_output=True, text=True, check=True,
            )
            launcher = Path(temporary) / "applications/vr2windy-proxy.desktop"
            self.assertTrue(launcher.is_file())
            self.assertIn(str(launcher), result.stdout)
            if subprocess.run(["sh", "-c", "command -v desktop-file-validate"],
                              capture_output=True).returncode == 0:
                subprocess.run(["desktop-file-validate", str(launcher)], check=True)


if __name__ == "__main__":
    unittest.main()
