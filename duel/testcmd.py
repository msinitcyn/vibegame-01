"""Тестовые команды игры с ботом: выдать артефакт себе или боту, поставить бота в режим.

Одна логика для всех мест, где играет бот: тестовый режим и разминка (свой матч на клиенте) и
сетевая партия против бота (сервер, сообщение {"type": "test", ...} — см. net.py, room.py).

Сообщение (клиент уже нашёл код артефакта; сервер всё равно проверяет):
    {"do": "give", "kind": "lasso", "to": "me" | "foe"}
    {"do": "bot", "mode": "play" | "stop" | "fire" | "stand" | "walk" | "noshoot" | "shoot"}
    {"do": "bot", "use": 0..3}
    {"do": "ammo", "n": 1..999, "to": "me" | "foe"}   патроны
    {"do": "drops", "on": bool}                        мобы роняют артефакты или нет
"""
from .items import INSTANT_ITEMS, ITEMS, item_name

AMMO_MAX_GIVE = 999                  # /ammo: не больше стольких патронов за раз
BOT_MODES = ("play", "stop", "fire", "stand", "walk", "noshoot", "shoot")

# слова команд чата (и русские) — разбирает client_chat
ME_WORDS = ("me", "я", "мне", "себе")
FOE_WORDS = ("bot", "foe", "бот", "боту", "ему", "сопернику")
MODE_WORDS = {
    "play": ("play", "go", "играй", "играть", "иди"),
    "stop": ("stop", "стоп", "стой", "стоять"),
    "fire": ("fire", "огонь"),
    "stand": ("stand", "стоит", "неходи"),
    "walk": ("walk", "ходи", "ходит"),
    "noshoot": ("noshoot", "nofire", "нестреляй", "нестреляет", "тихо"),
    "shoot": ("shoot", "стреляй", "стреляет"),
}
ON_WORDS = ("on", "yes", "1", "вкл", "да")
OFF_WORDS = ("off", "no", "0", "выкл", "нет")
USE_WORDS = ("use", "slot", "ячейка", "применить", "примени")


def _norm(text):
    return text.lower().replace("ё", "е").strip()


def find_item(text):
    """Код артефакта по коду или части названия (на языке игры); None — не нашёлся или их несколько."""
    word = _norm(text)
    if not word:
        return None
    if word in ITEMS:
        return word
    names = {k: _norm(item_name(k)) for k in ITEMS}
    exact = [k for k, n in names.items() if n == word]
    if exact:
        return exact[0]
    found = [k for k, n in names.items() if word in n]
    return found[0] if len(found) == 1 else None


def grant(match, p, kind):
    """Артефакт магу — как при подборе: мгновенный срабатывает сразу, остальные — в ячейку или очередь."""
    if kind in INSTANT_ITEMS:
        match.apply_item(p, kind)
    else:
        p.add_item(kind)


def run(match, bot, pid, msg):
    """Выполнить тестовую команду игрока pid против бота. True — выполнена."""
    if not isinstance(msg, dict):
        return False
    do = msg.get("do")
    if do == "give":
        kind = msg.get("kind")
        if not isinstance(kind, str) or kind not in ITEMS:
            return False
        me = match.player(pid)
        grant(match, match.other(me) if msg.get("to") == "foe" else me, kind)
        return True
    if do == "bot" and bot is not None:
        use = msg.get("use")
        if isinstance(use, int) and not isinstance(use, bool) and 0 <= use <= 3:
            bot.use_next = use
            return True
        mode = msg.get("mode")
        if mode in BOT_MODES:
            set_bot_mode(bot, mode)
            return True
    if do == "ammo":
        n = msg.get("n")
        if not isinstance(n, int) or isinstance(n, bool) or not 1 <= n <= AMMO_MAX_GIVE:
            return False
        me = match.player(pid)
        (match.other(me) if msg.get("to") == "foe" else me).ammo += n
        return True
    if do == "drops" and isinstance(msg.get("on"), bool):
        match.drops = msg["on"]
        return True
    return False


def set_bot_mode(bot, mode):
    """play / stop / fire — режим целиком; stand, walk, noshoot, shoot — по одному запрету в обычной игре."""
    if mode in ("play", "stop", "fire"):
        bot.mode = mode
        bot.walk = bot.shoot = True
        return
    bot.mode = "play"
    if mode in ("stand", "walk"):
        bot.walk = mode == "walk"
    else:
        bot.shoot = mode == "shoot"
