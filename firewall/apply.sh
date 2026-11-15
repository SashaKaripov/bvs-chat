#!/bin/sh
set -eu

if [ "$#" -ne 1 ]; then
  echo "usage: apply.sh <web|chat-api|worker>" >&2
  exit 1
fi

ROLE=$1
case "$ROLE" in
  web|chat-api|worker) ;;
  *)
    echo "unknown role: $ROLE" >&2
    exit 1
    ;;
esac

RULES_PATH=${RULES_PATH:-/firewall/rules.conf}

iptables -F OUTPUT
iptables -P OUTPUT DROP
iptables -A OUTPUT -o lo -j ACCEPT

if ! iptables -A OUTPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT 2>/dev/null; then
  iptables -A OUTPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
fi

for proto in udp tcp; do
  iptables -A OUTPUT -p "$proto" -d 127.0.0.11 --dport 53 -j ACCEPT
done

lookup() {
  getent hosts "$1" 2>/dev/null | while read -r addr rest; do
    case "$addr" in
      *:*) continue ;;
    esac
    echo "$addr"
    break
  done
  return 0
}

resolve() {
  n=0
  while [ "$n" -lt "$2" ]; do
    ip=$(lookup "$1") || true
    if [ -n "$ip" ]; then
      echo "$ip"
      return 0
    fi
    n=$((n + 1))
    if [ "$n" -lt "$2" ]; then
      sleep 1
    fi
  done
  return 1
}

add() {
  if [ "$1" = deny ]; then
    target=REJECT
  else
    target=ACCEPT
  fi
  if [ "$3" = any ]; then
    iptables -A OUTPUT -p "$2" --dport "$4" -j "$target"
    return 0
  fi
  if [ "$1" = deny ]; then
    ip=$(resolve "$3" 1) || return 0
  else
    ip=$(resolve "$3" 30) || exit 1
  fi
  iptables -A OUTPUT -p "$2" -d "$ip" --dport "$4" -j "$target"
}

pass() {
  want=$1
  current=
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    set -- $line
    case "$1" in
      role) current=$2 ;;
      "$want")
        if [ "$current" = "$ROLE" ]; then
          add "$1" "$2" "$3" "$4"
        fi
        ;;
    esac
  done < "$RULES_PATH"
}

pass deny
pass allow

if command -v ip6tables >/dev/null 2>&1; then
  ip6tables -F OUTPUT
  ip6tables -P OUTPUT DROP
  ip6tables -A OUTPUT -o lo -j ACCEPT
fi

echo "firewall role $ROLE applied" >&2
