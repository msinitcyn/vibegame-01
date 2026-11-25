"""Лаборатория баланса — командная строка (ядро — duel/lab.py; из игры — аддон «Лаборатория»).

    .venv/bin/python tools/lab.py report --games 600
    .venv/bin/python tools/lab.py --help        # все режимы и флаги

Подробно — в docstring duel/lab.py и в RUNBOOK.
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from duel.lab import main  # noqa: E402

if __name__ == "__main__":
    main()
