#!/usr/bin/env bash
# Ключ пишется только в .env с правами 600. В вывод его не класть.
set +x
set -euo pipefail

cd "$(cd "$(dirname "$0")/.." && pwd)"

tmp=""
cleanup() {
  if [[ -n "${tmp}" && -f "${tmp}" ]]; then
    rm -f "${tmp}"
  fi
}
trap cleanup EXIT

write_env=1
existing_line=""
existing_value=""
if [[ -f .env ]]; then
  existing_line="$(grep -m 1 -E '^OPENROUTER_API_KEY=' .env || true)"
  existing_value="${existing_line#*=}"
  existing_value="${existing_value%$'\r'}"
  existing_value="${existing_value#"${existing_value%%[![:space:]]*}"}"
  existing_value="${existing_value%"${existing_value##*[![:space:]]}"}"
  if [[ -n "${existing_line}" && -n "${existing_value}" ]]; then
    write_env=0
  fi
fi
unset existing_line existing_value

if [[ "${write_env}" -eq 1 ]]; then
  key_file="/Users/bonis/Downloads/gpt-bot/openrouter_key.txt"
  key=""
  if [[ -f "${key_file}" && -r "${key_file}" ]]; then
    if grep -q -E '^OPENROUTER_API_KEY=' "${key_file}"; then
      key_line="$(grep -m 1 -E '^OPENROUTER_API_KEY=' "${key_file}" || true)"
      key="${key_line#*=}"
      unset key_line
    else
      key="$(tr -d '\r' < "${key_file}")"
    fi
    key="${key%$'\r'}"
    key="${key#"${key%%[![:space:]]*}"}"
    key="${key%"${key##*[![:space:]]}"}"
  fi
  if [[ -z "${key}" ]]; then
    echo "Положи ключ в .env как OPENROUTER_API_KEY" >&2
    exit 1
  fi
  umask 077
  tmp="$(mktemp)"
  printf 'OPENROUTER_API_KEY=%s\nCHAT_MODEL=openai/gpt-4o-mini\n' "${key}" > "${tmp}"
  chmod 600 "${tmp}"
  mv "${tmp}" .env
  tmp=""
  chmod 600 .env
  unset key key_file
fi

docker compose up -d --build
