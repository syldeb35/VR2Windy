import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
LAUNCHER_NAME = "vr2windy-proxy.desktop"


def desktop_string(value):
    return (str(value).replace("\\", "\\\\").replace("\n", "\\n")
            .replace("\t", "\\t").replace("\r", "\\r"))


def exec_argument(value):
    value = str(value).replace("%", "%%")
    for character in ('\\', '"', '$', '`'):
        value = value.replace(character, '\\' + character)
    return desktop_string(f'"{value}"')


def install_launcher(data_home, python_executable, project_root):
    if not data_home.is_absolute():
        raise ValueError("XDG_DATA_HOME must be an absolute path")
    script = project_root / "proxy_control.py"
    icon = project_root / "proxy_icon.png"
    for path in (script, icon):
        if not path.is_file():
            raise FileNotFoundError(f"Required file not found: {path}")

    applications = data_home / "applications"
    applications.mkdir(parents=True, exist_ok=True)
    launcher = applications / LAUNCHER_NAME
    content = (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=VR2Windy Proxy\n"
        "Comment=Contrôle du proxy NMEA VR2Windy\n"
        f"Exec={exec_argument(python_executable)} {exec_argument(script)}\n"
        f"Icon={desktop_string(icon)}\n"
        "Terminal=false\n"
        "StartupWMClass=Vr2windy proxy\n"
        "Categories=Application;Maps;Navigation\n"
        "Keywords=virtual;regatta;router\n"
    )
    launcher.write_text(content, encoding="utf-8")
    return launcher


def main():
    data_home = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
    try:
        launcher = install_launcher(data_home, Path(sys.executable).absolute(), ROOT)
    except (OSError, ValueError) as error:
        print(f"Impossible d'installer le lanceur : {error}", file=sys.stderr)
        return 1
    print(f"Lanceur installé : {launcher}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
