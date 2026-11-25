#!/usr/bin/env bash
# Автообновление сервера на последний выпуск (тег vX.Y.Z на GitHub) — запускает spellgunners-update.timer
# раз в 10 минут. Сервер ходит строго по выпускам (не по master): у него то же, что у игроков.
# Новый выпуск ставится, когда на сервере никто не играет (страница состояния: игроков 0); если люди сидят
# дольше FORCE_AFTER — ставится всё равно (иначе сервер отстанет от игр насовсем). Лог — journalctl -t spellgunners-update.
set -uo pipefail
# переменные — для проверки скрипта на другой машине; на сервере — значения по умолчанию
cd "${SG_DIR:-/opt/spellgunners}" || exit 1
FORCE_AFTER=${SG_FORCE_AFTER:-$((6 * 3600))}
STATE=${SG_STATE:-/var/lib/spellgunners/update-waiting}
STATUS=${SG_STATUS:-http://127.0.0.1:5557/}
RESTART=${SG_RESTART:-systemctl restart spellgunners.service}
log() { logger -t spellgunners-update "$*"; echo "$*"; }

git fetch --tags --quiet origin || { log "нет связи с GitHub"; exit 0; }
latest=$(git tag -l 'v*' --sort=-v:refname | head -1)
current=$(git describe --tags --exact-match 2>/dev/null || echo "нет")
[[ -z "$latest" || "$latest" == "$current" ]] && { rm -f "$STATE"; exit 0; }

# метка уже есть, а выпуск ещё собирается (или сборка упала) — не обновляться: иначе сайт останется без
# браузерной версии (её берём из выпуска). Обновимся при следующей проверке, когда выпуск будет готов.
REPO=${SG_REPO:-msinitcyn/vibegame-01}
if [[ -z "${SG_SKIP_SITE:-}" ]] && ! curl -fsIL --max-time 20 -o /dev/null \
     "https://github.com/$REPO/releases/download/$latest/spellgunners-web.zip"; then
  log "есть метка $latest, но выпуска с браузерной версией ещё нет — ждём"
  exit 0
fi

busy=$(curl -s --max-time 5 "$STATUS" | python3 -c \
  "import json,sys; d=json.load(sys.stdin); print(d.get('players', 0) + d.get('lobby', 0))" 2>/dev/null || echo 0)
if [[ "$busy" != "0" ]]; then
  [[ -f "$STATE" ]] || date +%s > "$STATE"
  waited=$(( $(date +%s) - $(cat "$STATE") ))
  if (( waited < FORCE_AFTER )); then
    log "есть выпуск $latest (сейчас $current), на сервере играют ($busy) — ждём"
    exit 0
  fi
  log "ждали $((waited / 60)) мин — обновляем, хотя играют"
fi
git -c advice.detachedHead=false checkout --quiet "$latest" || { log "не переключился на $latest"; exit 1; }
rm -f "$STATE"
$RESTART
log "обновлён: $current -> $latest"
if [[ -z "${SG_SKIP_SITE:-}" ]]; then                # сайт: страница и браузерная версия этого выпуска
  bash deploy/site.sh "$latest" 2>&1 | logger -t spellgunners-update
fi
exit 0
