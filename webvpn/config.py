from pathlib import Path

from dynaconf import Dynaconf, loaders
from dynaconf.utils.boxing import DynaBox


def get_setting_path():
    config_dir = Path.home() / ".config" / "webvpn-py"
    if not config_dir.exists():
        config_dir.mkdir(parents=True)
    return config_dir / "settings.yaml"


settings = Dynaconf(
    envvar_prefix="WEBVPN",
    settings_files=[
        str(Path(__file__).parent / "settings.yaml"),
        str(get_setting_path())
    ],
)


def save_settings():
    config_dir = Path.home() / ".config" / "webvpn-py"
    if not config_dir.exists():
        config_dir.mkdir(parents=True)

    data = settings.as_dict()
    loaders.write(str(get_setting_path()), DynaBox(data).to_dict())
