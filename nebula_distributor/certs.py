import os
import subprocess
from pathlib import Path
from typing import Union, Tuple


class NebulaCerts:
    def __init__(self, ca_cert: Union[str, Path], ca_key: Union[str, Path], out_dir: Union[str, Path], subnet_size: int, nebula_exe_path: Union[str, Path] = None):
        self.ca_cert = Path(ca_cert)
        self.ca_key = Path(ca_key)
        self.out_dir = Path(out_dir)
        self.subnet_size = subnet_size
        if nebula_exe_path is None:
            self.nebula_exe_path = 'nebula-cert'
        else:
            self.nebula_exe_path = Path(nebula_exe_path)
            assert self.nebula_exe_path.exists()

        assert self.ca_cert.exists()
        assert self.ca_key.exists()
        assert self.out_dir.exists()

    def create_new(self, name: str, type: str, ip: str, groups: Union[list, str] = list, overwrite: bool = False) -> Tuple[Path, Path]:
        if isinstance(groups, str):
            groups = [groups]
        if len(groups) > 0:
            groups_arg = f'-groups {" ".join(groups)}'
        else:
            groups_arg = ''
        out_cert = self.out_dir / f'{type}-{name}.crt'
        out_key = self.out_dir / f'{type}-{name}.key'

        if overwrite:
            os.remove(out_cert) if out_cert.exists() else None
            os.remove(out_key) if out_key.exists() else None

        cmd = f'{self.nebula_exe_path} sign -name "{name}" -ip "{ip}/{self.subnet_size}" -ca-crt "{self.ca_cert}" -ca-key "{self.ca_key}" -out-crt "{out_cert}" -out-key "{out_key}" {groups_arg}'
        s = subprocess.run(cmd, shell=True)
        return out_cert, out_key

    def read_host_certs(self, hostname: Union[str, Path], type: Union[str, Path]) -> Tuple[Path, str, Path, str]:
        crt = self.out_dir / f'{type}-{hostname}.crt'
        key = self.out_dir / f'{type}-{hostname}.key'
        return crt, self.read_file(crt), key, self.read_file(key)

    def read_ca_crt(self) -> Tuple[Path, str]:
        return self.ca_cert, self.read_file(self.ca_cert)

    def read_file(self, file_path: Union[str, Path]):
        file_path = Path(file_path)
        return None if not file_path.exists() else file_path.read_text()
