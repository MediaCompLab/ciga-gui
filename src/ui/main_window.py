from PySide6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
                               QPushButton, QLabel, QComboBox, QCheckBox,
                               QGroupBox, QTabWidget, QTableWidget, QTableWidgetItem,
                               QFileDialog, QListWidget, QAbstractItemView, QMessageBox, QApplication, QProgressDialog, QDialog, QPlainTextEdit)
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

from .workers.network_worker import NetworkWorker
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
        left_panel.setFixedWidth(280)

        self._setup_left_panel(left_layout)

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
        main_layout.addWidget(left_panel)
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

        # 2. Network Config Group
        net_group = QGroupBox("2. Network Configuration")
        net_layout = QVBoxLayout()
        self.cb_source = QComboBox()
        self.cb_target = QComboBox()
        
        # Make position a multi-select list widget to support MultiIndex
        self.list_position = QListWidget()
        self.list_position.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.list_position.setFixedHeight(60)
        self.list_position.setToolTip("Hold Ctrl/Cmd to select multiple columns for hierarchical position (MultiIndex).")
        
        # Add Weight column selection
        self.cb_weight = QComboBox()
        self.cb_weight.setToolTip("Select a column specifying edge weights, or leave as Default (Count).")
        
        # Base items
        for cb in [self.cb_source, self.cb_target, self.cb_weight]:
            cb.addItem("-- Select Column --")
            
        self.cb_weight.setItemText(0, "-- Default (Count occurrences) --")

        net_layout.addWidget(QLabel("Source (e.g. Speaker):"))
        net_layout.addWidget(self.cb_source)
        net_layout.addWidget(QLabel("Target (e.g. Listener):"))
        net_layout.addWidget(self.cb_target)
        net_layout.addWidget(QLabel("Position(s) (e.g. Scene/Time):"))
        net_layout.addWidget(self.list_position)
        
        # Add a visual separator or grouping for edge weighting
        net_layout.addWidget(QLabel("Edge Weight Column (Optional):"))
        net_layout.addWidget(self.cb_weight)
        
        self.btn_custom_weight = QPushButton("Compute Custom Weights...")
        self.btn_custom_weight.setToolTip("Define a custom Python function to compute weights based on an interaction column.")
        self.btn_custom_weight.setEnabled(False)
        net_layout.addWidget(self.btn_custom_weight)

        self.btn_build_graph = QPushButton("Build Network")
        self.btn_build_graph.setEnabled(False)
        net_layout.addWidget(self.btn_build_graph)
        net_group.setLayout(net_layout)

        # 3. Analysis Group
        analysis_group = QGroupBox("3. Calculate Metrics")
        analysis_layout = QVBoxLayout()
        
        # Network Status Label
        self.lbl_network_status = QLabel("Network not built yet.")
        self.lbl_network_status.setStyleSheet("color: blue; font-weight: bold;")
        self.lbl_network_status.setWordWrap(True)
        analysis_layout.addWidget(self.lbl_network_status)
        
        self.chk_accumulate = QCheckBox("Accumulate dynamically")
        self.chk_accumulate.setChecked(True)
        self.chk_accumulate.setToolTip("If true, calculates metrics on cumulative edges up to each time step.")

        self.chk_weighted = QCheckBox("Use Weights")
        self.chk_weighted.setChecked(True)

        self.chk_normalized = QCheckBox("Normalize metrics")
        self.chk_normalized.setChecked(True)
        
        # Metrics setup
        self.metrics_tabs = QTabWidget()
        
        # Centrality
        cent_widget = QWidget()
        cent_layout = QVBoxLayout(cent_widget)
        self.chk_degree = QCheckBox("Degree Centrality")
        self.chk_degree.setChecked(True)
        self.chk_betweenness = QCheckBox("Betweenness Centrality")
        self.chk_closeness = QCheckBox("Closeness Centrality")
        self.chk_eigenvector = QCheckBox("Eigenvector Centrality")
        for cb in [self.chk_degree, self.chk_betweenness, self.chk_closeness, self.chk_eigenvector]:
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
        analysis_layout.addWidget(metrics_box)
        analysis_layout.addWidget(self.btn_run_analysis)
        analysis_group.setLayout(analysis_layout)

        # Add groups to left panel layout
        layout.addWidget(data_group)
        layout.addWidget(net_group)
        layout.addWidget(analysis_group)
        layout.addStretch() # Push everything to the top

        # Connect button signals (mock functionality for demo)
        self.btn_load_csv.clicked.connect(self.load_file)
        self.btn_build_graph.clicked.connect(self.build_network)
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
                lower_cols = [c.lower() for c in columns]
                if 'speaker' in lower_cols:
                    self.cb_source.setCurrentIndex(lower_cols.index('speaker') + 1)
                if 'listener' in lower_cols:
                    self.cb_target.setCurrentIndex(lower_cols.index('listener') + 1)
                    
                # For position, let's try to find 'scene' or 'time'
                for i, col in enumerate(lower_cols):
                    if 'scene' in col or 'time' in col:
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

    def build_network(self):
        """Construct the TGraph using the user's column selections."""
        if not hasattr(self, 'df_raw') or self.df_raw is None:
            return
            
        source_col = self.cb_source.currentText()
        target_col = self.cb_target.currentText()
        
        selected_positions = [item.text() for item in self.list_position.selectedItems()]
        
        weight_col_text = self.cb_weight.currentText()
        weight_col = weight_col_text if not weight_col_text.startswith("-- Default") else None

        if source_col.startswith("--") or target_col.startswith("--"):
            QMessageBox.warning(self, "Missing Columns", "Please select valid Source and Target columns.")
            return
            
        if len(selected_positions) == 0:
            QMessageBox.warning(self, "Missing Position", "Please select at least one Position column (e.g. Scene/Time).")
            return

        self.btn_build_graph.setEnabled(False)
        self.lbl_network_status.setText("Building network... please wait.")
        self.lbl_network_status.setStyleSheet("color: orange;")
        
        # Show progress dialog
        self.net_prog = QProgressDialog("Building Network...", None, 0, 0, self)
        self.net_prog.setWindowTitle("Please Wait")
        self.net_prog.setWindowModality(Qt.WindowModality.WindowModal)
        self.net_prog.setMinimumDuration(0)
        self.net_prog.show()

        # Start background worker
        self.net_worker = NetworkWorker(self.df_raw, source_col, target_col, selected_positions, weight_col)
        self.net_worker.finished.connect(self._on_network_built)
        self.net_worker.start()

    def _on_network_built(self, tgraph, error_msg):
        self.btn_build_graph.setEnabled(True)
        if hasattr(self, 'net_prog'):
            self.net_prog.close()

        if error_msg:
            self.lbl_network_status.setText("Failed to build network.")
            self.lbl_network_status.setStyleSheet("color: red;")
            QMessageBox.critical(self, "Error Building TGraph", f"An error occurred while building the network:\n{error_msg}\n\nPlease ensure your columns match requirements.")
            return

        self.tgraph = tgraph
        num_time_steps = len(self.tgraph.data.index.unique())
        total_edges = len(self.tgraph.data)
        
        success_msg = f"Network built successfully!\n• {num_time_steps} Time Step(s)\n• {total_edges} Distinct Edge(s)"
        self.lbl_network_status.setText(success_msg)
        self.lbl_network_status.setStyleSheet("color: green;")
        
        self.btn_run_analysis.setEnabled(True)
        self.btn_gen_viz.setEnabled(True)
        self.tabs.setCurrentWidget(self.tab_analysis)

    def run_analysis(self):
        """Run selected metrics and merge them into a result DataFrame."""
        if not hasattr(self, 'tgraph') or self.tgraph is None:
            QMessageBox.warning(self, "No Network", "Please build the network first.")
            return

        acc = self.chk_accumulate.isChecked()
        wtd = self.chk_weighted.isChecked()
        nrm = self.chk_normalized.isChecked()
        
        metrics_dict = {
            'degree': self.chk_degree.isChecked(),
            'betweenness': self.chk_betweenness.isChecked(),
            'closeness': self.chk_closeness.isChecked(),
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

        self.analysis_worker = AnalysisWorker(self.tgraph, acc, wtd, nrm, metrics_dict)
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
            QMessageBox.warning(self, "No Network", "Please build the network first.")
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
