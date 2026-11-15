#!/bin/sh
set -e
/firewall/apply.sh web
exec nginx -g 'daemon off;'
