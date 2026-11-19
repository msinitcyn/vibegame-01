"""Запуск игры «Дуэль шариков». Подробности — в RUNBOOK.md.

    python main.py                                   # хотсит, полный экран
    python main.py --connect localhost --windowed    # сетевой клиент (сервер: python -m duel.server)
    python main.py --connect 192.168.1.5 --pad 1     # свой геймпад — второй по счёту
"""
import argparse
import os


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Дуэль шариков")
    ap.add_argument("--connect", metavar="АДРЕС", help="подключиться к серверу (host или host:port)")
    ap.add_argument("--windowed", action="store_true", help="в окне, а не на весь экран")
    ap.add_argument("--pad", type=int, default=0, help="номер своего геймпада (с 0) в сетевой игре")
    args = ap.parse_args()
    net = None
    if args.connect:
        # кнопки геймпада доходят и до окна без фокуса — два клиента на одном компьютере
        os.environ["SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS"] = "1"
        from duel.net import connect
        try:
            net = connect(args.connect)
        except (ConnectionError, OSError) as e:
            raise SystemExit(f"не удалось подключиться к {args.connect}: {e}")
    import pygame
    from duel.game import Game
    Game(windowed=args.windowed, net=net, pad=args.pad).run()
    pygame.quit()
