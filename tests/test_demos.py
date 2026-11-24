"""Сценки в справке: сценарии из assets/demos/*.json идут и показывают то, что обещают."""
import json

from duel import demos
from duel.config import HELP_BASICS, HERO_ONLY_ITEMS
from duel.items import ITEMS


def test_all_scenarios_valid():
    files = sorted(demos.DEMO_DIR.glob("*.json"))
    assert files
    for f in files:
        data = json.loads(f.read_text(encoding="utf-8"))
        assert f.stem in ITEMS or f.stem in HELP_BASICS, f.name     # имя файла — артефакт или умение мага
        assert len(data["view"]) == 4 and data["length"] > 0
        d = demos.Demo(data)
        for _ in range(int(data["length"] * 60) + 5):     # круг целиком и начало следующего
            d.update(1 / 60)


def test_lasso_pulls_runner_back():
    d = demos.Demo(demos.load("lasso"))
    start = d.match.red.x
    while d.t < 3.5:
        d.update(1 / 60)
    assert "lassoed" in d.match.red.effects or d.t > 3.9
    assert d.match.red.x < start - 100                     # бежал вправо, а оказался левее
    assert HERO_ONLY_ITEMS["lasso"] == d.match.blue.hero


def test_help_page_with_demo_draws(game):
    from duel.config import HELP_TABS
    game.state, game.help_page, game.help_full = "help", HELP_TABS.index("artifacts"), False
    game.open_land("fire")
    game.help_index = game.help_kinds().index("lasso")
    game.hits = []
    game.draw_help()
    assert "lasso" in game._demos
    game.help_full = True                       # во весь экран
    game.draw_help()
    game.help_full = False


def test_speed_slows_demo():
    """"speed": 0.5 — за секунду настоящего времени сценка проходит полсекунды."""
    walk = demos.load("walk")
    assert 0 < walk.get("speed", 1) < 1                    # ходьба показывается замедленно
    d = demos.Demo({**walk, "speed": 0.5})
    for _ in range(60):
        d.update(1 / 60)
    assert abs(d.t - 0.5) < 0.02


def test_new_demos_show_their_artifact():
    for kind, check in (("bear", lambda m: "bear" in m.blue.effects),
                        ("triple", lambda m: "triple" in m.blue.effects),
                        ("zombies", lambda m: any(x.zombie_of is m.blue for x in m.mobs))):
        d = demos.Demo(demos.load(kind))
        while d.t < 1.2:
            d.update(1 / 60)
        assert check(d.match), kind


def test_frost_and_light_demos():
    for kind, check in (("beam", lambda m: m.beams or m.red.hp < m.red.max_hp),
                        ("icewalk", lambda m: "icewalk" in m.blue.effects),
                        ("foe_freeze", lambda m: "freeze" in m.red.effects)):
        d = demos.Demo(demos.load(kind))
        while d.t < 0.9:
            d.update(1 / 60)
        assert check(d.match), kind


def test_demos_on_neutral_strip_except_foe_land():
    from duel.entities import zone_at
    for f in sorted(demos.DEMO_DIR.glob("*.json")):
        if f.stem in ("foe_land", "icewalk", "landswap", "firmground"):   # про землю и арену: маги там нарочно
            continue
        data = json.loads(f.read_text(encoding="utf-8"))
        for side in ("blue", "red"):
            s = data["setup"][side]
            if (s["x"], s["y"]) != (900, 600):           # «сосед где-то далеко» — не на виду
                assert zone_at(s["x"], s["y"]) == "neutral", (f.name, side)


def test_shield_demo_keeps_hp_until_shield_breaks():
    d = demos.Demo(demos.load("shield"))
    while d.t < 2.0:
        d.update(1 / 60)
    assert d.match.blue.hp == d.match.blue.max_hp and "shield" in d.match.blue.effects
    while d.t < 5.5:
        d.update(1 / 60)
    assert "shield" not in d.match.blue.effects and d.match.blue.hp < d.match.blue.max_hp


