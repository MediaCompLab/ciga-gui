"""Headless tests for the background workers against the installed CIGA package.

The workers are QThreads, but calling ``run()`` directly executes them on the test
thread, so no event loop or display is needed.
"""
import pandas as pd
import pytest

from src.ui.workers.analysis_worker import AnalysisWorker
from src.ui.workers.graph_worker import GraphWorker

ALL_METRICS = (
    "degree", "betweenness", "closeness", "harmonic", "eigenvector",
    "leiden", "multilevel", "label_propagation",
    "density", "transitivity", "is_connected", "diameter", "reciprocity",
)
POSITIONS = ["Season", "Episode", "Scene"]


def _annotations():
    return pd.DataFrame({
        "Season": [1, 1, 1, 2, 2],
        "Episode": [1, 1, 2, 1, 1],
        "Scene": [1, 2, 1, 1, 2],
        "Speaker": ["A", "B", "A", "C", "A"],
        "Listener": ["B", "A", "C", "A", "C"],
    })


def _build_tgraph(df=None, source="Speaker", target="Listener", positions=POSITIONS):
    result = {}
    worker = GraphWorker(_annotations() if df is None else df, source, target, positions, None)
    worker.finished.connect(lambda tgraph, error: result.update(tgraph=tgraph, error=error))
    worker.run()
    assert result["error"] is None
    return result["tgraph"]


def _run_analysis(tgraph, metrics, **options):
    result, progress = {}, []
    worker = AnalysisWorker(tgraph, True, True, False, dict.fromkeys(metrics, True), options)
    worker.progress.connect(lambda percent, message: progress.append((percent, message)))
    worker.finished.connect(lambda df, error: result.update(df=df, error=error))
    worker.run()
    return result, progress


def test_every_metric_runs_against_installed_ciga():
    result, _ = _run_analysis(_build_tgraph(), ALL_METRICS)

    assert result["error"] is None
    assert result["df"] is not None
    assert {"Season", "Episode", "Scene", "character"} <= set(result["df"].columns)


@pytest.mark.parametrize("metric", ["multilevel", "transitivity"])
def test_undirected_only_metrics_accept_directed_graphs(metric):
    tgraph = _build_tgraph()
    assert tgraph.is_directed

    result, _ = _run_analysis(tgraph, [metric])

    assert result["error"] is None
    assert not result["df"].empty


def test_progress_reports_individual_time_steps():
    _, progress = _run_analysis(_build_tgraph(), ["degree"])

    step_messages = [message for _, message in progress if "time steps" in message]
    assert step_messages, "per-step progress from CIGA's sequential driver was not captured"
    assert step_messages[-1] == "Degree Centrality: 5/5 time steps"


def _hooked_tqdms():
    # Whichever modules this ciga release runs its time-step loop in.
    import src.ui.workers.analysis_worker as worker_module

    hosts = worker_module._tqdm_hosts()
    assert hosts, "no tqdm host found in the installed ciga"
    return {module: module.tqdm for module in hosts}


def test_progress_hook_is_restored_after_analysis():
    originals = _hooked_tqdms()

    _run_analysis(_build_tgraph(), ["degree"])

    assert all(module.tqdm is original for module, original in originals.items())


def test_progress_hook_is_restored_when_a_metric_fails(monkeypatch):
    import src.ui.workers.analysis_worker as worker_module

    def broken(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(worker_module, "tgraph_degree_centrality", broken)
    originals = _hooked_tqdms()
    result, _ = _run_analysis(_build_tgraph(), ["degree"])

    assert result["error"] == "boom"
    assert all(module.tqdm is original for module, original in originals.items())


def test_metrics_still_run_when_no_progress_hook_is_found(monkeypatch):
    import src.ui.workers.analysis_worker as worker_module

    monkeypatch.setattr(worker_module, "_tqdm_hosts", lambda: [])
    result, progress = _run_analysis(_build_tgraph(), ["degree", "density"])

    assert result["error"] is None
    assert not any("time steps" in message for _, message in progress)


def test_decay_accumulation_runs():
    result, _ = _run_analysis(
        _build_tgraph(), ["degree"], decay_enabled=True, decay_rate=0.1, decay_mode="exponential"
    )

    assert result["error"] is None
    assert not result["df"].empty


def test_annotator_export_splits_multi_character_cells():
    df = pd.DataFrame({
        "line": ["Hi all", "Hello"],
        "speakers": ["Sheldon, Leonard", "Penny"],
        "listeners": ["Penny", "Sheldon, Leonard"],
        "position": [1, 2],
    })

    tgraph = _build_tgraph(df, "speakers", "listeners", ["position"])

    assert sorted(str(name) for name in tgraph.get_graph().vs["name"]) == ["Leonard", "Penny", "Sheldon"]


@pytest.mark.parametrize("weight_col", ["weight", "score"])
def test_custom_weight_column_is_used(weight_col):
    df = _annotations().assign(**{weight_col: [2.0, 1.0, 1.0, 1.0, 1.0]})
    result = {}
    worker = GraphWorker(df, "Speaker", "Listener", POSITIONS, weight_col)
    worker.finished.connect(lambda tgraph, error: result.update(tgraph=tgraph, error=error))
    worker.run()

    assert result["error"] is None
