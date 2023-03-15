#!/bin/sh /etc/rc.common
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
}
