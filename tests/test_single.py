"""Одна копия игры: вторая не запускается; блокировка снимается, когда первая закрылась."""
import os
import subprocess
import sys
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.mark.skipif(os.name == "nt", reason="на Windows — мьютекс, проверяется вручную")
def test_second_copy_refused(tmp_path):
    env = dict(os.environ, DUEL_SETTINGS=str(tmp_path / "s.json"), PYTHONPATH=ROOT)
    env.pop("DUEL_MULTI", None)
    hold = "from duel import single; import time; assert single.acquire(); print('ok', flush=True); time.sleep(3)"
    first = subprocess.Popen([sys.executable, "-c", hold], env=env, stdout=subprocess.PIPE, text=True, cwd=ROOT)
    try:
        assert first.stdout.readline().strip() == "ok"
        second = subprocess.run([sys.executable, "-c", "from duel import single; print(single.acquire())"],
                                env=env, capture_output=True, text=True, cwd=ROOT)
        assert second.stdout.strip() == "False"
    finally:
        first.kill()
        first.wait()
    time.sleep(0.1)
    again = subprocess.run([sys.executable, "-c", "from duel import single; print(single.acquire())"],
                           env=env, capture_output=True, text=True, cwd=ROOT)
    assert again.stdout.strip() == "True"                 # первая закрылась — можно снова
