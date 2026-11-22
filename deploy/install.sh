#!/usr/bin/env bash
# Установка сервера Spellgunners на чистую Ubuntu (24.04): служба, Caddy с сертификатом, файрвол, копии базы.
#   sudo git clone https://github.com/msinitcyn/vibegame-01 /opt/spellgunners
#   cd /opt/spellgunners && sudo bash deploy/install.sh имя.duckdns.org
# Повторный запуск безопасен (обновит настройки). Подробно — docs/deploy-aws.md.
set -euo pipefail

DOMAIN="${1:-}"
if [[ -z "$DOMAIN" ]]; then
  echo "нужен домен: sudo bash deploy/install.sh имя.duckdns.org" >&2
  exit 1
fi
if [[ $EUID -ne 0 ]]; then
  echo "запустите через sudo" >&2
  exit 1
fi
cd "$(dirname "$0")/.."
SRC="$(pwd)"
if [[ "$SRC" != "/opt/spellgunners" ]]; then
  echo "код должен лежать в /opt/spellgunners (сейчас $SRC)" >&2
  exit 1
fi

echo "== пакеты: Caddy, файрвол, автообновления безопасности"
apt-get update -q
apt-get install -y -q caddy ufw unattended-upgrades python3
dpkg-reconfigure -f noninteractive unattended-upgrades || true

echo "== пользователь и папка данных"
id spellgunners >/dev/null 2>&1 || useradd --system --home /var/lib/spellgunners --shell /usr/sbin/nologin spellgunners
install -d -o spellgunners -g spellgunners -m 750 /var/lib/spellgunners

echo "== проверка: сервер запускается"
sudo -u spellgunners HOME=/var/lib/spellgunners python3 -c "import duel.server" || { echo "код не запускается" >&2; exit 1; }

echo "== служба сервера и копии базы"
install -m 644 deploy/spellgunners.service /etc/systemd/system/spellgunners.service
install -m 644 deploy/spellgunners-backup.service /etc/systemd/system/spellgunners-backup.service
install -m 644 deploy/spellgunners-backup.timer /etc/systemd/system/spellgunners-backup.timer
systemctl daemon-reload
systemctl enable --now spellgunners.service
systemctl enable --now spellgunners-backup.timer

echo "== Caddy: https/wss для $DOMAIN"
sed "s/__DOMAIN__/$DOMAIN/" deploy/Caddyfile.template > /etc/caddy/Caddyfile
systemctl enable caddy
systemctl reload caddy || systemctl restart caddy

echo "== файрвол: только SSH, 80 (сертификат) и 443 (игра)"
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

sleep 2
echo
systemctl --no-pager --lines=3 status spellgunners.service || true
echo
echo "готово. Проверка сервера:  curl -s http://127.0.0.1:5557/health"
echo "адрес для игры:            wss://$DOMAIN/"
