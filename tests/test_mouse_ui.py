"""Мышь в меню: наведение выбирает пункт, левая кнопка нажимает, правая — назад."""
import pygame

from duel import i18n


def redraw(game, draw):
    game.hits = []
    draw()


def point(game, i=None, pred=None):
    """Центр отмеченного места: по номеру или первого, подходящего под условие (по Rect)."""
    hits = [h for h in game.hits if pred is None or pred(h[0])]
    return hits[i or 0][0].center


def click(game, pos, button=1):
    game.on_mouse_move(pos)
    game.on_mouse_button(button)


def test_menu_hover_and_click(game):
    game.state = "menu"
    game.menu_index = 0
    redraw(game, game.draw_menu)
    help_i = game.menu.index("help")
    pos = game.hits[help_i][0].center
    game.on_mouse_move(pos)
    assert game.menu_index == help_i                  # наведение выбирает
    game.on_mouse_button(1)
    assert game.state == "help"
    click(game, (10, 400), button=3)                  # правая — назад
    assert game.state == "menu"
    click(game, (10, 400), button=3)                  # в главном меню правая ничего не делает (Esc — выход!)
    assert game.state == "menu"
    redraw(game, game.draw_menu)
    pygame.event.clear(pygame.QUIT)
    click(game, (70, game.screen.get_height() - 30))  # «Выход»
    assert pygame.event.get(pygame.QUIT)


def test_help_pages_by_halves_and_back_button(game):
    game.state, game.help_page = "help", 0
    redraw(game, game.draw_help)
    click(game, (900, 400))
    assert game.help_page == 1
    redraw(game, game.draw_help)
    click(game, (100, 400))
    assert game.help_page == 0
    redraw(game, game.draw_help)
    click(game, (44, 30))                             # «←»
    assert game.state == "menu"


def test_settings_arrows_by_half(game):
    i18n.set_lang("ru")
    game.state, game.settings_index = "settings", 0
    redraw(game, game.draw_settings)
    lang = game.hits[game.settings_rows.index("lang")][0]
    click(game, (lang.right - 20, lang.centery))      # правая половина — «▶»
    assert i18n.get_lang() == "en"
    redraw(game, game.draw_settings)
    click(game, (lang.left + 20, lang.centery))       # левая — «◀»
    assert i18n.get_lang() == "ru"
    redraw(game, game.draw_settings)
    back = game.hits[game.settings_rows.index("back")][0]
    click(game, back.center)
    assert game.state == "menu"


def test_pick_heroes_with_mouse(game):
    game.settings["aim_mode"] = "move"
    game.open_pick(10)
    redraw(game, game.draw_pick)
    cards = [h[0] for h in game.hits[:-1]]            # 5 героев × 2 строки (последнее — «←»)
    game.on_mouse_move(cards[2].center)               # наведение — третий герой у синего
    assert game.pick["blue"]["hero"] == "nature"
    game.on_mouse_button(1)                           # щелчок по выбранному — подтвердить
    assert game.pick["blue"]["ok"]
    click(game, cards[5 + 4].center)                  # красный — пятый герой: выбрать
    click(game, cards[5 + 4].center)                  # и подтвердить — партия
    assert game.state == "play" and game.match.red.hero == "light"


def test_own_server_room_and_lobby_buttons(game):
    from tests.test_net_menu import frames, warm_frames
    game.state = "menu"
    redraw(game, game.draw_menu)
    click(game, game.hits[game.menu.index("net")][0].center)
    assert game.state == "join"
    redraw(game, game.draw_join)
    create = next(h[0] for h in game.hits if h[0].w == 640 and h[0].y > 500)
    click(game, create.center)                        # «Создать свой сервер»
    assert game.host_server and game.state == "rooms"
    frames(game, lambda: game.lobby_server)
    redraw(game, game.draw_rooms)
    click(game, game.hits[1][0].center)               # «Создать комнату»
    assert game.net and game.state == "play"
    frames(game, lambda: game.net_seats and game.net_waiting)
    redraw(game, game.draw_lobby)
    buttons = [h for h in game.hits if h[0].h == 40]  # Готов, Бот, Разминка, Выйти
    assert len(buttons) == 4
    click(game, buttons[0][0].center)                 # Готов
    frames(game, lambda: game.my_ready())
    redraw(game, game.draw_lobby)
    buttons = [h for h in game.hits if h[0].h == 40]
    click(game, buttons[2][0].center)                 # Разминка
    assert game.warmup
    warm_frames(game, lambda: True)
    game.on_key(pygame.KSCAN_ESCAPE)
    redraw(game, game.draw_lobby)
    buttons = [h for h in game.hits if h[0].h == 40]
    click(game, buttons[3][0].center)                 # Выйти — к комнатам
    assert game.state == "rooms"


def test_win_screen_click_restarts(game):
    game.start()
    game.match.red.hp = 0
    game.update(1 / 60)
    game.win_time = pygame.time.get_ticks() - 2000
    redraw(game, game.draw)
    click(game, (500, 400))
    assert not game.snap["winner"]


def test_hover_draws_highlight_without_crash(game):
    game.state = "update"
    game.updater.state, game.updater.error = "error", "download"
    redraw(game, game.draw_update)
    retry = game.hits[0][0]
    game.on_mouse_move(retry.center)
    redraw(game, game.draw_update)                    # кнопка под курсором — подсвечена
    click(game, game.hits[1][0].center)               # «В меню»
    assert game.state == "menu"
