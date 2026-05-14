from PySide6.QtCore import QThread, Signal
from ciga import TGraph
from ciga.utils import prepare_data, agg_weights

class GraphWorker(QThread):
    finished = Signal(object, object)  # tgraph, error_message

    def __init__(self, df_raw, source_col, target_col, selected_positions, weight_col, directed=True):
        super().__init__()
        self.df_raw = df_raw
        self.source_col = source_col
        self.target_col = target_col
        self.selected_positions = selected_positions
        self.weight_col = weight_col
        self.directed = directed

    def run(self):
        try:
            df_working = self.df_raw.dropna(subset=[self.source_col, self.target_col]).copy()
            if self.weight_col is None:
                # Hidden implementation detail for "Default (Count occurrences)".
                # agg_weights later turns these per-row ones into frequency weights.
                df_working['weight'] = 1.0
                actual_weight_col = 'weight'
            else:
                if self.weight_col != 'weight' and 'weight' in df_working.columns:
                    df_working.drop(columns=['weight'], inplace=True)
                df_working.rename(columns={self.weight_col: 'weight'}, inplace=True)
                actual_weight_col = 'weight'

            try:
                df_clean = prepare_data(
                    data=df_working, 
                    positions=tuple(self.selected_positions), 
                    source=self.source_col, 
                    target=self.target_col, 
                    weight=actual_weight_col
                )
                df_agg = agg_weights(df_clean, positions=tuple(self.selected_positions))
            except Exception as pipe_err:
                raise RuntimeError(f"Error during CIGA data preparation:\n{str(pipe_err)}")
            
            tgraph = TGraph(
                data=df_agg,
                positions=self.selected_positions,
                directed=self.directed
            )
            self.finished.emit(tgraph, None)
        except Exception as e:
            self.finished.emit(None, str(e))
