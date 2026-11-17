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
        "title": "Дуэль шариков",
        "name.blue": "Синий",
        "name.red": "Красный",
        "name.cpu": "Компьютер",

        "menu.two": "Два игрока",
        "menu.vs": "Против компьютера: {level}",
        "level.easy": "легко",
        "level.medium": "средне",
        "level.hard": "сложно",
        "menu.test": "Тестовый режим: по {hp} жизней",
        "menu.help": "Артефакты: что делает каждый",
        "menu.settings": "Настройки",
        "menu.hint": "W/S или ↑/↓ — выбор,  Enter/Пробел или 1-{n} — выбрать,  Esc — выход",
        "menu.hint_vs": "Против компьютера: вы играете синим слева (W/A/S/D, Пробел, 1-4)",
        "pads.none": "Геймпады не подключены",
        "pads.list": "Геймпады: {list}",
        "pads.blue": "синий",
        "pads.red": "красный",
        "pads.spare": "запасной",
        "pads.hint": "Геймпад: стик/крестовина — движение, R1/R2 — огонь, □ △ ○ ✕ — артефакты, "
                     "Options — меню",

        "settings.title": "Настройки",
        "settings.lang": "Язык: {lang}",
        "settings.back": "Назад",
        "settings.hint": "W/S — выбор,  A/D или Enter — изменить,  Esc — назад",

        "help.title": "Артефакты",
        "help.back": "Esc, Enter, Пробел или ✕/○ на геймпаде — назад",
        "sec.defense": "Защита",
        "sec.weapon": "Оружие: на {t} с",
        "sec.attack": "Атака",
        "sec.debuff": "Дебаффы на соперника",
        "note.1": "Рамка: зелёная — защита, синяя — атака, оранжевая — по сопернику.",
        "note.2": "Статус под именем игрока — всё, что действует сейчас, с таймерами.",
        "note.3": "Артефакты — только из убитых мобов, у того, кто добил. Ячейки заняты — "
                  "в очередь; рядом с ячейками видно {queue} следующих.",
        "note.4": "Оружие: на {weapon} с, разных не больше {wmax} — новое вытесняет старое.",
        "note.5": "Повтор любого эффекта добавляет время (щиту — и удары). Двойникам передаются щит, "
                  "оружие, размер, скорость, «не стреляет».",
        "note.6": "Патроны: в начале {ammo}, выстрел — 1. Пачки по {pack} подбираются сразу.",
        "note.7": "Мобы: волна каждые {every} с в случайных местах, +1 моб и +1 жизнь; "
                  "максимум {mmax} мобов по {mhp}, дальше волны всё чаще.",
        "note.8": "Дебаффы снимает только время или очищение.",

        "wave.title": "волна {n}",
        "wave.in": "через {s} с",
        "wave.next": "след. {s} с",
        "wave.popup": "волна {n}: +{count} по {hp} жизней",
        "wave.stronger": "волна {n}: мобы сильнее",
        "popup.noammo": "нет патронов",
        "popup.ammo": "+{n} патронов",
        "popup.mobdead": "моб повержен",
        "win": "{name} победил!",
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

        "help.shield": "Гасит {shield_hits} пуль или держится {shield} с — что кончится раньше. "
                       "В статусе видно, сколько ударов и секунд осталось.",
        "help.heal": "+{heal} жизни сразу при подборе, в инвентарь не кладётся.",
        "help.shrink": "Ты меньше в 2 раза на {shrink} с — в тебя труднее попасть.",
        "help.speed": "Движение ×1,8 на {speed} с: легче уворачиваться и собирать артефакты.",
        "help.clearfoe": "Все пули соперника, что сейчас на экране, исчезают.",
        "help.slowfoe": "Пули соперника летят примерно вдвое медленнее, {slowfoe} с.",
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
                     "твоими, свои — поглощаются.",
    },

    # ------------------------------------------------------------------ English
    "en": {
        "title": "Ball Duel",
        "name.blue": "Blue",
        "name.red": "Red",
        "name.cpu": "Computer",

        "menu.two": "Two players",
        "menu.vs": "Vs computer: {level}",
        "level.easy": "easy",
        "level.medium": "medium",
        "level.hard": "hard",
        "menu.test": "Test mode: {hp} lives each",
        "menu.help": "Artifacts: what each one does",
        "menu.settings": "Settings",
        "menu.hint": "W/S or ↑/↓ — move,  Enter/Space or 1-{n} — select,  Esc — quit",
        "menu.hint_vs": "Vs computer: you play blue on the left (W/A/S/D, Space, 1-4)",
        "pads.none": "No gamepads connected",
        "pads.list": "Gamepads: {list}",
        "pads.blue": "blue",
        "pads.red": "red",
        "pads.spare": "spare",
        "pads.hint": "Gamepad: stick/D-pad — move, R1/R2 — fire, □ △ ○ ✕ — artifacts, Options — menu",

        "settings.title": "Settings",
        "settings.lang": "Language: {lang}",
        "settings.back": "Back",
        "settings.hint": "W/S — move,  A/D or Enter — change,  Esc — back",

        "help.title": "Artifacts",
        "help.back": "Esc, Enter, Space or ✕/○ on gamepad — back",
        "sec.defense": "Defense",
        "sec.weapon": "Weapon: {t} s",
        "sec.attack": "Attack",
        "sec.debuff": "Debuffs on the opponent",
        "note.1": "Frame: green — defense, blue — attack, orange — against the opponent.",
        "note.2": "The status under a player's name shows everything active right now, with timers.",
        "note.3": "Artifacts drop only from killed mobs, for whoever finished them. Slots full — "
                  "into the queue; the next {queue} are shown next to the slots.",
        "note.4": "Weapons: {weapon} s, at most {wmax} different at once — a new one replaces the oldest.",
        "note.5": "Repeating any effect adds time (and hits for the shield). Clones get the shield, "
                  "weapons, size, speed and \"can't shoot\".",
        "note.6": "Ammo: {ammo} at start, 1 per shot. Packs of {pack} are picked up instantly.",
        "note.7": "Mobs: a wave every {every} s in random spots, +1 mob and +1 life; "
                  "at most {mmax} mobs with {mhp} lives, then waves come faster.",
        "note.8": "Debuffs are removed only by time or cleanse.",

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

        "help.shield": "Blocks {shield_hits} bullets or lasts {shield} s — whichever ends first. "
                       "Hits and seconds left are shown in the status.",
        "help.heal": "+{heal} lives right on pickup, doesn't go to the inventory.",
        "help.shrink": "You are 2× smaller for {shrink} s — harder to hit.",
        "help.speed": "Movement ×1.8 for {speed} s: easier to dodge and collect artifacts.",
        "help.clearfoe": "All opponent bullets currently on screen disappear.",
        "help.slowfoe": "Opponent bullets fly about twice as slow, {slowfoe} s.",
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
                     "and become yours, your own are absorbed.",
    },

    # ------------------------------------------------------------------ suomi
    "fi": {
        "title": "Pallojen kaksintaistelu",
        "name.blue": "Sininen",
        "name.red": "Punainen",
        "name.cpu": "Tietokone",

        "menu.two": "Kaksi pelaajaa",
        "menu.vs": "Tietokonetta vastaan: {level}",
        "level.easy": "helppo",
        "level.medium": "keskitaso",
        "level.hard": "vaikea",
        "menu.test": "Testitila: {hp} elämää kummallekin",
        "menu.help": "Artefaktit: mitä kukin tekee",
        "menu.settings": "Asetukset",
        "menu.hint": "W/S tai ↑/↓ — liiku,  Enter/välilyönti tai 1-{n} — valitse,  Esc — lopeta",
        "menu.hint_vs": "Tietokonetta vastaan: pelaat sinisellä vasemmalla (W/A/S/D, välilyönti, 1-4)",
        "pads.none": "Peliohjaimia ei ole kytketty",
        "pads.list": "Peliohjaimet: {list}",
        "pads.blue": "sininen",
        "pads.red": "punainen",
        "pads.spare": "vara",
        "pads.hint": "Peliohjain: tikku/ristiohjain — liiku, R1/R2 — ammu, □ △ ○ ✕ — artefaktit, "
                     "Options — valikko",

        "settings.title": "Asetukset",
        "settings.lang": "Kieli: {lang}",
        "settings.back": "Takaisin",
        "settings.hint": "W/S — liiku,  A/D tai Enter — vaihda,  Esc — takaisin",

        "help.title": "Artefaktit",
        "help.back": "Esc, Enter, välilyönti tai ✕/○ ohjaimessa — takaisin",
        "sec.defense": "Puolustus",
        "sec.weapon": "Ase: {t} s",
        "sec.attack": "Hyökkäys",
        "sec.debuff": "Heikennykset vastustajalle",
        "note.1": "Kehys: vihreä — puolustus, sininen — hyökkäys, oranssi — vastustajaa vastaan.",
        "note.2": "Pelaajan nimen alla näkyy kaikki voimassa oleva ajastimineen.",
        "note.3": "Artefakteja saa vain kaatuneista hirviöistä, viimeisen osuman tehneelle. "
                  "Paikat täynnä — jonoon; seuraavat {queue} näkyvät paikkojen vieressä.",
        "note.4": "Aseet: {weapon} s, enintään {wmax} erilaista kerralla — uusi korvaa vanhimman.",
        "note.5": "Saman vaikutuksen toisto lisää aikaa (kilvelle myös osumia). Kloonit saavat kilven, "
                  "aseet, koon, nopeuden ja \"ei voi ampua\".",
        "note.6": "Ammukset: alussa {ammo}, laukaus vie 1. {pack} ammuksen laatikot poimitaan heti.",
        "note.7": "Hirviöt: aalto {every} s välein satunnaisiin paikkoihin, +1 hirviö ja +1 elämä; "
                  "enintään {mmax} hirviötä, {mhp} elämää, sitten aallot tihenevät.",
        "note.8": "Heikennykset poistuvat vain ajan kanssa tai puhdistuksella.",

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

        "help.shield": "Torjuu {shield_hits} luotia tai kestää {shield} s — kumpi loppuu ensin. "
                       "Jäljellä olevat osumat ja sekunnit näkyvät tilarivillä.",
        "help.heal": "+{heal} elämää heti poimittaessa, ei mene varastoon.",
        "help.shrink": "Olet 2× pienempi {shrink} s — sinuun on vaikeampi osua.",
        "help.speed": "Liike ×1,8 {speed} s: helpompi väistää ja kerätä artefakteja.",
        "help.clearfoe": "Kaikki ruudulla olevat vastustajan luodit katoavat.",
        "help.slowfoe": "Vastustajan luodit lentävät noin puolet hitaammin, {slowfoe} s.",
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
                     "ja muuttuvat sinun luodeiksesi, omasi imeytyvät.",
    },
}
