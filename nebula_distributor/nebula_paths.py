from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Union, Any


class stub(SimpleNamespace):
    sub_paths = {}

    def __init__(self, root_path: Union[str, Path], **kwargs: Any):
        super().__init__(**kwargs)
        self.path = Path(root_path)

    def __fspath__(self):
        return str(self.path)

    def __str__(self):
        return self.__fspath__()

    def __repr__(self):
        return self.__fspath__()


class NebulaPaths:
    def __init__(self, files_root: Union[str, Path]):
        self.root = Path(files_root)
        self.configs = Path(self.root / 'configs')
        self.base_configs = stub(Path(self.configs / 'base'))
        self.firewalls = stub(Path(self.configs / 'firewall'))
        self.extras = stub(Path(self.configs / 'extra'))
        self.overrides = stub(Path(self.configs / 'override'))
        self.certs = Path(self.root / 'certs')

        self.base_configs.base = Path(self.base_configs, 'base.yaml')
        self.base_configs.default = Path(self.base_configs, 'default.yaml')
        self.base_configs.host_base = Path(self.base_configs, 'host-base.yaml')
        self.base_configs.lighthouse_base = Path(self.base_configs, 'lighthouse-base.yaml')

    def __repr__(self):
        items = (f"{k}={v!r}" for k, v in self.__dict__.items())
        return "{}({})".format(type(self).__name__, ", ".join(items))
