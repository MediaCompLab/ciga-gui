from PySide6.QtCore import QThread, Signal
import pandas as pd

from ciga.analysis import tgraph_degree, tgraph_betweenness, tgraph_closeness, tgraph_eigenvector_centrality
from ciga.analysis.tgraph_community_analysis import tgraph_community_leiden, tgraph_community_multilevel, tgraph_community_label_propagation
from ciga.analysis.tgraph_properties import tgraph_density, tgraph_transitivity_undirected, tgraph_is_connected, tgraph_diameter, tgraph_reciprocity

class AnalysisWorker(QThread):
    finished = Signal(object, object)  # df_final, error_message
    progress = Signal(int, str)  # percent, status_message

    def __init__(self, tgraph, acc, wtd, nrm, metrics_dict):
        super().__init__()
        self.tgraph = tgraph
        self.acc = acc
        self.wtd = wtd
        self.nrm = nrm
        self.metrics = metrics_dict

    def run(self):
        try:
            pos_cols = list(self.tgraph._position)
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
                self.progress.emit(percent, f"Calculating {metric_name}...")

            # 1. Centrality (Node-level)
            if self.metrics.get('degree'):
                self.progress.emit(int((current_step / total_metrics) * 100), "Calculating Degree Centrality...")
                res = tgraph_degree(self.tgraph, accumulate=self.acc, weighted=self.wtd, normalized=self.nrm)
                df_node = res if df_node is None else pd.merge(df_node, res, on=node_cols, how='outer')
                update_progress("Degree Centrality")

            if self.metrics.get('betweenness'):
                self.progress.emit(int((current_step / total_metrics) * 100), "Calculating Betweenness Centrality (This can take a while)...")
                inv_wt = "reciprocal" if self.wtd else False
                res = tgraph_betweenness(self.tgraph, accumulate=self.acc, weighted=self.wtd, invert_weight=inv_wt, normalized=self.nrm)
                df_node = res if df_node is None else pd.merge(df_node, res, on=node_cols, how='outer')
                update_progress("Betweenness Centrality")

            if self.metrics.get('closeness'):
                self.progress.emit(int((current_step / total_metrics) * 100), "Calculating Closeness Centrality...")
                inv_wt = "reciprocal" if self.wtd else False
                res = tgraph_closeness(self.tgraph, accumulate=self.acc, weighted=self.wtd, invert_weight=inv_wt, normalized=self.nrm)
                df_node = res if df_node is None else pd.merge(df_node, res, on=node_cols, how='outer')
                update_progress("Closeness Centrality")

            if self.metrics.get('eigenvector'):
                self.progress.emit(int((current_step / total_metrics) * 100), "Calculating Eigenvector Centrality...")
                res = tgraph_eigenvector_centrality(self.tgraph, accumulate=self.acc, weighted=self.wtd, scale=self.nrm)
                df_node = res if df_node is None else pd.merge(df_node, res, on=node_cols, how='outer')
                update_progress("Eigenvector Centrality")

            # 2. Community (Node-level)
            if self.metrics.get('leiden'):
                self.progress.emit(int((current_step / total_metrics) * 100), "Calculating Leiden Community...")
                res = tgraph_community_leiden(self.tgraph, accumulate=self.acc, w_normalized=self.nrm)
                df_node = res if df_node is None else pd.merge(df_node, res, on=node_cols, how='outer')
                update_progress("Leiden Community")

            if self.metrics.get('multilevel'):
                self.progress.emit(int((current_step / total_metrics) * 100), "Calculating Multilevel Community...")
                res = tgraph_community_multilevel(self.tgraph, accumulate=self.acc, w_normalized=self.nrm)
                df_node = res if df_node is None else pd.merge(df_node, res, on=node_cols, how='outer')
                update_progress("Multilevel Community")

            if self.metrics.get('label_propagation'):
                self.progress.emit(int((current_step / total_metrics) * 100), "Calculating Label Propagation Community...")
                res = tgraph_community_label_propagation(self.tgraph, accumulate=self.acc, w_normalized=self.nrm)
                df_node = res if df_node is None else pd.merge(df_node, res, on=node_cols, how='outer')
                update_progress("Label Propagation")

            # 3. Graph Properties (Graph-level)
            if self.metrics.get('density'):
                self.progress.emit(int((current_step / total_metrics) * 100), "Calculating Density...")
                res = tgraph_density(self.tgraph, accumulate=self.acc)
                df_graph = res if df_graph is None else pd.merge(df_graph, res, on=pos_cols, how='outer')
                update_progress("Density")

            if self.metrics.get('transitivity'):
                self.progress.emit(int((current_step / total_metrics) * 100), "Calculating Transitivity...")
                res = tgraph_transitivity_undirected(self.tgraph, accumulate=self.acc, w_normalized=self.nrm)
                df_graph = res if df_graph is None else pd.merge(df_graph, res, on=pos_cols, how='outer')
                update_progress("Transitivity")

            if self.metrics.get('is_connected'):
                self.progress.emit(int((current_step / total_metrics) * 100), "Calculating Connectivity Status...")
                res = tgraph_is_connected(self.tgraph, accumulate=self.acc)
                df_graph = res if df_graph is None else pd.merge(df_graph, res, on=pos_cols, how='outer')
                update_progress("Connected Status")

            if self.metrics.get('diameter'):
                self.progress.emit(int((current_step / total_metrics) * 100), "Calculating Diameter...")
                res = tgraph_diameter(self.tgraph, accumulate=self.acc, w_normalized=self.nrm)
                df_graph = res if df_graph is None else pd.merge(df_graph, res, on=pos_cols, how='outer')
                update_progress("Diameter")

            if self.metrics.get('reciprocity'):
                self.progress.emit(int((current_step / total_metrics) * 100), "Calculating Reciprocity...")
                res = tgraph_reciprocity(self.tgraph, accumulate=self.acc)
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
