import unittest

import numpy as np

from run import R140, Ranker, blob


class DensityControls(unittest.TestCase):
    def test_dense_and_empty_negatives(self):
        scope = {}
        exec(blob('kpp', 'score.py', R140), scope)
        rank = Ranker(scope)
        view = np.zeros((50, 50), dtype=bool)
        view[:, 23] = True
        presence = np.ones_like(view)
        sparse = rank.score(view, view, presence, 0)
        dense = rank.score(view, presence, presence, 0)
        self.assertEqual(rank.pending, [1.0, 0.0])
        self.assertEqual(rank.decide({0: sparse, 90: dense}), 0)
        self.assertEqual(rank.answers.pop()['pick'], 0)
        empty = np.zeros_like(view)
        miss = np.roll(view, 10, axis=1)
        a = rank.score(view, empty, presence, 0)
        b = rank.score(view, miss, presence, 0)
        self.assertEqual(rank.pending, [-1.0, 0.0])
        rank.decide({0: a, 90: b})
        self.assertIsNone(rank.answers.pop()['pick'])


if __name__ == '__main__':
    unittest.main()
