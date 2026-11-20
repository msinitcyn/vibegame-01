# Design

- `UNIT_SCALE` и `unit(size)` в config — размеры фигур считаются от прежних чисел.
- Волна k: `MOB_COUNT + k + max(0, k − (MOB_MAX_HP − MOB_HP)) · MOB_LATE_EXTRA`, предел `MOB_MAX = 16`.
- Выбор героя: `pick_keys(pid)` из `self.controls`; `mouse_quiet` после нажатия клавиши, наведение — только при сдвиге ≥ 4 px от `hover_from`.
