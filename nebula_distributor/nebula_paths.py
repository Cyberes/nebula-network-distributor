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
        self.stubs = stub(Path(self.configs / 'stubs'))
        self.firewalls = stub(Path(self.configs / 'firewalls'))
        self.certs = Path(self.root / 'certs')

        self.stubs.base = Path(self.stubs, 'base.yaml')
        self.stubs.default = Path(self.stubs, 'default.yaml')
        self.stubs.host_base = Path(self.stubs, 'host-base.yaml')
        self.stubs.lighthouse_base = Path(self.stubs, 'lighthouse-base.yaml')

    def __repr__(self):
        items = (f"{k}={v!r}" for k, v in self.__dict__.items())
        return "{}({})".format(type(self).__name__, ", ".join(items))
