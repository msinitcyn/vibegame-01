#!/usr/bin/env bash
# Обновить сервер на последний выпуск СЕЙЧАС (не дожидаясь, пока все выйдут):
#   sudo bash /opt/spellgunners/deploy/update.sh
# Обычно не нужно: spellgunners-update.timer делает это сам, когда на сервере никто не играет.
set -euo pipefail
cd /opt/spellgunners
git fetch --tags --quiet origin
latest=$(git tag -l 'v*' --sort=-v:refname | head -1)
git -c advice.detachedHead=false checkout --quiet "$latest"
echo "версия $latest"
systemctl restart spellgunners.service
sleep 2
curl -s http://127.0.0.1:5557/health || true
systemctl --no-pager --lines=5 status spellgunners.service || true
