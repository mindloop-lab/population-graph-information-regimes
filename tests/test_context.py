from audit.graph import random_context_draws, site_matched_context_draws


def test_random_draw_is_order_invariant() -> None:
    first = random_context_draws("q", ["q", "a", "b", "c"], 2, 3, 1024)
    second = random_context_draws("q", ["c", "b", "q", "a"], 2, 3, 1024)
    assert first == second
    assert all("q" not in draw.context_ids for draw in first)


def test_site_matched_draws_have_equal_size_and_expected_sites() -> None:
    pool = ["q", "s1", "s2", "x1", "x2", "x3"]
    sites = {"q": "A", "s1": "A", "s2": "A", "x1": "B", "x2": "C", "x3": "C"}
    pairs = site_matched_context_draws("q", pool, sites, cap=2, draws=2, seed=9)
    assert len(pairs) == 2
    for same, cross in pairs:
        assert len(same.context_ids) == len(cross.context_ids) == 2
        assert all(sites[subject_id] == "A" for subject_id in same.context_ids)
        assert all(sites[subject_id] != "A" for subject_id in cross.context_ids)
