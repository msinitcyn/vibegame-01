"""Повторы — в «Настройки → Дополнительно»: сохранять ли, папка, список записанных партий и просмотр."""
import pygame

from duel import config, settings
from duel.commands import Command
from duel.match import Match
from duel.replay import Recorder


def write_replay(folder, tuning=None):
    m = Match(seed=3, heroes={"blue": "fire", "red": "earth"})
    rec = Recorder(m, "lab", players={"blue": "hard · hero", "red": "easy · rush"}, tuning=tuning or [])
    for _ in range(30):
        c = {"blue": Command(move=(1, 0)), "red": Command()}
        rec.tick(c)
        m.step(1 / 60, c)
    return rec.save(folder, m, sub="")


def open_advanced(game):
    game.state = "settings"
    game.settings_index = game.settings_rows.index("advanced")
    game.on_key(pygame.KSCAN_RETURN)
    assert game.settings_page == "advanced" and game.settings_rows == game.advanced_rows


def test_replays_not_in_main_menu(game):
    assert "replays" not in game.menu


def test_advanced_settings_folder_list_and_watch(game, tmp_path):
    open_advanced(game)
    game.settings_index = game.settings_rows.index("replay_dir")
    game.on_text(str(tmp_path))                        # путь набирается в строке
    assert game.settings["replay_dir"] == str(tmp_path)
    assert settings.load()["replay_dir"] == str(tmp_path)
    game.draw_settings()
    path = write_replay(game.replay_folder(), ["BASE_SPEED=170"])
    game.settings_index = game.settings_rows.index("replays")
    game.on_key(pygame.KSCAN_RETURN)
    assert game.state == "replays" and game.replay_list[0]["path"] == path
    game.draw_replays()
    game.on_key(pygame.KSCAN_RETURN)                   # то же нажатие / двойной щелчок — повтор не запускает
    assert game.state == "replays" and game.replay is None
    game.replays_opened -= 1000
    game.on_key(pygame.KSCAN_RETURN)
    assert game.replay is not None and game.match.blue.speed == 170
    game.on_key(pygame.KSCAN_ESCAPE)                   # из повтора — в список
    assert game.replay is None and game.state == "replays"
    assert Match(seed=1).blue.speed == config.BASE_SPEED
    game.on_key(pygame.KSCAN_ESCAPE)                   # из списка — в «Дополнительно»
    assert game.state == "settings" and game.settings_page == "advanced"
    game.on_key(pygame.KSCAN_ESCAPE)                   # из «Дополнительно» — на главную страницу настроек
    assert game.settings_page == "main" and game.settings_rows[game.settings_index] == "advanced"
    game.settings["replay_dir"] = ""


def test_save_replays_switch(game):
    open_advanced(game)
    game.settings_index = game.settings_rows.index("save_replays")
    game.on_key(pygame.KSCAN_RETURN)
    assert game.settings["save_replays"] is False
    game.on_key(pygame.KSCAN_RETURN)
    assert game.settings["save_replays"] is True
    game.close_advanced()


def test_replay_dir_backspace(game):
    open_advanced(game)
    game.settings_index = game.settings_rows.index("replay_dir")
    game.settings["replay_dir"] = "/tmp/ab"
    game.on_key(pygame.KSCAN_BACKSPACE)
    assert game.settings["replay_dir"] == "/tmp/a"
    game.settings["replay_dir"] = ""
    game.close_advanced()


def test_click_selects_then_second_click_watches(game, tmp_path):
    game.settings["replay_dir"] = str(tmp_path)
    write_replay(tmp_path)
    write_replay(tmp_path)
    game.open_replays()
    game.replays_opened -= 1000
    assert len(game.replay_list) == 2 and game.replay_index == 0
    game.replay_click(1)                                # первый щелчок — выбрать
    assert game.replay_index == 1 and game.replay is None
    game.replay_click(1)                                # второй — смотреть
    assert game.replay is not None
    game.close_replay()
    game.settings["replay_dir"] = ""


def test_menu_screens_show_frame(game, monkeypatch):
    """Каждый экран меню выводит кадр на дисплей (иначе картинка застывает — «Повторы» так и висели)."""
    flips = []
    monkeypatch.setattr(pygame.display, "flip", lambda: flips.append(1))
    for state, prep in (("replays", game.open_replays), ("settings", None), ("menu", None), ("help", None)):
        if prep:
            prep()
        game.state = state
        flips.clear()
        game.screen_frame(1 / 60)
        assert flips, state


def test_lab_run_folders_switch_with_arrows(game):
    from duel.replay import lab_root, summary, write_index
    run = lab_root() / "20991231-235959-report-normal"
    run.mkdir(parents=True, exist_ok=True)
    p1 = write_replay(run)
    write_index(run, {p1.name: {**summary({"mode": "lab", "heroes": {"blue": "fire", "red": "earth"}}),
                                "winner": "red", "time": 42}})
    game.open_replays()
    assert len(game.replay_folders) >= 2 and game.replay_folder_i == 0
    game.on_key(pygame.KSCAN_RIGHT)                     # → самый новый прогон лаборатории
    assert game.shown_replay_folder() == run
    assert game.replay_list[0]["path"] == p1 and game.replay_list[0]["winner"] == "red"   # из оглавления
    game.draw_replays()
    game.on_key(pygame.KSCAN_LEFT)
    assert game.replay_folder_i == 0
    game.replay_index = 0
    game.on_event(pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=-1, flipped=False))


def test_folder_without_index_is_read_lazily(game, tmp_path, monkeypatch):
    """Папка без оглавления (прогон ещё идёт): список открывается сразу, файлы читаются по видимым строкам."""
    from duel import replay as rp
    for _ in range(12):
        write_replay(tmp_path)
    game.settings["replay_dir"] = str(tmp_path)
    reads = []
    real = rp.load
    monkeypatch.setattr("duel.client_menus.replay_load", lambda p: reads.append(p) or real(p))
    game.open_replays()
    assert len(game.replay_list) == 12 and not reads          # открыть — ничего не читая
    for _ in range(12):
        game.draw_replays()
    assert len(reads) == 9                                     # только видимые строки, по одной за кадр
    assert game.replay_list[0]["mode"] == "lab"
    game.settings["replay_dir"] = ""
