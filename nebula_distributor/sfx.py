import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Union


def create_installer_archive(hostname: str, output: Union[str, Path], config_path: Union[str, Path], host_key_path: Union[str, Path], host_crt_path: Union[str, Path], ca_crt_path: Union[str, Path], nebula_files: str, init_type: str, keep_nebula_crt: bool = False):
    tmp_script = str(tempfile.mkstemp()[1])
    tmp_dir = Path(tempfile.mkdtemp())
    tmp_archive_dir = Path(tempfile.mkdtemp())

    os.mkdir(tmp_dir / 'etc')

    if nebula_files:
        shutil.copytree(nebula_files, tmp_dir / 'nebula')
        if not keep_nebula_crt:
            os.remove(tmp_dir / 'nebula' / 'nebula-cert')
        mv_nebula_str = 'mv $TMP/nebula/* /usr/sbin'
    else:
        mv_nebula_str = ''
    shutil.copy(config_path, tmp_dir / 'etc' / 'config.yaml')
    shutil.copy(host_key_path, tmp_dir / 'etc' / 'host.key')
    shutil.copy(host_crt_path, tmp_dir / 'etc' / 'host.crt')
    shutil.copy(ca_crt_path, tmp_dir / 'etc' / 'ca.crt')

    # /usr/local/bin/

    sfx_file = f"""#!/bin/bash
if [[ $EUID -ne 0 ]]; then
  echo "This script must be run as root."
  exit 1
fi

# ps h -p $$ -o args='' | cut -f1 -d' ' | grep 'bash' &> /dev/null
# if [ $? != 0 ]; then
#    echo "This must be run in bash!"
#    exit 1
# fi

TMP=$(mktemp -d)
echo "Extracting archive to $TMP"
sed '0,/^#EOF#$/d' $0 | tar xzv -C "$TMP"

echo "Copying files..."
mkdir -p /etc/nebula/
{mv_nebula_str}
mv $TMP/etc/* /etc/nebula/"""

    if init_type == 'systemd':
        sfx_file = sfx_file + """echo "Setting up service..."
echo '''[Unit]
Description=nebula
Wants=basic.target
After=basic.target network.target
Before=sshd.service

[Service]
SyslogIdentifier=nebula
ExecReload=/bin/kill -HUP $MAINPID
ExecStart=/usr/sbin/nebula -config /etc/nebula/config.yaml
Restart=always
RestartSec=2
StartLimitIntervalSec=1
StartLimitBurst=2000

[Install]
WantedBy=multi-user.target''' > /etc/systemd/system/nebula.service

systemctl daemon-reload
systemctl enable nebula
systemctl start nebula
systemctl restart nebula
sleep 3
systemctl status nebula"""
    elif init_type == 'initd':
        sfx_file = sfx_file + """\n????"""
    elif init_type == 'openwrt':
        sfx_file = sfx_file + """\necho '''#!/bin/sh /etc/rc.common
START=50
USE_PROCD=1

start_service() {
  procd_open_instance
  procd_set_param command /usr/sbin/nebula -config /etc/nebula/config.yaml
  procd_set_param respawn ${respawn_threshold:-3600} ${respawn_timeout:-5} ${respawn_retry:-5}
  procd_set_param stdout 1
  procd_set_param stderr 1
  procd_set_param pidfile /var/run/nebula.pid
  procd_close_instance
}''' > /etc/init.d/nebula"""
    elif init_type == False:
        pass
    else:
        raise Exception(f'Init type "{init_type}" not found!')

    sfx_file = sfx_file + """\necho "Cleaning up..."
rm -rf $TMP
echo "All done!"
exit 0
#EOF#
"""
    f = open(tmp_script, 'w')
    f.write(sfx_file)
    f.close()

    subprocess.run(f'cd "{tmp_dir}" && tar -czvf "{tmp_archive_dir / "data.tar.gz"}" .', shell=True)
    subprocess.run(f'cat "{tmp_script}" "{tmp_archive_dir / "data.tar.gz"}" > "{os.path.join(output, hostname + "-installer.run")}"', shell=True)

    os.remove(tmp_script)
    shutil.rmtree(tmp_archive_dir)  # shutil.rmtree(tmp_dir)
