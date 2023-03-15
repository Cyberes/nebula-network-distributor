# nebula-network-distributor

_An easy way to distribute configs and certs to your Nebula network._

I run a [Nebula network](https://github.com/slackhq/nebula) with over a dozen hosts. That's enough that it's tedious to
manually configure each one but not enough to warrant something like Ansible.

I wrote this simple tool to construct configs from premade templates and push them out to the hosts.

### Features

- Automated installation of new configs and keys.
- Automated signing of new keys.
- Automatically reload the host's Nebula service.
- Daemon service to run as a server.
- Securely store your sudo passwords using your operating system's keyring.

## Install

```bash
pip install -r requirements.txt
```

Make sure you have these libraries installed. They should come with your OS but I manually built Python3.10 so I didn't
have them.

```bash
sudo python3 -m pip install --force-reinstall --no-cache-dir netifaces
sudo python3 -m pip install --force-reinstall --no-cache-dir secretstorage
```

If you're getting the error `a terminal is required to read the password` try this:

```bash
 sudo visudo

 dpanzer ALL = NOPASSWD: /bin/echo
 dpanzer ALL = NOPASSWD: /usr/bin/tee
```

## Use

- Firewall settings are in `files/configs/firewalls`. The root key is the name of the group you want this to apply to.
- Config base stubs are in  `files/configs/base_configs`.
    - `base.yaml` is applied to all hosts.
    - `default.yaml` is Nebula's default config, not used.
    - `host-base.yaml` is applied to all non-lighthouse hosts.
    - `lighthouse-base.yaml` is applied to all lighthouse hosts.

Copy `config.sample.yml` to `config.yml` and fill out the details.

Overrides can either be linked to group names or filenames specified in `overrides`. If you specify a filename
in `overrides` then that file will be loaded and the root group keys will be ignored (all groups in the override file
will be added to overrides).

Extras are used to add extra config items to a host based on group membership. All applicable extras for a host will be
merged together before applying to the host's config file, so make sure there
aren't any duplicate keys in your extras for a host. Then the extras will be merged into the host's config, replacing
values.

Don't use extras or overrides for firewalls. There's a specific folder for firewalls to be applied per-group.

Then run it with:

```bash
./distributor.py
```

To generate and install certs, do this:

```bash
./distributor.py --generate-certs
```

## OpenWRT

```bash
opkg update
opkg install nebula bash tar gzip sed
```

```yaml
arch: none
init: openwrt
```

`/usr/bin/hostname`

```bash
#!/bin/bash
cat /proc/sys/kernel/hostname
```