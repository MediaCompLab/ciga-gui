from PySide6.QtCore import QThread, Signal
from contextlib import contextmanager
import pandas as pd

from ciga import TGraph
from ciga.utils import accumulate_weights
from ciga.analysis import tgraph_degree_centrality, tgraph_betweenness_centrality, tgraph_closeness_centrality, tgraph_harmonic_centrality, tgraph_eigenvector_centrality
from ciga.analysis.tgraph_community_analysis import tgraph_community_leiden, tgraph_community_multilevel, tgraph_community_label_propagation
from ciga.analysis.tgraph_properties import tgraph_density, tgraph_transitivity_undirected, tgraph_is_connected, tgraph_diameter, tgraph_reciprocity
import ciga.analysis.tgraph_centrality_analysis as tgraph_centrality_module
import ciga.analysis.tgraph_community_analysis as tgraph_community_module
import ciga.analysis.tgraph_properties as tgraph_properties_module

class AnalysisWorker(QThread):
    finished = Signal(object, object)  # df_final, error_message
    progress = Signal(int, str)  # percent, status_message

    def __init__(self, tgraph, accumulate, weighted, normalized, metrics_dict, analysis_options=None):
        super().__init__()
        self.tgraph = tgraph
        self.accumulate = accumulate
        self.weighted = weighted
        self.normalized = normalized
        self.metrics = metrics_dict
        self.options = analysis_options or {}
        self.start_bound = self.options.get('start')
        self.end_bound = self.options.get('end')
        self.window_size = self.options.get('window_size')
        self.stride = self.options.get('stride', 1)
        self.w_normalized = self.options.get('w_normalized', False)
        self.invert_weight = self.options.get('invert_weight', 'auto')
        self.mean_weight = self.options.get('mean_weight', False)
        self.decay_enabled = self.options.get('decay_enabled', False)
        self.decay_rate = self.options.get('decay_rate', 0.0)
        self.decay_mode = self.options.get('decay_mode', 'exponential')
        if self.window_size is not None:
            self.accumulate = False
        if self.decay_enabled:
            self.accumulate = False

    def _scope_kwargs(self):
        return {
            'start': self.start_bound,
            'end': self.end_bound,
            'accumulate': self.accumulate,
            'window_size': self.window_size,
            'stride': self.stride,
        }

    def _path_invert_weight(self):
        if not self.weighted:
            return False
        if self.invert_weight == 'auto':
            return 'reciprocal'
        if self.invert_weight == 'none':
            return False
        return self.invert_weight

    def _prepared_tgraph(self):
        if not self.decay_enabled:
            return self.tgraph

        self.progress.emit(0, "Preparing decayed weights...")
        positions = tuple(self.tgraph._position)
        decayed_data = accumulate_weights(
            self.tgraph.data.reset_index(),
            positions=positions,
            decay=self.decay_rate,
            decay_mode=self.decay_mode,
            accum_mode='auto',
            ltm_rate=0.0,
        )
        return TGraph(data=decayed_data, positions=positions, directed=self.tgraph.is_directed)

    def _emit_metric_progress(self, metric_index, total_metrics, completed_steps, total_steps, metric_name):
        if total_metrics <= 0:
            return

        metric_fraction = 0.0
        if total_steps:
            metric_fraction = completed_steps / total_steps

        percent = int(((metric_index + metric_fraction) / total_metrics) * 100)
        percent = max(0, min(percent, 99))

        if total_steps:
            message = f"{metric_name}: {completed_steps}/{total_steps} time steps"
        else:
            message = f"Calculating {metric_name}..."
        self.progress.emit(percent, message)

    @contextmanager
    def _sync_ciga_tqdm(self, metric_name, metric_index, total_metrics):
        modules = (tgraph_centrality_module, tgraph_community_module, tgraph_properties_module)
        originals = [(module, module.tqdm) for module in modules]
        fallback_tqdm = originals[0][1]

        def gui_tqdm(iterable=None, *args, **kwargs):
            if iterable is None:
                return fallback_tqdm(iterable, *args, **kwargs)

            total = kwargs.get('total')
            if total is None:
                try:
                    total = len(iterable)
                except TypeError:
                    total = None

            self._emit_metric_progress(metric_index, total_metrics, 0, total, metric_name)

            def progress_iter():
                completed = 0
                for item in iterable:
                    yield item
                    completed += 1
                    self._emit_metric_progress(metric_index, total_metrics, completed, total, metric_name)

            return progress_iter()

        try:
            for module, _ in originals:
                module.tqdm = gui_tqdm
            yield
        finally:
            for module, original in originals:
                module.tqdm = original

    def run(self):
        try:
            analysis_tgraph = self._prepared_tgraph()
            pos_cols = list(analysis_tgraph._position)
            node_cols = pos_cols + ['character']
            df_node = None
            df_graph = None

            # Calculate total metrics to compute for progress tracking
            selected_metrics = [k for k, v in self.metrics.items() if v]
            total_metrics = len(selected_metrics)
            if total_metrics == 0:
                self.finished.emit(None, None)
                return

            current_step = 0

            def update_progress(metric_name):
                nonlocal current_step
                current_step += 1
                percent = int((current_step / total_metrics) * 100)
                self.progress.emit(percent, f"Finished {metric_name}.")

            # 1. Centrality (Node-level)
            if self.metrics.get('degree'):
                self.progress.emit(int((current_step / total_metrics) * 100), "Calculating Degree Centrality...")
                with self._sync_ciga_tqdm("Degree Centrality", current_step, total_metrics):
                    res = tgraph_degree_centrality(
                        analysis_tgraph,
                        **self._scope_kwargs(),
                        weighted=self.weighted,
                        w_normalized=self.w_normalized,
                        normalized=self.normalized,
                        mean_weight=self.mean_weight,
                    )
                df_node = res if df_node is None else pd.merge(df_node, res, on=node_cols, how='outer')
                update_progress("Degree Centrality")

            if self.metrics.get('betweenness'):
                self.progress.emit(int((current_step / total_metrics) * 100), "Calculating Betweenness Centrality (This can take a while)...")
                inv_wt = self._path_invert_weight()
                with self._sync_ciga_tqdm("Betweenness Centrality", current_step, total_metrics):
                    res = tgraph_betweenness_centrality(
                        analysis_tgraph,
                        **self._scope_kwargs(),
                        weighted=self.weighted,
                        w_normalized=self.w_normalized,
                        invert_weight=inv_wt,
                        normalized=self.normalized,
                        mean_weight=self.mean_weight,
                    )
                df_node = res if df_node is None else pd.merge(df_node, res, on=node_cols, how='outer')
                update_progress("Betweenness Centrality")

            if self.metrics.get('closeness'):
                self.progress.emit(int((current_step / total_metrics) * 100), "Calculating Closeness Centrality...")
                inv_wt = self._path_invert_weight()
                with self._sync_ciga_tqdm("Closeness Centrality", current_step, total_metrics):
                    res = tgraph_closeness_centrality(
                        analysis_tgraph,
                        **self._scope_kwargs(),
                        weighted=self.weighted,
                        w_normalized=self.w_normalized,
                        invert_weight=inv_wt,
                        normalized=self.normalized,
                        mean_weight=self.mean_weight,
                    )
                df_node = res if df_node is None else pd.merge(df_node, res, on=node_cols, how='outer')
                update_progress("Closeness Centrality")

            if self.metrics.get('harmonic'):
                self.progress.emit(int((current_step / total_metrics) * 100), "Calculating Harmonic Centrality...")
                inv_wt = self._path_invert_weight()
                with self._sync_ciga_tqdm("Harmonic Centrality", current_step, total_metrics):
                    res = tgraph_harmonic_centrality(
                        analysis_tgraph,
                        **self._scope_kwargs(),
                        weighted=self.weighted,
                        w_normalized=self.w_normalized,
                        invert_weight=inv_wt,
                        normalized=self.normalized,
                        mean_weight=self.mean_weight,
                    )
                df_node = res if df_node is None else pd.merge(df_node, res, on=node_cols, how='outer')
                update_progress("Harmonic Centrality")

            if self.metrics.get('eigenvector'):
                self.progress.emit(int((current_step / total_metrics) * 100), "Calculating Eigenvector Centrality...")
                with self._sync_ciga_tqdm("Eigenvector Centrality", current_step, total_metrics):
                    res = tgraph_eigenvector_centrality(
                        analysis_tgraph,
                        **self._scope_kwargs(),
                        weighted=self.weighted,
                        w_normalized=self.w_normalized,
                        scale=self.normalized,
                        mean_weight=self.mean_weight,
                    )
                df_node = res if df_node is None else pd.merge(df_node, res, on=node_cols, how='outer')
                update_progress("Eigenvector Centrality")

            # 2. Community (Node-level)
            if self.metrics.get('leiden'):
                self.progress.emit(int((current_step / total_metrics) * 100), "Calculating Leiden Community...")
                with self._sync_ciga_tqdm("Leiden Community", current_step, total_metrics):
                    res = tgraph_community_leiden(
                        analysis_tgraph,
                        **self._scope_kwargs(),
                        w_normalized=self.w_normalized,
                        mean_weight=self.mean_weight,
                    )
                df_node = res if df_node is None else pd.merge(df_node, res, on=node_cols, how='outer')
                update_progress("Leiden Community")

            if self.metrics.get('multilevel'):
                self.progress.emit(int((current_step / total_metrics) * 100), "Calculating Multilevel Community...")
                with self._sync_ciga_tqdm("Multilevel Community", current_step, total_metrics):
                    res = tgraph_community_multilevel(
                        analysis_tgraph,
                        **self._scope_kwargs(),
                        w_normalized=self.w_normalized,
                        mean_weight=self.mean_weight,
                    )
                df_node = res if df_node is None else pd.merge(df_node, res, on=node_cols, how='outer')
                update_progress("Multilevel Community")

            if self.metrics.get('label_propagation'):
                self.progress.emit(int((current_step / total_metrics) * 100), "Calculating Label Propagation Community...")
                with self._sync_ciga_tqdm("Label Propagation", current_step, total_metrics):
                    res = tgraph_community_label_propagation(
                        analysis_tgraph,
                        **self._scope_kwargs(),
                        w_normalized=self.w_normalized,
                        mean_weight=self.mean_weight,
                    )
                df_node = res if df_node is None else pd.merge(df_node, res, on=node_cols, how='outer')
                update_progress("Label Propagation")

            # 3. Graph Properties (Graph-level)
            if self.metrics.get('density'):
                self.progress.emit(int((current_step / total_metrics) * 100), "Calculating Density...")
                with self._sync_ciga_tqdm("Density", current_step, total_metrics):
                    res = tgraph_density(
                        analysis_tgraph,
                        **self._scope_kwargs(),
                        w_normalized=self.w_normalized,
                        mean_weight=self.mean_weight,
                    )
                df_graph = res if df_graph is None else pd.merge(df_graph, res, on=pos_cols, how='outer')
                update_progress("Density")

            if self.metrics.get('transitivity'):
                self.progress.emit(int((current_step / total_metrics) * 100), "Calculating Transitivity...")
                with self._sync_ciga_tqdm("Transitivity", current_step, total_metrics):
                    res = tgraph_transitivity_undirected(
                        analysis_tgraph,
                        **self._scope_kwargs(),
                        w_normalized=self.w_normalized,
                        mean_weight=self.mean_weight,
                    )
                df_graph = res if df_graph is None else pd.merge(df_graph, res, on=pos_cols, how='outer')
                update_progress("Transitivity")

            if self.metrics.get('is_connected'):
                self.progress.emit(int((current_step / total_metrics) * 100), "Calculating Connectivity Status...")
                with self._sync_ciga_tqdm("Connected Status", current_step, total_metrics):
                    res = tgraph_is_connected(analysis_tgraph, **self._scope_kwargs())
                df_graph = res if df_graph is None else pd.merge(df_graph, res, on=pos_cols, how='outer')
                update_progress("Connected Status")

            if self.metrics.get('diameter'):
                self.progress.emit(int((current_step / total_metrics) * 100), "Calculating Diameter...")
                with self._sync_ciga_tqdm("Diameter", current_step, total_metrics):
                    res = tgraph_diameter(
                        analysis_tgraph,
                        **self._scope_kwargs(),
                        weighted=self.weighted,
                        w_normalized=self.w_normalized,
                        mean_weight=self.mean_weight,
                    )
                df_graph = res if df_graph is None else pd.merge(df_graph, res, on=pos_cols, how='outer')
                update_progress("Diameter")

            if self.metrics.get('reciprocity'):
                self.progress.emit(int((current_step / total_metrics) * 100), "Calculating Reciprocity...")
                with self._sync_ciga_tqdm("Reciprocity", current_step, total_metrics):
                    res = tgraph_reciprocity(analysis_tgraph, **self._scope_kwargs())
                df_graph = res if df_graph is None else pd.merge(df_graph, res, on=pos_cols, how='outer')
                update_progress("Reciprocity")

            self.progress.emit(100, "Merging results...")
            
            # Merge node and graph dataframes
            if df_node is not None and df_graph is not None:
                df_final = pd.merge(df_node, df_graph, on=pos_cols, how='left')
            elif df_node is not None:
                df_final = df_node
            elif df_graph is not None:
                df_final = df_graph
            else:
                df_final = None

            self.finished.emit(df_final, None)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.finished.emit(None, str(e))
