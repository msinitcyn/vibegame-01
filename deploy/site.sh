#!/usr/bin/env bash
# Сайт сервера: страница (deploy/site/index.html) и браузерная версия того же выпуска (play/, из релиза на
# GitHub — spellgunners-web.zip) в /var/www/spellgunners. Запускают install.sh и autoupdate.sh;
# руками:  sudo bash /opt/spellgunners/deploy/site.sh [тег]
set -euo pipefail
cd "${SG_DIR:-/opt/spellgunners}"
REPO=msinitcyn/vibegame-01
OUT=${SG_SITE:-/var/www/spellgunners}
TAG=${1:-$(git describe --tags --exact-match 2>/dev/null || true)}

new=$(mktemp -d)
cp deploy/site/index.html assets/icon.png "$new/"
if [[ -n "$TAG" ]] && curl -fsSL --max-time 120 -o "$new/web.zip" \
     "https://github.com/$REPO/releases/download/$TAG/spellgunners-web.zip"; then
  python3 -c "import sys, zipfile; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" "$new/web.zip" "$new/play"
  rm -f "$new/web.zip"
  echo "сайт: браузерная версия $TAG"
else
  echo "сайт: в выпуске ${TAG:-?} нет браузерной версии — страница без неё"
fi
chmod -R a+rX "$new"
# подмена целиком: посетитель видит либо старый сайт, либо новый — не половину
mkdir -p "$(dirname "$OUT")"
rm -rf "$OUT.old"
[[ -d "$OUT" ]] && mv "$OUT" "$OUT.old"
mv "$new" "$OUT"
rm -rf "$OUT.old"
