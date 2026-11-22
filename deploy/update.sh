#!/usr/bin/env bash
# Обновить сервер до последней версии с GitHub и перезапустить:  sudo bash /opt/spellgunners/deploy/update.sh
set -euo pipefail
cd /opt/spellgunners
git pull --ff-only
systemctl restart spellgunners.service
sleep 2
curl -s http://127.0.0.1:5557/health || true
systemctl --no-pager --lines=5 status spellgunners.service || true
