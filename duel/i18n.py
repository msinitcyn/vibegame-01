"""Переводы: русский, английский, финский.

t("ключ", **числа) — строка на текущем языке. Нет перевода — берётся русская.
Числа подставляются через {имя}, например t("popup.ammo", n=20).
"""

LANGS = {"ru": "Русский", "en": "English", "fi": "Suomi"}
DEFAULT_LANG = "ru"
_lang = DEFAULT_LANG


def set_lang(code):
    global _lang
    _lang = code if code in LANGS else DEFAULT_LANG


def get_lang():
    return _lang


def t(key, **kw):
    text = TEXTS[_lang].get(key) or TEXTS[DEFAULT_LANG][key]
    return text.format(**kw) if kw else text


TEXTS = {
    # ------------------------------------------------------------------ русский
    "ru": {
        "title": "Spellgunners",
        "name.blue": "Синий",
        "name.red": "Красный",

        "menu.two": "Два игрока",
        "menu.test": "Тестовый режим: по {hp} жизней",
        "menu.help": "Артефакты: что делает каждый",
        "menu.settings": "Настройки",
        "menu.host": "Создать игру по сети",
        "menu.join": "Подключиться к игре",
        "net.wait_title": "Ждём второго игрока",
        "net.your_addr": "Второй игрок вводит адрес этого компьютера:",
        "net.no_addr": "Адрес не найден — узнайте его командой hostname -I",
        "net.host_hint": "B или △ — играть с ботом,   Esc или ○ — отмена",
        "net.guest_wait": "Подключились. Ждём, пока второй игрок присоединится…",
        "net.guest_hint": "Esc или ○ — отключиться",
        "net.join_title": "Подключиться к игре",
        "net.join_prompt": "Адрес компьютера, создавшего игру:",
        "net.join_hint": "↑/↓ — выбор,   Enter или ✕ — подключиться,   Esc или ○ — назад,   Backspace — стереть",
        "net.found": "Игры в сети:",
        "net.searching": "Ищем игры в сети…",
        "net.none_hint": "Не видно? Создайте игру на другом компьютере, разрешите игру в брандмауэре или введите адрес.",
        "net.manual": "Или введите адрес вручную:",
        "net.st_wait": "ждёт второго игрока",
        "net.st_full": "мест нет",
        "net.st_proto": "другая версия игры",
        "net.lost": "Связь с сервером потеряна",
        "net.port_busy": "Не удалось создать игру: порт {port} занят",
        "net.fail": "Не удалось подключиться: {err}",
        "net.err.refused": "на этом адресе игра не создана",
        "net.err.timeout": "компьютер не отвечает",
        "net.err.badhost": "такого адреса нет",
        "net.err.full": "в игре уже два игрока",
        "net.err.proto": "другая версия игры — обновите её на обоих компьютерах",
        "net.title_suffix": "{name} (сеть)",
        "menu.hint": "W/S или ↑/↓ — выбор,  Enter/Пробел или 1-{n} — выбрать,  Esc — выход",
        "pads.none": "Геймпады не подключены",
        "pads.list": "Геймпады: {list}",
        "pads.blue": "синий",
        "pads.red": "красный",
        "pads.spare": "запасной",
        "pads.hint": "Геймпад: стик/крестовина — движение, R1/R2 — огонь, L1/L2 — удар, "
                     "□ △ ○ ✕ — артефакты, Options — меню",

        "settings.title": "Настройки",
        "settings.lang": "Язык: {lang}",
        "settings.back": "Назад",
        "settings.name": "Имя: {name}",
        "settings.name_empty": "— (по цвету)",
        "settings.name_hint": "Наберите имя (до 16 букв, любой язык),  Backspace — стереть,  ↑/↓ — другая строка,  Esc — назад",
        "name.bot": "Бот",
        "settings.hint": "W/S — выбор,  A/D или Enter — изменить,  Esc — назад",

        "help.title": "Артефакты",
        "help.rules": "Правила",
        "help.pages": "A/D или ←/→ — страница {page}/{pages}",
        "help.back": "Esc, Enter, Пробел, ✕/○ — назад",
        "sec.defense": "Защита",
        "sec.weapon": "Оружие: на {t} с",
        "sec.attack": "Атака",
        "sec.debuff": "Дебаффы на соперника",
        "note.1": "Рамка: зелёная — защита, синяя — атака, оранжевая — по сопернику.",
        "note.2": "Статус под именем игрока — всё, что действует сейчас, с таймерами.",
        "note.3": "Артефакт выпадает, только если моб добит на твоей земле, — на месте гибели, "
                  "и лежит, пока не подберёшь. Ячейки заняты — в очередь; рядом с ячейками "
                  "видно {queue} следующих.",
        "note.4": "Оружие: на {weapon} с, разных не больше {wmax} — новое вытесняет старое.",
        "note.5": "Повтор любого эффекта добавляет время (щиту — и удары). Двойникам передаются щит, "
                  "оружие, размер, скорость, «не стреляет».",
        "note.6": "Патроны: в начале {ammo}, выстрел — 1. Пачки по {pack} подбираются сразу.",
        "note.7": "Мобы: волна каждые {every} с в случайных местах, в новой волне +1 моб и +1 жизнь "
                  "(уже живые не лечатся); "
                  "максимум {mmax} мобов по {mhp}, дальше волны всё чаще. Каждый {ranged}-й моб — "
                  "дальнобойный (зелёный, с кристаллом): держится на расстоянии и стреляет "
                  "не дальше {range} px.",
        "note.8": "Дебаффы снимает только время или очищение.",
        "note.9": "Ближний удар (E / правый Shift / L1, L2) — только по мобам рядом: {melee} урона, "
                  "без патронов, раз в {melee_cd} с.",

        "wave.title": "волна {n}",
        "wave.in": "через {s} с",
        "wave.next": "след. {s} с",
        "wave.popup": "волна {n}: +{count} по {hp} жизней",
        "wave.stronger": "волна {n}: мобы сильнее",
        "popup.noammo": "нет патронов",
        "popup.ammo": "+{n} патронов",
        "popup.mobdead": "моб повержен",
        "win": "Победа: {name}!",
        "win.hint": "R — ещё раз, Esc — в меню",

        "item.triple": "веер",
        "item.shrink": "уменьшение",
        "item.speed": "скорость",
        "item.wall": "стена-зеркало",
        "item.rapid": "скорострельность",
        "item.slowfoe": "пули соперника медленнее",
        "item.shield": "щит",
        "item.heal": "лечение +{heal}",
        "item.clones": "двойники",
        "item.breaker": "сбиваешь пули",
        "item.wavy": "пули волной",
        "item.clearfoe": "убрать пули соперника",
        "item.cleanse": "очищение",
        "item.foe_grow": "соперник ×2",
        "item.foe_freeze": "заморозить соперника",
        "item.foe_nofire": "соперник не стреляет",
        "item.foe_invert": "соперник: управление наоборот",
        "item.foe_noitems": "соперник без артефактов",
        "item.fastshots": "быстрые пули",
        "decimal": ",",

        "help.shield": "Гасит {shield_hits} пуль или держится {shield} с — что кончится раньше. "
                       "В статусе видно, сколько ударов и секунд осталось.",
        "help.heal": "+{heal} жизни сразу при подборе, в инвентарь не кладётся.",
        "help.shrink": "Ты меньше в 2 раза на {shrink} с — в тебя труднее попасть.",
        "help.speed": "Движение ×1,8 на {speed} с: легче уворачиваться и собирать артефакты.",
        "help.clearfoe": "Все пули соперника, что сейчас на экране, исчезают.",
        "help.slowfoe": "Пули соперника и мобы, которые идут на тебя, примерно вдвое медленнее, "
                        "{slowfoe} с.",
        "help.fastshots": "Твои пули летят в {fast} раза быстрее {fastshots} с, и мобы, "
                          "которые идут на соперника, — тоже.",
        "help.foe_grow": "Соперник больше в 2 раза на {grow2} с — по нему легче попасть.",
        "help.foe_freeze": "Соперник не может двигаться {freeze} с. Стрелять может.",
        "help.foe_nofire": "Соперник не может стрелять {nofire} с.",
        "help.foe_invert": "У соперника управление наоборот {invert} с.",
        "help.foe_noitems": "Соперник не может использовать артефакты {noitems} с "
                            "(кроме очищения). Подбирать может.",
        "help.cleanse": "Снимает с тебя и твоих двойников все дебаффы соперника. "
                        "Работает даже под запретом артефактов.",
        "help.triple": "Каждый выстрел — веер из трёх пуль, {triple} с. Патрон один.",
        "help.rapid": "Пауза между выстрелами {rapid_cd} с вместо {cd} с, {rapid} с.",
        "help.wavy": "Твои пули летят синусоидой {wavy} с — их трудно предугадать.",
        "help.clones": "{clones} двойника сами ходят и стреляют. Умирают с одного попадания, "
                       "живут до {clone_time} с.",
        "help.breaker": "{breaker} с твои пули сбивают встречные пули соперника.",
        "help.wall": "Стена перед тобой на {wall_time} с: пули соперника отражаются и становятся "
                     "твоими, свои пролетают насквозь. Мобы сквозь неё не проходят.",
    },

    # ------------------------------------------------------------------ English
    "en": {
        "title": "Spellgunners",
        "name.blue": "Blue",
        "name.red": "Red",

        "menu.two": "Two players",
        "menu.test": "Test mode: {hp} lives each",
        "menu.help": "Artifacts: what each one does",
        "menu.settings": "Settings",
        "menu.host": "Host a network game",
        "menu.join": "Join a game",
        "net.wait_title": "Waiting for the second player",
        "net.your_addr": "The second player enters this computer's address:",
        "net.no_addr": "Address not found — check it with hostname -I",
        "net.host_hint": "B or △ — play against a bot,   Esc or ○ — cancel",
        "net.guest_wait": "Connected. Waiting for the second player to join…",
        "net.guest_hint": "Esc or ○ — disconnect",
        "net.join_title": "Join a game",
        "net.join_prompt": "Address of the computer hosting the game:",
        "net.join_hint": "↑/↓ — choose,   Enter or ✕ — connect,   Esc or ○ — back,   Backspace — erase",
        "net.found": "Games on the network:",
        "net.searching": "Looking for games on the network…",
        "net.none_hint": "Nothing? Host a game on the other computer, allow the game in the firewall or enter the address.",
        "net.manual": "Or enter the address:",
        "net.st_wait": "waiting for the second player",
        "net.st_full": "full",
        "net.st_proto": "different game version",
        "net.lost": "Connection to the server lost",
        "net.port_busy": "Could not host a game: port {port} is busy",
        "net.fail": "Could not connect: {err}",
        "net.err.refused": "no game is hosted at this address",
        "net.err.timeout": "the computer does not answer",
        "net.err.badhost": "no such address",
        "net.err.full": "the game already has two players",
        "net.err.proto": "different game version — update it on both computers",
        "net.title_suffix": "{name} (network)",
        "menu.hint": "W/S or ↑/↓ — move,  Enter/Space or 1-{n} — select,  Esc — quit",
        "pads.none": "No gamepads connected",
        "pads.list": "Gamepads: {list}",
        "pads.blue": "blue",
        "pads.red": "red",
        "pads.spare": "spare",
        "pads.hint": "Gamepad: stick/D-pad — move, R1/R2 — fire, L1/L2 — melee, □ △ ○ ✕ — artifacts, "
                     "Options — menu",

        "settings.title": "Settings",
        "settings.lang": "Language: {lang}",
        "settings.back": "Back",
        "settings.name": "Name: {name}",
        "settings.name_empty": "— (by colour)",
        "settings.name_hint": "Type your name (up to 16 letters),  Backspace — erase,  ↑/↓ — other row,  Esc — back",
        "name.bot": "Bot",
        "settings.hint": "W/S — move,  A/D or Enter — change,  Esc — back",

        "help.title": "Artifacts",
        "help.rules": "Rules",
        "help.pages": "A/D or ←/→ — page {page}/{pages}",
        "help.back": "Esc, Enter, Space, ✕/○ — back",
        "sec.defense": "Defense",
        "sec.weapon": "Weapon: {t} s",
        "sec.attack": "Attack",
        "sec.debuff": "Debuffs on the opponent",
        "note.1": "Frame: green — defense, blue — attack, orange — against the opponent.",
        "note.2": "The status under a player's name shows everything active right now, with timers.",
        "note.3": "An artifact drops only if the mob dies on your land — right where it fell — "
                  "and stays until you pick it up. Slots full — into the queue; the next {queue} "
                  "are shown next to the slots.",
        "note.4": "Weapons: {weapon} s, at most {wmax} different at once — a new one replaces the oldest.",
        "note.5": "Repeating any effect adds time (and hits for the shield). Clones get the shield, "
                  "weapons, size, speed and \"can't shoot\".",
        "note.6": "Ammo: {ammo} at start, 1 per shot. Packs of {pack} are picked up instantly.",
        "note.7": "Mobs: a wave every {every} s in random spots, each new wave +1 mob and +1 life "
                  "(mobs already on the field don't heal); "
                  "at most {mmax} mobs with {mhp} lives, then waves come faster. One mob in {ranged} "
                  "is ranged (green, with a crystal): it keeps its distance and shoots up to {range} px.",
        "note.8": "Debuffs are removed only by time or cleanse.",
        "note.9": "Melee (E / right Shift / L1, L2) hits only nearby mobs: {melee} damage, "
                  "no ammo, once every {melee_cd} s.",

        "wave.title": "wave {n}",
        "wave.in": "in {s} s",
        "wave.next": "next {s} s",
        "wave.popup": "wave {n}: +{count} with {hp} lives",
        "wave.stronger": "wave {n}: mobs get stronger",
        "popup.noammo": "out of ammo",
        "popup.ammo": "+{n} ammo",
        "popup.mobdead": "mob defeated",
        "win": "{name} wins!",
        "win.hint": "R — again, Esc — menu",

        "item.triple": "fan",
        "item.shrink": "shrink",
        "item.speed": "speed",
        "item.wall": "mirror wall",
        "item.rapid": "rapid fire",
        "item.slowfoe": "slow enemy bullets",
        "item.shield": "shield",
        "item.heal": "heal +{heal}",
        "item.clones": "clones",
        "item.breaker": "bullet breaker",
        "item.wavy": "wave bullets",
        "item.clearfoe": "clear enemy bullets",
        "item.cleanse": "cleanse",
        "item.foe_grow": "opponent ×2",
        "item.foe_freeze": "freeze opponent",
        "item.foe_nofire": "opponent can't shoot",
        "item.foe_invert": "opponent: reversed controls",
        "item.foe_noitems": "opponent: no artifacts",
        "item.fastshots": "fast bullets",
        "decimal": ".",

        "help.shield": "Blocks {shield_hits} bullets or lasts {shield} s — whichever ends first. "
                       "Hits and seconds left are shown in the status.",
        "help.heal": "+{heal} lives right on pickup, doesn't go to the inventory.",
        "help.shrink": "You are 2× smaller for {shrink} s — harder to hit.",
        "help.speed": "Movement ×1.8 for {speed} s: easier to dodge and collect artifacts.",
        "help.clearfoe": "All opponent bullets currently on screen disappear.",
        "help.slowfoe": "Opponent bullets and mobs coming at you are about twice as slow, {slowfoe} s.",
        "help.fastshots": "Your bullets fly {fast}× faster for {fastshots} s, and so do mobs "
                          "going after the opponent.",
        "help.foe_grow": "The opponent is 2× bigger for {grow2} s — easier to hit.",
        "help.foe_freeze": "The opponent can't move for {freeze} s. Can still shoot.",
        "help.foe_nofire": "The opponent can't shoot for {nofire} s.",
        "help.foe_invert": "The opponent's controls are reversed for {invert} s.",
        "help.foe_noitems": "The opponent can't use artifacts for {noitems} s "
                            "(except cleanse). Can still pick them up.",
        "help.cleanse": "Removes all opponent debuffs from you and your clones. "
                        "Works even when artifacts are blocked.",
        "help.triple": "Every shot is a fan of three bullets, {triple} s. Costs one round.",
        "help.rapid": "Pause between shots {rapid_cd} s instead of {cd} s, {rapid} s.",
        "help.wavy": "Your bullets fly in a sine wave for {wavy} s — hard to predict.",
        "help.clones": "{clones} clones walk and shoot on their own. They die from one hit "
                       "and live up to {clone_time} s.",
        "help.breaker": "For {breaker} s your bullets knock down incoming opponent bullets.",
        "help.wall": "A wall in front of you for {wall_time} s: opponent bullets bounce back "
                     "and become yours, your own fly through. Mobs can't pass it.",
    },

    # ------------------------------------------------------------------ suomi
    "fi": {
        "title": "Spellgunners",
        "name.blue": "Sininen",
        "name.red": "Punainen",

        "menu.two": "Kaksi pelaajaa",
        "menu.test": "Testitila: {hp} elämää kummallekin",
        "menu.help": "Artefaktit: mitä kukin tekee",
        "menu.settings": "Asetukset",
        "menu.host": "Luo verkkopeli",
        "menu.join": "Liity peliin",
        "net.wait_title": "Odotetaan toista pelaajaa",
        "net.your_addr": "Toinen pelaaja syöttää tämän tietokoneen osoitteen:",
        "net.no_addr": "Osoitetta ei löytynyt — tarkista se komennolla hostname -I",
        "net.host_hint": "B tai △ — pelaa bottia vastaan,   Esc tai ○ — peru",
        "net.guest_wait": "Yhdistetty. Odotetaan toisen pelaajan liittymistä…",
        "net.guest_hint": "Esc tai ○ — katkaise yhteys",
        "net.join_title": "Liity peliin",
        "net.join_prompt": "Pelin luoneen tietokoneen osoite:",
        "net.join_hint": "↑/↓ — valitse,   Enter tai ✕ — yhdistä,   Esc tai ○ — takaisin,   Backspace — poista",
        "net.found": "Pelit verkossa:",
        "net.searching": "Etsitään pelejä verkosta…",
        "net.none_hint": "Ei näy? Luo peli toisella tietokoneella, salli peli palomuurissa tai syötä osoite.",
        "net.manual": "Tai syötä osoite itse:",
        "net.st_wait": "odottaa toista pelaajaa",
        "net.st_full": "täynnä",
        "net.st_proto": "eri peliversio",
        "net.lost": "Yhteys palvelimeen katkesi",
        "net.port_busy": "Pelin luonti epäonnistui: portti {port} on varattu",
        "net.fail": "Yhdistäminen epäonnistui: {err}",
        "net.err.refused": "tässä osoitteessa ei ole peliä",
        "net.err.timeout": "tietokone ei vastaa",
        "net.err.badhost": "osoitetta ei ole",
        "net.err.full": "pelissä on jo kaksi pelaajaa",
        "net.err.proto": "eri peliversio — päivitä se molemmille tietokoneille",
        "net.title_suffix": "{name} (verkko)",
        "menu.hint": "W/S tai ↑/↓ — liiku,  Enter/välilyönti tai 1-{n} — valitse,  Esc — lopeta",
        "pads.none": "Peliohjaimia ei ole kytketty",
        "pads.list": "Peliohjaimet: {list}",
        "pads.blue": "sininen",
        "pads.red": "punainen",
        "pads.spare": "vara",
        "pads.hint": "Peliohjain: tikku/ristiohjain — liiku, R1/R2 — ammu, L1/L2 — lyönti, "
                     "□ △ ○ ✕ — artefaktit, Options — valikko",

        "settings.title": "Asetukset",
        "settings.lang": "Kieli: {lang}",
        "settings.back": "Takaisin",
        "settings.name": "Nimi: {name}",
        "settings.name_empty": "— (värin mukaan)",
        "settings.name_hint": "Kirjoita nimesi (enintään 16 merkkiä),  Backspace — poista,  ↑/↓ — toinen rivi,  Esc — takaisin",
        "name.bot": "Botti",
        "settings.hint": "W/S — liiku,  A/D tai Enter — vaihda,  Esc — takaisin",

        "help.title": "Artefaktit",
        "help.rules": "Säännöt",
        "help.pages": "A/D tai ←/→ — sivu {page}/{pages}",
        "help.back": "Esc, Enter, välilyönti, ✕/○ — takaisin",
        "sec.defense": "Puolustus",
        "sec.weapon": "Ase: {t} s",
        "sec.attack": "Hyökkäys",
        "sec.debuff": "Heikennykset vastustajalle",
        "note.1": "Kehys: vihreä — puolustus, sininen — hyökkäys, oranssi — vastustajaa vastaan.",
        "note.2": "Pelaajan nimen alla näkyy kaikki voimassa oleva ajastimineen.",
        "note.3": "Artefakti putoaa vain, jos hirviö kaatuu omalla alueellasi — kaatumispaikkaan — "
                  "ja odottaa, kunnes poimit sen. Paikat täynnä — jonoon; seuraavat {queue} "
                  "näkyvät paikkojen vieressä.",
        "note.4": "Aseet: {weapon} s, enintään {wmax} erilaista kerralla — uusi korvaa vanhimman.",
        "note.5": "Saman vaikutuksen toisto lisää aikaa (kilvelle myös osumia). Kloonit saavat kilven, "
                  "aseet, koon, nopeuden ja \"ei voi ampua\".",
        "note.6": "Ammukset: alussa {ammo}, laukaus vie 1. {pack} ammuksen laatikot poimitaan heti.",
        "note.7": "Hirviöt: aalto {every} s välein satunnaisiin paikkoihin, uudessa aallossa +1 hirviö "
                  "ja +1 elämä (kentällä olevat eivät parane); "
                  "enintään {mmax} hirviötä, {mhp} elämää, sitten aallot tihenevät. Joka {ranged}. "
                  "hirviö ampuu kaukaa (vihreä, kristallipäinen): pysyy etäällä ja ampuu enintään "
                  "{range} px päähän.",
        "note.8": "Heikennykset poistuvat vain ajan kanssa tai puhdistuksella.",
        "note.9": "Lähilyönti (E / oikea Shift / L1, L2) osuu vain lähellä oleviin hirviöihin: "
                  "{melee} vahinkoa, ilman ammuksia, kerran {melee_cd} s välein.",

        "wave.title": "aalto {n}",
        "wave.in": "{s} s päästä",
        "wave.next": "seur. {s} s",
        "wave.popup": "aalto {n}: +{count}, {hp} elämää",
        "wave.stronger": "aalto {n}: hirviöt vahvistuvat",
        "popup.noammo": "ammukset loppu",
        "popup.ammo": "+{n} ammusta",
        "popup.mobdead": "hirviö kaatui",
        "win": "{name} voitti!",
        "win.hint": "R — uudestaan, Esc — valikkoon",

        "item.triple": "viuhka",
        "item.shrink": "kutistus",
        "item.speed": "nopeus",
        "item.wall": "peilimuuri",
        "item.rapid": "pikatuli",
        "item.slowfoe": "vastustajan luodit hitaammin",
        "item.shield": "kilpi",
        "item.heal": "parannus +{heal}",
        "item.clones": "kloonit",
        "item.breaker": "luotien torjunta",
        "item.wavy": "aaltoluodit",
        "item.clearfoe": "poista vastustajan luodit",
        "item.cleanse": "puhdistus",
        "item.foe_grow": "vastustaja ×2",
        "item.foe_freeze": "jäädytä vastustaja",
        "item.foe_nofire": "vastustaja ei voi ampua",
        "item.foe_invert": "vastustaja: käänteinen ohjaus",
        "item.foe_noitems": "vastustaja ilman artefakteja",
        "item.fastshots": "nopeat luodit",
        "decimal": ",",

        "help.shield": "Torjuu {shield_hits} luotia tai kestää {shield} s — kumpi loppuu ensin. "
                       "Jäljellä olevat osumat ja sekunnit näkyvät tilarivillä.",
        "help.heal": "+{heal} elämää heti poimittaessa, ei mene varastoon.",
        "help.shrink": "Olet 2× pienempi {shrink} s — sinuun on vaikeampi osua.",
        "help.speed": "Liike ×1,8 {speed} s: helpompi väistää ja kerätä artefakteja.",
        "help.clearfoe": "Kaikki ruudulla olevat vastustajan luodit katoavat.",
        "help.slowfoe": "Vastustajan luodit ja sinua kohti tulevat hirviöt ovat noin puolet "
                        "hitaampia, {slowfoe} s.",
        "help.fastshots": "Luotisi lentävät {fast}× nopeammin {fastshots} s, samoin vastustajaa "
                          "kohti menevät hirviöt.",
        "help.foe_grow": "Vastustaja on 2× suurempi {grow2} s — häneen on helpompi osua.",
        "help.foe_freeze": "Vastustaja ei voi liikkua {freeze} s. Ampua voi.",
        "help.foe_nofire": "Vastustaja ei voi ampua {nofire} s.",
        "help.foe_invert": "Vastustajan ohjaus on käänteinen {invert} s.",
        "help.foe_noitems": "Vastustaja ei voi käyttää artefakteja {noitems} s "
                            "(paitsi puhdistusta). Poimia voi.",
        "help.cleanse": "Poistaa sinusta ja klooneistasi kaikki vastustajan heikennykset. "
                        "Toimii myös artefaktikiellon aikana.",
        "help.triple": "Jokainen laukaus on kolmen luodin viuhka, {triple} s. Kuluttaa yhden ammuksen.",
        "help.rapid": "Tauko laukausten välillä {rapid_cd} s eikä {cd} s, {rapid} s.",
        "help.wavy": "Luotisi lentävät aaltoillen {wavy} s — vaikea ennakoida.",
        "help.clones": "{clones} kloonia liikkuu ja ampuu itse. Ne kuolevat yhdestä osumasta "
                       "ja elävät enintään {clone_time} s.",
        "help.breaker": "{breaker} s luotisi torjuvat vastaan tulevat vastustajan luodit.",
        "help.wall": "Muuri edessäsi {wall_time} s: vastustajan luodit kimpoavat takaisin "
                     "ja muuttuvat sinun luodeiksesi, omasi lentävät läpi. Hirviöt eivät pääse läpi.",
    },
}
