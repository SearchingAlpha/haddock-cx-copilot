"""Clustering scores: evals/clustering.py, docs/specs/evals.md (Radar)."""

from evals.clustering import accuracy, ari, per_problem, scores


def test_ari_is_one_for_the_same_partition_with_other_names():
    assert ari(["a", "a", "b", "b"], ["x", "x", "y", "y"]) == 1.0


def test_ari_known_value():
    # sklearn.metrics.adjusted_rand_score([0, 0, 1, 1], [0, 0, 1, 2]) == 0.5714285714285715
    assert round(ari([0, 0, 1, 1], [0, 0, 1, 2]), 6) == 0.571429


def test_scores_reward_keeping_noise_out():
    truth = {"1": "P1", "2": "P1", "3": None, "4": None}
    perfect = scores({"1": "A", "2": "A"}, truth)
    assert perfect["ari"] == 1.0 and perfect["purity"] == 1.0 and perfect["noise_kept_out"] == 1.0
    noisy = scores({"1": "A", "2": "A", "3": "A"}, truth)
    assert noisy["noise_in_problems"] == 1 and noisy["purity"] == round(2 / 3, 3)


def test_mixed_and_split_problems_are_counted():
    truth = {"1": "P1", "2": "P1", "3": "P2", "4": "P2"}
    pred = {"1": "A", "2": "B", "3": "B", "4": "B"}
    s = scores(pred, truth)
    assert s["mixed_problems"] == 1 and s["problems_found"] == 2
    found = {"B": {"status": "candidate", "detected_at": "2026-09-03T10:00:00", "detected_at_n": 3}}
    created = {"1": "2026-09-01T10:00:00", "2": "2026-09-02T10:00:00", "3": "2026-09-02T11:00:00",
               "4": "2026-09-03T10:00:00"}
    planted = {"P1": {"title": "x", "start": "2026-09-01"}, "P2": {"title": "y", "start": "2026-09-02"}}
    rows = {r["planted"]: r for r in per_problem(pred, truth, planted, found, created)}
    assert rows["P1"]["splits"] == 2 and rows["P1"]["main_share"] == 0.5
    assert rows["P2"]["main_problem"] == "B" and rows["P2"]["days_to_detect"] == round(34 / 24, 1)
    assert rows["P2"]["planted_before_detection"] == 2


def test_accuracy_only_on_planted_tickets():
    labels = {"1": {"entity": "Revo", "problem_id": "P3"}, "2": {"entity": None, "problem_id": None}}
    signals = [{"ticket_id": "1", "entity": "Revo"}, {"ticket_id": "2", "entity": "BBVA"}]
    assert accuracy(signals, labels, "entity") == 0.5
    assert accuracy(signals, labels, "entity", only_planted=True) == 1.0
