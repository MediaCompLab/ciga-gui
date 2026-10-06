"""Exercise real file loading and graph construction for annotator CSVs."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QTWEBENGINE_DISABLE_SANDBOX', '1')

import pandas as pd
import pytest
from PySide6.QtWidgets import QApplication, QFileDialog
from PySide6.QtCore import QCoreApplication, QEvent
from src.ui.main_window import MainWindow
from src.ui.workers.graph_worker import GraphWorker


@pytest.fixture(scope='module')
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize('with_position', [False, True])
def test_annotator_csv_builds_without_manual_column_corrections(qapp, tmp_path, monkeypatch, with_position):
    df = pd.DataFrame({
        'line': ['Hello all', 'Hi'],
        'start_time': ['00:00:01,000', '00:00:03,000'],
        'end_time': ['00:00:02,000', '00:00:04,000'],
        'speakers': ['Alice', 'Bob'],
        'listeners': ['Bob, Charlie', 'Alice'],
        'targets': ['Bob', 'Alice'],
    })
    if with_position:
        df['position'] = [2, 4]  # Uncoded subtitles can leave gaps.
    path = tmp_path / 'annotations.csv'
    df.to_csv(path, index=False, encoding='utf-8-sig')
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *a, **k: (str(path), ''))
    window = MainWindow()
    try:
        window.load_file()
        assert window.cb_source.currentText() == 'speakers'
        assert window.cb_target.currentText() == 'listeners'
        positions = [item.text() for item in window.list_position.selectedItems()]
        assert positions == (['position'] if with_position else [])
        if not positions:
            positions = [window._ensure_auto_position_column()]
        result = {}
        worker = GraphWorker(window.df_raw, window.cb_source.currentText(), window.cb_target.currentText(), positions, None)
        worker.finished.connect(lambda graph, error: result.update(graph=graph, error=error))
        worker.run()
        assert result['error'] is None
        assert set(result['graph'].get_graph().vs['name']) == {'Alice', 'Bob', 'Charlie'}
        assert list(result['graph'].data.index.get_level_values('position').unique()) == ([2, 4] if with_position else [1, 2])
    finally:
        window.close()
        window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


@pytest.mark.parametrize('source,target', [('Speaker', 'Listener'), ('source', 'target'), (' Speakers ', ' Listeners ')])
def test_legacy_column_names_and_numeric_hierarchy(qapp, tmp_path, monkeypatch, source, target):
    path = tmp_path / 'legacy.csv'
    pd.DataFrame({source: ['A'], target: ['B'], 'Season': [1], 'Episode': [2], 'Scene': [3], 'time_note': ['later']}).to_csv(path, index=False)
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *a, **k: (str(path), ''))
    window = MainWindow()
    try:
        window.load_file()
        assert window.cb_source.currentText() == source
        assert window.cb_target.currentText() == target
        assert [item.text() for item in window.list_position.selectedItems()] == ['Season', 'Episode', 'Scene']
    finally:
        window.close()
        window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
