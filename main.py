"""Запуск игры Spellgunners. Подробности — в RUNBOOK.md.

    python main.py                                   # хотсит, полный экран
    python main.py --connect localhost --windowed    # сетевой клиент (сервер: python -m duel.server)
    python main.py --connect 192.168.1.5 --pad 1     # свой геймпад — второй по счёту
    python main.py --selftest                        # самопроверка без окна (код выхода 0 — всё работает)
    python main.py --replay logs/replays/….json.gz   # повтор партии (см. duel/replay.py)
"""
import argparse
import os


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()     # собранная игра: процессы лаборатории (аддон) запускают этот же exe
    ap = argparse.ArgumentParser(description="Spellgunners")
    ap.add_argument("--connect", metavar="АДРЕС", help="подключиться к серверу (host или host:port)")
    ap.add_argument("--windowed", action="store_true", help="в окне, а не на весь экран")
    ap.add_argument("--pad", type=int, default=0, help="номер своего геймпада (с 0) в сетевой игре")
    ap.add_argument("--selftest", action="store_true", help="самопроверка без окна и звука")
    ap.add_argument("--replay", metavar="ФАЙЛ", help="показать повтор партии (logs/replays/*.json.gz)")
    ap.add_argument("--movie", metavar="РОЛИК", help="показать ролик assets/movies/<РОЛИК> (Esc — в меню)")
    args = ap.parse_args()
    if args.selftest:
        from duel.selftest import run
        raise SystemExit(run())
    # одна копия игры (DUEL_MULTI=1 — можно несколько, для проверки сети на одном компьютере); повтор — рядом с игрой
    if not os.environ.get("DUEL_MULTI") and not args.replay:
        from duel import settings, single
        from duel.i18n import set_lang, t
        if not single.acquire():
            set_lang(settings.load().get("lang", "en"))
            single.tell_already_running(t("already_running"))
            raise SystemExit(0)
    net = None
    if args.connect:
        # кнопки геймпада доходят и до окна без фокуса — два клиента на одном компьютере
        os.environ["SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS"] = "1"
        from duel import settings
        from duel.net import connect
        try:
            net = (*connect(args.connect, name=settings.load().get("name", "").strip()), args.connect)
        except (ConnectionError, OSError) as e:
            raise SystemExit(f"не удалось подключиться к {args.connect}: {e}")
    import pygame
    from duel import logs
    from duel.game import Game
    logs.setup()                       # лог и файлы падений — в папке настроек, logs/
    try:
        replay = None
        if args.replay:
            from duel.replay import load
            replay = load(args.replay)
        Game(windowed=args.windowed or bool(args.replay), net=net, pad=args.pad, replay=replay,
             movie=args.movie, intro=not (net or args.replay or args.movie)).run()
    except Exception as e:
        logs.report_crash(e)
        raise
    finally:
        logs.log.info("выход")
    pygame.quit()
