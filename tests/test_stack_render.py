"""Все артефакты по нескольку раз обоим магам — партия и картинка не падают (эффекты складываются,
времени больше полной длительности — анимации не уходят «в минус»)."""
import pygame
import pytest

from duel import render
from duel.config import HEROES
from duel.items import ITEMS
from duel.match import Match
from duel.snapshot import snapshot


@pytest.mark.parametrize("heroes", [dict(blue=a, red=b) for a, b in zip(HEROES, HEROES[1:] + HEROES[:1])])
def test_spam_all_artifacts_and_draw(heroes):
    pygame.font.init()
    font = pygame.font.Font(None, 14)
    m = Match(seed=5, heroes=heroes)
    m.blue.max_hp = m.red.max_hp = m.blue.hp = m.red.hp = 1000
    surf = pygame.Surface((1000, 720))
    for rnd in range(3):
        for kind in ITEMS:
            for p in m.players:
                m.apply_item(p, kind)
                m.apply_item(p, kind)                  # дважды подряд — время сверх длительности
        for i in range(90):
            m.step(1 / 60)
            if i % 15 == 0:
                snap = snapshot(m)
                for viewer in (None, "blue", "red"):
                    render.draw_field(surf, snap, font, viewer)
