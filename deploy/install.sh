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

echo "== код: последний выпуск (сервер ходит по выпускам, как игроки)"
git fetch --tags --quiet origin
LATEST=$(git tag -l 'v*' --sort=-v:refname | head -1)
[[ -n "$LATEST" ]] && git -c advice.detachedHead=false checkout --quiet "$LATEST" && echo "версия $LATEST"
# дальше — install.sh из этого выпуска, а не тот, что уже читает bash (старый не знает новых шагов)
if [[ -z "${SG_REEXEC:-}" ]]; then
  SG_REEXEC=1 exec bash deploy/install.sh "$@"
fi

echo "== система: все обновления (образ Lightsail старее последних исправлений безопасности)"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get -y -q full-upgrade

echo "== пакеты: Caddy, файрвол, автообновления безопасности"
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
install -m 644 deploy/spellgunners-update.service /etc/systemd/system/spellgunners-update.service
install -m 644 deploy/spellgunners-update.timer /etc/systemd/system/spellgunners-update.timer
systemctl daemon-reload
systemctl enable spellgunners.service
systemctl restart spellgunners.service             # уже работал — перезапуск, чтобы взять новый код
systemctl enable --now spellgunners-backup.timer
systemctl enable --now spellgunners-update.timer       # новый выпуск — сам, когда никто не играет

echo "== сайт: страница и браузерная версия этого выпуска"
bash deploy/site.sh "${LATEST:-}" || echo "сайт не разложен — проверьте связь с GitHub"

echo "== Caddy: https/wss и сайт для $DOMAIN"
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
[[ -f /var/run/reboot-required ]] && echo "ВНИМАНИЕ: обновилось ядро — перезагрузите машину: sudo reboot (сервер поднимется сам)"
echo "готово. Проверка сервера:  curl -s http://127.0.0.1:5557/health"
echo "адрес для игры:            wss://$DOMAIN/"
