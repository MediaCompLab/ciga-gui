from PySide6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
                               QPushButton, QLabel, QComboBox, QCheckBox,
                               QGroupBox, QTabWidget, QTableWidget, QTableWidgetItem,
                               QFileDialog, QListWidget, QAbstractItemView, QMessageBox, QApplication, QProgressDialog, QDialog, QPlainTextEdit,
                               QLineEdit, QSpinBox, QDoubleSpinBox, QScrollArea)
from PySide6.QtGui import QAction
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import Qt, QUrl
import pandas as pd
import sys
import os
import tempfile
import socket
import threading

import ciga
from ciga import TGraph

from .workers.graph_worker import GraphWorker
from .workers.analysis_worker import AnalysisWorker
from .dialogs.custom_weight_dialog import CustomWeightDialog

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._viz_server = None
        self.setWindowTitle("CIGA GUI")
        self.resize(1000, 700)

        self._create_menu_bar()

        # Central Widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # Left Panel (Controls)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_panel.setMinimumWidth(280)

        self._setup_left_panel(left_layout)
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFixedWidth(310)
        left_scroll.setWidget(left_panel)

        # Right Panel (Tabs)
        self.tabs = QTabWidget()
        
        self.tab_raw_data = QWidget()
        self.tab_analysis = QWidget()
        self.tab_viz = QWidget()

        self.tabs.addTab(self.tab_raw_data, "Raw Data")
        self.tabs.addTab(self.tab_analysis, "Analysis Results")
        self.tabs.addTab(self.tab_viz, "Visualization")

        self._setup_right_panel()

        # Add panels to main layout
        main_layout.addWidget(left_scroll)
        main_layout.addWidget(self.tabs)

    def _create_menu_bar(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("File")
        help_menu = menu_bar.addMenu("Help")

        load_action = QAction("Load Data...", self)
        load_action.triggered.connect(self.load_file)
        file_menu.addAction(load_action)

        export_action = QAction("Export Analysis Results...", self)
        export_action.triggered.connect(self.export_analysis_csv)
        file_menu.addAction(export_action)
        
        file_menu.addSeparator()

        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        about_action = QAction("About CIGA", self)
        about_action.triggered.connect(self.show_about_dialog)
        help_menu.addAction(about_action)

    def show_about_dialog(self):
        msg = QMessageBox(self)
        msg.setWindowTitle("About CIGA GUI")
        msg.setTextFormat(Qt.RichText)
        msg.setText(
            "<h3>CIGA: Character Interaction and Graph Analysis</h3>"
            "<p><b>CIGA GUI</b></p>"
            "<p><b>Version: 1.0.0</b></p>"
            "<p>A temporal graph based tool for visualizing and analyzing character interactions.</p>"
            "<p><i>Developed by: <a href='http://mediacomplab.com'>Media Comprehension Lab</a></i></p>"
            "<p>For more information, visit our <a href='https://github.com/MediaComprehensionLab/CIGA'>GitHub Repository</a>.</p>"
            "<p>If you find CIGA useful, please consider citing our work:"
            "<pre>@article{mcl2025ciga,\n  title={CIGA: Character Interaction and Graph Analysis for Video},\n  author={Media Comprehension Lab},\n  year={2025}\n}</pre></p>"
        )
        msg.exec()

    def _setup_left_panel(self, layout):
        # 1. Data Import Group
        data_group = QGroupBox("1. Data Import")
        data_layout = QVBoxLayout()
        self.btn_load_csv = QPushButton("Load CSV / XLSX...")
        self.lbl_file_path = QLabel("No file loaded")
        self.lbl_file_path.setWordWrap(True)
        self.lbl_file_path.setStyleSheet("color: gray; font-size: 11px;")
        
        data_layout.addWidget(self.btn_load_csv)
        data_layout.addWidget(self.lbl_file_path)
        data_group.setLayout(data_layout)

        # 2. Graph Config Group
        graph_group = QGroupBox("2. Graph Configuration")
        graph_layout = QVBoxLayout()
        self.cb_source = QComboBox()
        self.cb_target = QComboBox()
        self.cb_graph_type = QComboBox()
        self.cb_graph_type.addItems(["Directed", "Undirected"])
        self.cb_graph_type.setToolTip("Choose whether source-target direction should be preserved.")
        
        # Make position a multi-select list widget to support MultiIndex
        self.list_position = QListWidget()
        self.list_position.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.list_position.setFixedHeight(60)
        self.list_position.setToolTip("Hold Ctrl/Cmd to select multiple columns for hierarchical position (MultiIndex).")
        self.chk_auto_position = QCheckBox("Auto position if missing")
        self.chk_auto_position.setChecked(True)
        self.chk_auto_position.setToolTip("When no position column is selected, create a numeric position column from row order.")
        
        # Add Weight column selection
        self.cb_weight = QComboBox()
        self.cb_weight.setToolTip("Select a column specifying edge weights, or leave as Default (Count).")
        
        # Base items
        for cb in [self.cb_source, self.cb_target, self.cb_weight]:
            cb.addItem("-- Select Column --")
            
        self.cb_weight.setItemText(0, "-- Default (Count occurrences) --")

        graph_layout.addWidget(QLabel("Source (e.g. Speaker):"))
        graph_layout.addWidget(self.cb_source)
        graph_layout.addWidget(QLabel("Target (e.g. Listener):"))
        graph_layout.addWidget(self.cb_target)
        graph_layout.addWidget(QLabel("Graph Type:"))
        graph_layout.addWidget(self.cb_graph_type)
        graph_layout.addWidget(QLabel("Position(s) (e.g. Scene/Time):"))
        graph_layout.addWidget(self.list_position)
        graph_layout.addWidget(self.chk_auto_position)
        
        # Add a visual separator or grouping for edge weighting
        graph_layout.addWidget(QLabel("Edge Weight Column (Optional):"))
        graph_layout.addWidget(self.cb_weight)
        
        self.btn_custom_weight = QPushButton("Compute Custom Weights...")
        self.btn_custom_weight.setToolTip("Define a custom Python function to compute weights based on an interaction column.")
        self.btn_custom_weight.setEnabled(False)
        graph_layout.addWidget(self.btn_custom_weight)

        self.btn_build_graph = QPushButton("Build TGraph")
        self.btn_build_graph.setEnabled(False)
        graph_layout.addWidget(self.btn_build_graph)
        graph_group.setLayout(graph_layout)

        # 3. Analysis Group
        analysis_group = QGroupBox("3. Calculate Metrics")
        analysis_layout = QVBoxLayout()
        
        # TGraph Status Label
        self.lbl_graph_status = QLabel("TGraph not built yet.")
        self.lbl_graph_status.setStyleSheet("color: blue; font-weight: bold;")
        self.lbl_graph_status.setWordWrap(True)
        analysis_layout.addWidget(self.lbl_graph_status)
        
        self.chk_accumulate = QCheckBox("Accumulate dynamically")
        self.chk_accumulate.setChecked(True)
        self.chk_accumulate.setToolTip("If true, calculates metrics on cumulative edges up to each time step.")

        self.chk_weighted = QCheckBox("Use Weights")
        self.chk_weighted.setChecked(True)

        self.chk_normalized = QCheckBox("Normalize metric scores")
        self.chk_normalized.setChecked(True)

        # Temporal scope controls
        scope_box = QGroupBox("Temporal Scope")
        scope_layout = QVBoxLayout(scope_box)

        self.spin_window_size = QSpinBox()
        self.spin_window_size.setRange(0, 1000000)
        self.spin_window_size.setSpecialValueText("Off")
        self.spin_window_size.setToolTip("If set, each metric uses only the most recent N time steps. Overrides Accumulate dynamically.")

        self.spin_stride = QSpinBox()
        self.spin_stride.setRange(1, 1000000)
        self.spin_stride.setValue(1)
        self.spin_stride.setToolTip("Analyze every Nth time step.")

        window_stride_layout = QHBoxLayout()
        window_stride_layout.addWidget(QLabel("Window:"))
        window_stride_layout.addWidget(self.spin_window_size)
        window_stride_layout.addWidget(QLabel("Stride:"))
        window_stride_layout.addWidget(self.spin_stride)
        scope_layout.addLayout(window_stride_layout)

        self.edit_start_bound = QLineEdit()
        self.edit_start_bound.setPlaceholderText("Start, e.g. 1 or 1,1,1")
        self.edit_start_bound.setToolTip("Optional inclusive start position. Use comma-separated values for multi-level positions.")
        self.edit_end_bound = QLineEdit()
        self.edit_end_bound.setPlaceholderText("End, e.g. 10 or 1,2,5")
        self.edit_end_bound.setToolTip("Optional inclusive end position. Use comma-separated values for multi-level positions.")
        scope_layout.addWidget(self.edit_start_bound)
        scope_layout.addWidget(self.edit_end_bound)

        # Weight handling controls
        weight_box = QGroupBox("Weight Handling")
        weight_layout = QVBoxLayout(weight_box)

        self.chk_graph_weight_normalized = QCheckBox("Normalize graph weights")
        self.chk_graph_weight_normalized.setToolTip("Normalize edge weights before metric calculation. This is separate from metric-score normalization.")

        self.cb_invert_weight = QComboBox()
        self.cb_invert_weight.addItem("Auto invert path weights", "auto")
        self.cb_invert_weight.addItem("Do not invert weights", "none")
        self.cb_invert_weight.addItem("Reciprocal inversion", "reciprocal")
        self.cb_invert_weight.addItem("Max-minus inversion", "max_minus")
        self.cb_invert_weight.setToolTip("For weighted betweenness, closeness, and harmonic centrality, igraph treats weights as distance/cost.")

        self.chk_mean_weight = QCheckBox("Average accumulated/window weights")
        self.chk_mean_weight.setToolTip("Divide accumulated or windowed edge weights by the number of time steps represented.")

        self.chk_decay_weights = QCheckBox("Apply decay accumulation")
        self.chk_decay_weights.setToolTip("Precompute decayed cumulative weights before metric calculation. This is the forgetting simulation mode.")

        self.spin_decay_rate = QDoubleSpinBox()
        self.spin_decay_rate.setRange(0.0, 0.99)
        self.spin_decay_rate.setSingleStep(0.05)
        self.spin_decay_rate.setDecimals(2)
        self.spin_decay_rate.setValue(0.10)
        self.spin_decay_rate.setToolTip("Decay rate. For exponential decay, values must be in [0, 1).")

        self.cb_decay_mode = QComboBox()
        self.cb_decay_mode.addItem("Exponential decay", "exponential")
        self.cb_decay_mode.addItem("Power-law decay", "power_law")
        self.cb_decay_mode.addItem("Linear decay", "linear")

        weight_layout.addWidget(self.chk_graph_weight_normalized)
        weight_layout.addWidget(QLabel("Path weight mode:"))
        weight_layout.addWidget(self.cb_invert_weight)
        weight_layout.addWidget(self.chk_mean_weight)
        weight_layout.addWidget(self.chk_decay_weights)

        decay_layout = QHBoxLayout()
        decay_layout.addWidget(QLabel("Decay:"))
        decay_layout.addWidget(self.spin_decay_rate)
        weight_layout.addLayout(decay_layout)
        weight_layout.addWidget(self.cb_decay_mode)
        
        # Metrics setup
        self.metrics_tabs = QTabWidget()
        
        # Centrality
        cent_widget = QWidget()
        cent_layout = QVBoxLayout(cent_widget)
        self.chk_degree = QCheckBox("Degree Centrality")
        self.chk_degree.setChecked(True)
        self.chk_betweenness = QCheckBox("Betweenness Centrality")
        self.chk_closeness = QCheckBox("Closeness Centrality")
        self.chk_harmonic = QCheckBox("Harmonic Centrality")
        self.chk_eigenvector = QCheckBox("Eigenvector Centrality")
        for cb in [self.chk_degree, self.chk_betweenness, self.chk_closeness, self.chk_harmonic, self.chk_eigenvector]:
            cent_layout.addWidget(cb)
        cent_layout.addStretch()
        self.metrics_tabs.addTab(cent_widget, "Centrality")
        
        # Community
        comm_widget = QWidget()
        comm_layout = QVBoxLayout(comm_widget)
        self.chk_leiden = QCheckBox("Leiden Community")
        self.chk_multilevel = QCheckBox("Multilevel Community")
        self.chk_label_prop = QCheckBox("Label Propagation")
        for cb in [self.chk_leiden, self.chk_multilevel, self.chk_label_prop]:
            comm_layout.addWidget(cb)
        comm_layout.addStretch()
        self.metrics_tabs.addTab(comm_widget, "Community")

        # Global Properties
        prop_widget = QWidget()
        prop_layout = QVBoxLayout(prop_widget)
        self.chk_density = QCheckBox("Density")
        self.chk_transitivity = QCheckBox("Transitivity")
        self.chk_is_connected = QCheckBox("Is Connected")
        self.chk_diameter = QCheckBox("Diameter")
        self.chk_reciprocity = QCheckBox("Reciprocity")
        for cb in [self.chk_density, self.chk_transitivity, self.chk_is_connected, self.chk_diameter, self.chk_reciprocity]:
            prop_layout.addWidget(cb)
        prop_layout.addStretch()
        self.metrics_tabs.addTab(prop_widget, "Global")
        
        metrics_box = QGroupBox("Metrics")
        box_layout = QVBoxLayout(metrics_box)
        box_layout.addWidget(self.metrics_tabs)
        
        self.btn_run_analysis = QPushButton("Run Analysis")
        self.btn_run_analysis.setEnabled(False)
        
        # Add to analysis layout
        analysis_layout.addWidget(self.chk_accumulate)
        analysis_layout.addWidget(self.chk_weighted)
        analysis_layout.addWidget(self.chk_normalized)
        analysis_layout.addWidget(scope_box)
        analysis_layout.addWidget(weight_box)
        analysis_layout.addWidget(metrics_box)
        analysis_layout.addWidget(self.btn_run_analysis)
        analysis_group.setLayout(analysis_layout)

        # Add groups to left panel layout
        layout.addWidget(data_group)
        layout.addWidget(graph_group)
        layout.addWidget(analysis_group)
        layout.addStretch() # Push everything to the top

        # Connect button signals (mock functionality for demo)
        self.btn_load_csv.clicked.connect(self.load_file)
        self.btn_build_graph.clicked.connect(self.build_tgraph)
        self.btn_custom_weight.clicked.connect(self.open_custom_weight_dialog)
        self.btn_run_analysis.clicked.connect(self.run_analysis)

    def _setup_right_panel(self):
        # --- TAB 1: Raw Data ---
        layout1 = QVBoxLayout(self.tab_raw_data)
        self.table_raw_data = QTableWidget()
        layout1.addWidget(QLabel("Raw Data Preview:"))
        layout1.addWidget(self.table_raw_data)
        
        # --- TAB 2: Analysis Results ---
        layout2 = QVBoxLayout(self.tab_analysis)
        self.table_analysis = QTableWidget()
        
        # Tools for Analysis Tab
        tools_layout = QHBoxLayout()
        self.lbl_analysis_status = QLabel("Ready for analysis.")
        self.btn_export_csv = QPushButton("Export Results to CSV")
        self.btn_export_csv.setEnabled(False)
        self.btn_export_csv.clicked.connect(self.export_analysis_csv)
        
        tools_layout.addWidget(self.lbl_analysis_status)
        tools_layout.addStretch()
        tools_layout.addWidget(self.btn_export_csv)
        
        layout2.addLayout(tools_layout)
        layout2.addWidget(self.table_analysis)
        
        # --- TAB 3: Visualization ---
        layout3 = QVBoxLayout(self.tab_viz)
        
        # Tools for Visualization
        viz_tools_layout = QHBoxLayout()
        self.btn_gen_viz = QPushButton("Generate Visualization")
        self.btn_gen_viz.setEnabled(False)
        self.btn_gen_viz.clicked.connect(self.generate_visualization)
        viz_tools_layout.addWidget(self.btn_gen_viz)
        viz_tools_layout.addStretch()
        
        layout3.addLayout(viz_tools_layout)
        
        self.web_view = QWebEngineView()
        
        # Connect download requests (like the Export SVG button from the web page) to our save handler
        self.web_view.page().profile().downloadRequested.connect(self.handle_download)
        
        # Ensure it has something to show initially or leave it blank
        self.web_view.setHtml("<html><body style='display:flex;justify-content:center;align-items:center;height:100vh;color:gray;font-family:sans-serif;'>Generate a visualization to see it here.</body></html>")
        layout3.addWidget(self.web_view)

    def load_dataframe_to_table(self, df: pd.DataFrame, table_widget: QTableWidget, max_rows=1000):
        """Helper function to load a pandas DataFrame into a QTableWidget."""
        table_widget.clear()
        
        # Limit the display rows to avoid freezing the GUI on huge files
        display_df = df.head(max_rows)
        
        table_widget.setRowCount(display_df.shape[0])
        table_widget.setColumnCount(display_df.shape[1])
        table_widget.setHorizontalHeaderLabels(display_df.columns.astype(str))

        for row in range(display_df.shape[0]):
            for col in range(display_df.shape[1]):
                val = display_df.iloc[row, col]
                # Convert everything to string safely, handle NaNs
                str_val = "" if pd.isna(val) else str(val)
                item = QTableWidgetItem(str_val)
                # Keep items read-only for basic preview
                item.setFlags(item.flags() ^ Qt.ItemFlag.ItemIsEditable) 
                table_widget.setItem(row, col, item)

        table_widget.resizeColumnsToContents()

    def load_file(self):
        # Open file dialog
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Data File", "", 
            "Data Files (*.csv *.xlsx);;CSV Files (*.csv);;Excel Files (*.xlsx)"
        )
        
        if file_path:
            self.lbl_file_path.setText(f"...{file_path[-35:]}")
            
            try:
                # 1. Read Data using Pandas
                if file_path.endswith('.csv'):
                    self.df_raw = pd.read_csv(file_path)
                else:
                    self.df_raw = pd.read_excel(file_path)
                self.df_raw.columns = [str(col) for col in self.df_raw.columns]
                
                # 2. Display Data in QTableWidget
                self.load_dataframe_to_table(self.df_raw, self.table_raw_data)
                
                # 3. Populate Form Controls with DataFrame Columns
                columns = self.df_raw.columns.tolist()
                
                for cb in [self.cb_source, self.cb_target, self.cb_weight]:
                    # For weight we keep the default option at index 0
                    if cb == self.cb_weight:
                        cb.clear()
                        cb.addItem("-- Default (Count occurrences) --")
                        cb.addItems(columns)
                    else:
                        cb.clear()
                        cb.addItem("-- Select Column --")
                        cb.addItems(columns)
                
                self.list_position.clear()
                self.list_position.addItems(columns)
                
                # Attempt to auto-select common columns if they exist
                lower_cols = [c.strip().casefold() for c in columns]
                for combo, aliases in (
                    (self.cb_source, ('speaker', 'speakers', 'source')),
                    (self.cb_target, ('listener', 'listeners', 'target', 'targets')),
                ):
                    for alias in aliases:
                        if alias in lower_cols:
                            combo.setCurrentIndex(lower_cols.index(alias) + 1)
                            break
                    
                # For position, try common temporal/order columns first.
                for i, col in enumerate(lower_cols):
                    if (('scene' in col or 'time' in col or 'position' in col
                         or col in ('season', 'episode'))
                            and pd.api.types.is_numeric_dtype(self.df_raw[columns[i]])):
                        self.list_position.item(i).setSelected(True)

                self.btn_build_graph.setEnabled(True)
                self.btn_run_analysis.setEnabled(True)
                self.btn_custom_weight.setEnabled(True)
                
                # Switch focus to the Raw Data Tab
                self.tabs.setCurrentWidget(self.tab_raw_data)
                
            except Exception as e:
                QMessageBox.critical(self, "Error Loading File", f"Could not read file:\n{str(e)}")

    def open_custom_weight_dialog(self):
        if not hasattr(self, 'df_raw') or self.df_raw is None:
            return
            
        columns = self.df_raw.columns.tolist()
        dialog = CustomWeightDialog(self, columns)
        
        # Pre-select 'interaction' if it exists
        lower_cols = [c.lower() for c in columns]
        if 'interaction' in lower_cols:
            dialog.cb_inter_col.setCurrentIndex(lower_cols.index('interaction'))
            
        if dialog.exec() == QDialog.Accepted:
            code, col_name = dialog.get_function_and_column()
            
            local_env = {}
            try:
                exec(code, {}, local_env)
                if 'custom_weight' not in local_env:
                    QMessageBox.warning(self, "Error", "The code must define a function named 'custom_weight'.")
                    return
                    
                func = local_env['custom_weight']
                
                # Apply function
                temp_col = self.df_raw[col_name]
                self.df_raw['weight'] = temp_col.apply(func)
                
                # Refresh columns in UI and select the new column
                self._refresh_columns_after_custom_weight('weight')
                self.load_dataframe_to_table(self.df_raw, self.table_raw_data)
                
                QMessageBox.information(self, "Success", f"Computed weights added as 'weight' column and selected.")
                
            except Exception as e:
                QMessageBox.critical(self, "Execution Error", f"Failed to compute weights:\n{str(e)}")

    def _refresh_columns_after_custom_weight(self, new_col):
        columns = self.df_raw.columns.tolist()
        for cb in [self.cb_source, self.cb_target, self.cb_weight]:
            curr = cb.currentText()
            if cb == self.cb_weight:
                cb.clear()
                cb.addItem("-- Default (Count occurrences) --")
                cb.addItems(columns)
                if new_col in columns:
                    cb.setCurrentText(new_col)
                else:
                    cb.setCurrentText(curr)
            else:
                cb.clear()
                cb.addItem("-- Select Column --")
                cb.addItems(columns)
                cb.setCurrentText(curr)
                
        selected = [item.text() for item in self.list_position.selectedItems()]
        self.list_position.clear()
        self.list_position.addItems(columns)
        for i in range(self.list_position.count()):
            if self.list_position.item(i).text() in selected:
                self.list_position.item(i).setSelected(True)

    def _ensure_auto_position_column(self):
        """Create and select a numeric row-order position column when none is provided."""
        columns = self.df_raw.columns.tolist()
        base_name = "position"
        position_col = base_name
        if position_col in columns:
            suffix = 1
            while f"__ciga_position_{suffix}" in columns:
                suffix += 1
            position_col = f"__ciga_position_{suffix}"

        self.df_raw[position_col] = range(1, len(self.df_raw) + 1)

        for cb in [self.cb_source, self.cb_target, self.cb_weight]:
            cb.addItem(position_col)

        self.list_position.addItem(position_col)
        self.list_position.item(self.list_position.count() - 1).setSelected(True)
        self.load_dataframe_to_table(self.df_raw, self.table_raw_data)
        return position_col

    def build_tgraph(self):
        """Construct the TGraph using the user's column selections."""
        if not hasattr(self, 'df_raw') or self.df_raw is None:
            return
            
        source_col = self.cb_source.currentText()
        target_col = self.cb_target.currentText()
        directed = self.cb_graph_type.currentText() == "Directed"
        
        selected_positions = [item.text() for item in self.list_position.selectedItems()]
        
        weight_col_text = self.cb_weight.currentText()
        weight_col = weight_col_text if not weight_col_text.startswith("-- Default") else None

        if source_col.startswith("--") or target_col.startswith("--"):
            QMessageBox.warning(self, "Missing Columns", "Please select valid Source and Target columns.")
            return
            
        if len(selected_positions) == 0 and self.chk_auto_position.isChecked():
            selected_positions = [self._ensure_auto_position_column()]

        if len(selected_positions) == 0:
            QMessageBox.warning(self, "Missing Position", "Please select at least one Position column (e.g. Scene/Time).")
            return

        self.btn_build_graph.setEnabled(False)
        self.lbl_graph_status.setText("Building TGraph... please wait.")
        self.lbl_graph_status.setStyleSheet("color: orange;")
        
        # Show progress dialog
        self.tgraph_prog = QProgressDialog("Building TGraph...", None, 0, 0, self)
        self.tgraph_prog.setWindowTitle("Please Wait")
        self.tgraph_prog.setWindowModality(Qt.WindowModality.WindowModal)
        self.tgraph_prog.setMinimumDuration(0)
        self.tgraph_prog.show()

        # Start background worker
        self.tgraph_worker = GraphWorker(self.df_raw, source_col, target_col, selected_positions, weight_col, directed)
        self.tgraph_worker.finished.connect(self._on_tgraph_built)
        self.tgraph_worker.start()

    def _on_tgraph_built(self, tgraph, error_msg):
        self.btn_build_graph.setEnabled(True)
        if hasattr(self, 'tgraph_prog'):
            self.tgraph_prog.close()

        if error_msg:
            self.lbl_graph_status.setText("Failed to build TGraph.")
            self.lbl_graph_status.setStyleSheet("color: red;")
            QMessageBox.critical(self, "Error Building TGraph", f"An error occurred while building the TGraph:\n{error_msg}\n\nPlease ensure your columns match requirements.")
            return

        self.tgraph = tgraph
        num_time_steps = len(self.tgraph.data.index.unique())
        total_edges = len(self.tgraph.data)
        
        graph_type = "Directed" if self.tgraph.is_directed else "Undirected"
        success_msg = f"TGraph built successfully!\n• {graph_type}\n• {num_time_steps} Time Step(s)\n• {total_edges} Distinct Edge(s)"
        self.lbl_graph_status.setText(success_msg)
        self.lbl_graph_status.setStyleSheet("color: green;")
        
        self.btn_run_analysis.setEnabled(True)
        self.btn_gen_viz.setEnabled(True)
        self.tabs.setCurrentWidget(self.tab_analysis)

    def _parse_position_bound(self, text, label):
        """Parse a user-entered position bound into a numeric tuple."""
        text = text.strip()
        if not text:
            return None

        parts = [part.strip() for part in text.replace(";", ",").split(",") if part.strip()]
        if len(parts) > len(self.tgraph._position):
            raise ValueError(f"{label} has {len(parts)} values, but the TGraph uses {len(self.tgraph._position)} position column(s).")

        values = []
        for part in parts:
            try:
                if any(ch in part.lower() for ch in [".", "e"]):
                    value = float(part)
                    if value.is_integer():
                        value = int(value)
                else:
                    value = int(part)
            except ValueError as exc:
                raise ValueError(f"{label} must be numeric. Could not parse '{part}'.") from exc
            values.append(value)

        return tuple(values)

    def run_analysis(self):
        """Run selected metrics and merge them into a result DataFrame."""
        if not hasattr(self, 'tgraph') or self.tgraph is None:
            QMessageBox.warning(self, "No TGraph", "Please build the TGraph first.")
            return

        accumulate = self.chk_accumulate.isChecked()
        weighted = self.chk_weighted.isChecked()
        normalized = self.chk_normalized.isChecked()

        try:
            start_bound = self._parse_position_bound(self.edit_start_bound.text(), "Start")
            end_bound = self._parse_position_bound(self.edit_end_bound.text(), "End")
        except ValueError as e:
            QMessageBox.warning(self, "Invalid Temporal Scope", str(e))
            return

        window_size = self.spin_window_size.value() or None
        if window_size is not None:
            accumulate = False

        stride = self.spin_stride.value()
        mean_weight = self.chk_mean_weight.isChecked()
        decay_enabled = self.chk_decay_weights.isChecked()
        if decay_enabled and window_size is not None:
            QMessageBox.warning(
                self,
                "Invalid Temporal Scope",
                "Decay accumulation already defines a memory window. Turn Window off before using decay accumulation."
            )
            return

        if decay_enabled and mean_weight:
            QMessageBox.warning(
                self,
                "Invalid Weight Handling",
                "Decay accumulation cannot be combined with Average accumulated/window weights."
            )
            return

        if mean_weight and not accumulate and window_size is None:
            QMessageBox.warning(
                self,
                "Invalid Weight Handling",
                "Average accumulated/window weights requires Accumulate dynamically or a Window size."
            )
            return

        analysis_options = {
            'start': start_bound,
            'end': end_bound,
            'window_size': window_size,
            'stride': stride,
            'w_normalized': self.chk_graph_weight_normalized.isChecked(),
            'invert_weight': self.cb_invert_weight.currentData(),
            'mean_weight': mean_weight,
            'decay_enabled': decay_enabled,
            'decay_rate': self.spin_decay_rate.value(),
            'decay_mode': self.cb_decay_mode.currentData(),
        }
        if decay_enabled:
            accumulate = False
        
        metrics_dict = {
            'degree': self.chk_degree.isChecked(),
            'betweenness': self.chk_betweenness.isChecked(),
            'closeness': self.chk_closeness.isChecked(),
            'harmonic': self.chk_harmonic.isChecked(),
            'eigenvector': self.chk_eigenvector.isChecked(),
            'leiden': self.chk_leiden.isChecked(),
            'multilevel': self.chk_multilevel.isChecked(),
            'label_propagation': self.chk_label_prop.isChecked(),
            'density': self.chk_density.isChecked(),
            'transitivity': self.chk_transitivity.isChecked(),
            'is_connected': self.chk_is_connected.isChecked(),
            'diameter': self.chk_diameter.isChecked(),
            'reciprocity': self.chk_reciprocity.isChecked()
        }

        if not any(metrics_dict.values()):
            QMessageBox.warning(self, "No Metrics", "Please select at least one metric to calculate.")
            return

        self.lbl_analysis_status.setText("Calculating metrics... Please wait.")
        self.lbl_analysis_status.setStyleSheet("color: orange;")
        self.btn_run_analysis.setEnabled(False)
        
        # Show progress dialog
        self.analysis_prog = QProgressDialog("Initializing...", "Cancel", 0, 100, self)
        self.analysis_prog.setWindowTitle("Calculating Metrics")
        self.analysis_prog.setWindowModality(Qt.WindowModality.WindowModal)
        self.analysis_prog.setMinimumDuration(0)
        # We don't want them to cancel easily because it runs in C/C++ backend sometimes, but we can try
        self.analysis_prog.show()

        self.analysis_worker = AnalysisWorker(self.tgraph, accumulate, weighted, normalized, metrics_dict, analysis_options)
        self.analysis_worker.progress.connect(self._update_analysis_progress)
        self.analysis_worker.finished.connect(self._on_analysis_finished)
        self.analysis_worker.start()

    def _update_analysis_progress(self, val, msg):
        if hasattr(self, 'analysis_prog'):
            self.analysis_prog.setLabelText(msg)
            self.analysis_prog.setValue(val)

    def _on_analysis_finished(self, df_final, error_msg):
        self.btn_run_analysis.setEnabled(True)
        if hasattr(self, 'analysis_prog'):
            self.analysis_prog.close()

        if error_msg:
            self.lbl_analysis_status.setText("Analysis failed.")
            self.lbl_analysis_status.setStyleSheet("color: red;")
            QMessageBox.critical(self, "Analysis Error", str(error_msg))
            return

        # Store the resulting DataFrame
        self.df_metrics = df_final
        
        # Display it in the Table
        self.load_dataframe_to_table(self.df_metrics, self.table_analysis)
        
        # Update UI
        self.lbl_analysis_status.setText("Analysis complete.")
        self.lbl_analysis_status.setStyleSheet("color: green;")
        self.btn_export_csv.setEnabled(True)
        self.tabs.setCurrentWidget(self.tab_analysis)

    def export_analysis_csv(self):
        """Export the generated analysis DataFrame to a CSV file."""
        if not hasattr(self, 'df_metrics') or self.df_metrics is None:
            return
            
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Analysis Results", "ciga_metrics.csv", "CSV Files (*.csv)")
        if file_path:
            try:
                self.df_metrics.to_csv(file_path, index=False)
                QMessageBox.information(self, "Export Successful", f"Data saved successfully to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Failed", f"Failed to save CSV:\n{str(e)}")

    def handle_download(self, download):
        """Handles file download requests from the QWebEngineView (e.g. Export SVG)."""
        # Suggest a default file name based on what the browser wants
        default_file_name = download.downloadFileName()
        if not default_file_name:
            default_file_name = "tgraph.svg"
            
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Visualization as SVG", default_file_name, "SVG Files (*.svg);;All Files (*)"
        )
        
        if file_path:
            # Tell the download item where to write
            download.setDownloadDirectory(os.path.dirname(file_path))
            download.setDownloadFileName(os.path.basename(file_path))
            download.accept()
            # We could optionally hook to download.stateChanged to tell user when done, but for tiny SVGs it's instant.

    def generate_visualization(self):
        """Generate interactive temporal graph HTML utilizing CIGA's visualization server and load it into QWebEngineView."""
        if not hasattr(self, 'tgraph') or self.tgraph is None:
            QMessageBox.warning(self, "No TGraph", "Please build the TGraph first.")
            return

        try:
            from ciga.visualization import tgraph_viz
            import socket
            import threading
            
            # Close existing server if one is already running
            if hasattr(self, '_viz_server') and self._viz_server is not None:
                # Disconnect the web view first to avoid pending requests
                self.web_view.setUrl(QUrl("about:blank"))
                
                # Shutdown in a separate thread to avoid blocking the GUI
                def kill_server(srv):
                    try:
                        srv.shutdown()
                        srv.server_close()
                    except:
                        pass
                threading.Thread(target=kill_server, args=(self._viz_server,)).start()
                self._viz_server = None
            
            # Find an available open port
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(('localhost', 0))
            port = sock.getsockname()[1]
            sock.close()
            
            # Launch the interactive server in non-blocking background thread
            self._viz_server = tgraph_viz(self.tgraph, port=port, open_browser=False, blocking=False)
            
            url = f"http://localhost:{port}"
            self.web_view.setUrl(QUrl(url))
            
            self.tabs.setCurrentWidget(self.tab_viz)
            
        except Exception as e:
            QMessageBox.critical(self, "Error Generating Visualization", f"An error occurred:\n{str(e)}")

    def closeEvent(self, event):
        """Ensure background visualization server gets closed when exiting app"""
        if hasattr(self, '_viz_server') and self._viz_server is not None:
            # We must gracefully shut down `serve_forever()` from another thread first
            def kill_server(srv):
                try:
                    srv.shutdown()
                    srv.server_close()
                except:
                    pass
            import threading
            t = threading.Thread(target=kill_server, args=(self._viz_server,))
            t.start()
            t.join(timeout=2.0) # Ensure it attempts safe shutdown before process death
        event.accept()
