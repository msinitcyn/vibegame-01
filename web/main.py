"""Spellgunners в браузере (pygbag): тот же код игры, что на компьютере, свой вход.

Собрать и посмотреть (см. tools/build_web.py):
    .venv/bin/python tools/build_web.py        # build/web-src: этот файл + duel/ + assets/ (звуки — .ogg)
    .venv/bin/python -m pygbag build/web-src   # открыть http://localhost:8000

Отличия от компьютера — только в duel/platform.py (WEB): без сети, своего сервера и автообновления.
"""
import asyncio

from duel.game import Game


async def main():
    game = Game(windowed=True)
    await game.run_web()


asyncio.run(main())
