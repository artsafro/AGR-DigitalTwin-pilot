from docs.research.trainer_stated_band_r106.replay import stated


def test_stated_scope_is_half_open_and_filters_floors():
    rows = [
        (1, 'Wall', [1, 2, 4.65], [4, 6, 7]),
        (2, 'Wall', [0, 3, 7], [5, 7, 8]),
        (3, 'Wall', [-99, -99, 8], [99, 99, 9]),
        (4, 'Перекрытие example', [-9, -9, 7], [9, 9, 8]),
        (5, 'Wall', [-8, -8, 4.64], [8, 8, 7]),
    ]
    expected = {'ids': [1, 2], 'bounds_m': [[0, 2, 4.65], [5, 7, 8]]}
    assert stated(rows, (4.65, 8), 'Перекрытие') == expected
    assert stated(list(reversed(rows)), (4.65, 8), 'Перекрытие') == expected
    assert stated(rows, None, 'Перекрытие') is None
    assert stated(rows, (8.5, 9), 'Перекрытие') is None
