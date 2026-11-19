#!/bin/sh
# Установка «Дуэли шариков» для текущего пользователя (без sudo):
#   ./install.sh              — игра в ~/.local/bin/duel и в меню приложений
#   ./install.sh --uninstall  — удалить (настройки в ~/.config/duel остаются)
set -e

DIR=$(cd "$(dirname "$0")" && pwd)
BIN="${XDG_BIN_HOME:-$HOME/.local/bin}"
DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
APPS="$DATA/applications"
ICONS="$DATA/icons/hicolor/256x256/apps"

if [ "$1" = "--uninstall" ]; then
    rm -f "$BIN/duel" "$APPS/duel.desktop" "$ICONS/duel.png"
    command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$APPS" || true
    echo "Игра удалена."
    exit 0
fi

if [ ! -f "$DIR/duel-linux" ]; then
    echo "Рядом со скриптом нет файла duel-linux" >&2
    exit 1
fi

mkdir -p "$BIN" "$APPS" "$ICONS"
install -m 755 "$DIR/duel-linux" "$BIN/duel"
install -m 644 "$DIR/duel.png" "$ICONS/duel.png"
cat > "$APPS/duel.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Дуэль шариков
Name[en]=Ball Duel
Name[fi]=Pallojen kaksintaistelu
Comment=Дуэль двух магов с артефактами и мобами
Comment[en]=Duel of two mages with artifacts and mobs
Exec=$BIN/duel
Icon=duel
Terminal=false
Categories=Game;ArcadeGame;
EOF
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$APPS" || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -q "$DATA/icons/hicolor" 2>/dev/null || true

echo "Готово: «Дуэль шариков» в меню приложений, запуск из терминала — $BIN/duel"
case ":$PATH:" in
    *":$BIN:"*) ;;
    *) echo "(папки $BIN нет в PATH — из терминала запускайте полным путём)";;
esac
