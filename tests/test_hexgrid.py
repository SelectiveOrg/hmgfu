from hmgfu import hexgrid
from hmgfu.models import Hex


def test_cube_invariant_neighbours():
    for n in hexgrid.neighbours(Hex(2, -1, -1)):
        assert n.q + n.r + n.s == 0


def test_distance():
    assert hexgrid.hex_distance(Hex(0, 0, 0), Hex(0, 0, 0)) == 0
    assert hexgrid.hex_distance(Hex(0, 0, 0), Hex(1, 0, -1)) == 1
    assert hexgrid.hex_distance(Hex(0, 0, 0), Hex(3, -1, -2)) == 3


def test_ring_sizes():
    assert len(hexgrid.ring(Hex(), 1)) == 6
    assert len(hexgrid.ring(Hex(), 2)) == 12
    assert len(hexgrid.ring(Hex(), 3)) == 18
    # all at the right distance
    assert all(hexgrid.hex_distance(Hex(), h) == 2 for h in hexgrid.ring(Hex(), 2))


def test_spiral_is_dense_and_unique():
    cells = list(hexgrid.spiral(Hex(), 3))
    keys = {c.key() for c in cells}
    assert len(keys) == len(cells) == 1 + 6 + 12 + 18


def test_round_cube_valid():
    h = hexgrid.round_cube(0.9, -0.4, -0.5)
    assert h.q + h.r + h.s == 0


def test_weighted_centroid_pulls_toward_heavy():
    a, b = Hex(0, 0, 0), Hex(6, -6, 0)
    c = hexgrid.weighted_centroid([(a, 10.0), (b, 0.1)])
    assert hexgrid.hex_distance(c, a) < hexgrid.hex_distance(c, b)


def test_nearest_free_skips_occupied():
    occupied = {Hex(0, 0, 0).key(): "x"}
    free = hexgrid.nearest_free_hex(Hex(0, 0, 0), occupied)
    assert free.key() != Hex(0, 0, 0).key()
    assert hexgrid.hex_distance(free, Hex(0, 0, 0)) == 1
