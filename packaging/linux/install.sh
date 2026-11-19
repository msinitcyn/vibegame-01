#!/bin/sh
# Установка Spellgunners для текущего пользователя (без sudo):
#   ./install.sh              — игра в ~/.local/bin/spellgunners и в меню приложений
#   ./install.sh --uninstall  — удалить (настройки в ~/.config/duel остаются)
set -e

DIR=$(cd "$(dirname "$0")" && pwd)
BIN="${XDG_BIN_HOME:-$HOME/.local/bin}"
DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
APPS="$DATA/applications"
ICONS="$DATA/icons/hicolor/256x256/apps"

if [ "$1" = "--uninstall" ]; then
    rm -f "$BIN/spellgunners" "$APPS/spellgunners.desktop" "$ICONS/spellgunners.png"
    command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$APPS" || true
    echo "Игра удалена."
    exit 0
fi

if [ ! -f "$DIR/spellgunners-linux" ]; then
    echo "Рядом со скриптом нет файла spellgunners-linux" >&2
    exit 1
fi

mkdir -p "$BIN" "$APPS" "$ICONS"
install -m 755 "$DIR/spellgunners-linux" "$BIN/spellgunners"
install -m 644 "$DIR/spellgunners.png" "$ICONS/spellgunners.png"
cat > "$APPS/spellgunners.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Spellgunners
Comment=Дуэль магов со стволами: артефакты, мобы, игра по сети
Comment[en]=Duel of mages with guns: artifacts, mobs, network play
Comment[fi]=Taikureiden kaksintaistelu aseilla
Exec=$BIN/spellgunners
Icon=spellgunners
Terminal=false
Categories=Game;ArcadeGame;
EOF
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$APPS" || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -q "$DATA/icons/hicolor" 2>/dev/null || true

echo "Готово: Spellgunners в меню приложений, запуск из терминала — $BIN/spellgunners"
case ":$PATH:" in
    *":$BIN:"*) ;;
    *) echo "(папки $BIN нет в PATH — из терминала запускайте полным путём)";;
esac