def test_demo_events_sound_and_music_goes_quiet(game, monkeypatch):
    """Сценка звучит (выстрелы, удары, артефакт), а музыка меню на это время затихает."""
    d = demos.Demo(demos.load("bear"))
    kinds = []
    while d.t < 3.0:
        d.update(1 / 60)
        kinds += [e[0] for e in d.take_events()]
    assert "used" in kinds and "melee" in kinds
    played = []
    monkeypatch.setattr(game.audio, "item", lambda k: played.append(("item", k)))
    monkeypatch.setattr(game.audio, "melee", lambda: played.append(("melee",)))
    game.event_sounds([("used", "blue", "bear"), ("melee", "blue")])
    assert played == [("item", "bear"), ("melee",)]
    music = []
    monkeypatch.setattr(game.audio, "music", music.append)
    game.state = "help"
    from duel.config import HELP_TABS
    game.help_page, game.help_index = HELP_TABS.index("mages"), 0      # «Маги» → «Ходьба» — есть сценка
    game.update_music()
    from duel.config import HELP_TABS
    game.help_page = HELP_TABS.index("rules")            # «Правила» — сценки нет
    game.update_music()
    game.state = "menu"
    game.update_music()
    assert music == ["quiet", "menu", "menu"]


def run_demo(kind, fps=60):
    """Прогнать сценку целиком с заданной частотой кадров; вернуть сведения по ходу."""
    from duel.entities import zone_at
    demos.reload_all()
    dm = demos.Demo(demos.load(kind))
    seen = {"zones": {}, "burn": {}, "mob_min": 99}
    while dm.t < dm.length - 0.1:                     # до конца по часам самой сценки
        dm.update(1 / fps)
        for p in dm.match.players:
            seen["zones"].setdefault(p.id, set()).add(zone_at(p.x, p.y))
            if dm.match.danger(p)[1]:
                seen["burn"].setdefault(p.id, set()).add(dm.match.danger(p)[1])
        for m in dm.match.mobs:
            seen["mob_min"] = min(seen["mob_min"], m.hp)
    return seen


def test_demos_show_their_point_even_at_low_fps():
    """Сценки показывают своё и при 4 кадрах в секунду (браузер): часы сценки идут с её партией."""
    for fps in (60, 4):
        land = run_demo("foe_land", fps)
        assert "red" in land["zones"]["blue"] and "blue" in land["zones"]["red"], fps    # дошли до чужой земли
        assert land["burn"] == {"blue": {"fire"}, "red": {"frost"}}, fps
        assert run_demo("bear", fps)["mob_min"] < 6, fps                                  # медведь добежал
        ice = run_demo("icewalk", fps)
        assert "red" in ice["zones"]["blue"] and "blue" not in ice["burn"], fps           # Холод по земле Огня — не горит
        assert ice["burn"].get("red") == {"frost"}, fps                                   # Огонь на тропе — горит морозом


def test_mobswap_rapid_and_bear_demos():
    """Сценки «Перевода стрелок» и «Скорострельности» показывают своё; медведь бьёт, только дойдя до моба."""
    import math as _m
    for fps in (60, 4):
        demos.reload_all()
        d = demos.Demo(demos.load("mobswap"))
        swapped = set()
        while d.t < d.length - 0.1:
            d.update(1 / fps)
            swapped |= {id(m) for m in d.match.mobs if m.swap > 0 and m.target is d.match.red}
        assert len(swapped) == 2, fps                     # оба моба ушли на соперника — с анимацией

        d = demos.Demo(demos.load("rapid"))
        while d.t < d.length - 0.1:
            d.update(1 / fps)
            if "rapid" in d.match.blue.effects:
                break
        assert "rapid" in d.match.blue.effects, fps

        d = demos.Demo(demos.load("bear"))
        was = False
        while d.t < d.length - 0.1:
            d.update(1 / fps)
            b = d.match.blue
            if b.melee_flash > 0 and not was and d.match.mobs and "bear" in b.effects:
                m = d.match.mobs[0]
                gap = _m.hypot(m.x - b.x, m.y - b.y) - m.radius - b.radius
                assert m.hp < m.max_hp, (fps, round(gap))  # каждый удар медведя — по мобу, не в воздух
            was = b.melee_flash > 0


def test_offstage_player_is_never_hit():
    """Соперник «за кадром» (offstage): отскочившие от стенок пули сквозь него — звуков попадания в сценке нет."""
    import glob
    import os
    for f in sorted(glob.glob(str(demos.DEMO_DIR / "*.json"))):
        kind = os.path.basename(f)[:-5]
        data = demos.load(kind)
        if not any((data["setup"].get(p) or {}).get("offstage") for p in ("blue", "red")):
            continue
        d = demos.Demo(data)
        hits = []
        while d.t < d.length - 0.05:
            d.update(1 / 30)
            hits += [e for e in d.take_events() if e[0] == "hit_mage"]
        assert not hits, kind
    assert demos.load("triple")["heroes"]["blue"] == "fire"      # веер — артефакт Огня
