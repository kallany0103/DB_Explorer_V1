def apply_main_window_styles(main_window):
    primary_color, header_color, selection_color = "#ECEFF3", "#9FA6AF", "#8E959E"
    text_color_on_primary, alternate_row_color, border_color = "#1f2937", "#F7F8FA", "#B8BEC6"
    main_window.setStyleSheet(f"""
        QSplitter::handle {{ background: #e0e0e0; border: none; }}
        QMainWindow, QToolBar {{ background-color: {primary_color}; color: {text_color_on_primary}; }}
        QStatusBar {{ background-color: #F2F4F7; color: {text_color_on_primary}; border-top: 1px solid #D1D6DD; }}
        QTreeView {{ background-color: white; alternate-background-color: {alternate_row_color}; border: 1px solid {border_color}; outline: none; }}
        QTreeView::item {{ border: none; }}
        QTreeView::item:selected, QTreeView::item:selected:active, QTreeView::item:selected:!active {{ background-color: #f0f0f0; color: black; border: none; outline: none; }}
        QTableView {{ alternate-background-color: #f7f7f7; background-color: white; gridline-color: #c8c8c8; border: 1px solid {border_color}; font-family: Arial, sans-serif; font-size: 9pt;}}
        QTableView::item {{ padding: 4px; }}
        QTableView::item:selected {{ background-color: {selection_color}; color: white; }}
        QHeaderView::section {{
            background-color: #A9A9A9;
            color: #ffffff;
            padding: 5px;
            border: none;
            border-right: 1px solid #d3d3d3;
            border-bottom: 1px solid #A9A9A9;
            font-weight: 600;
            font-size: 9pt;
        }}
        QHeaderView::section:disabled {{
            color: #ffffff;
        }}

        QTreeView QHeaderView::section {{
            background-color: #9FA6AF;
            color: #ffffff;
            font-weight: 600;
            border-bottom: 1px solid #8B929B;
        }}

        #objectExplorerLabel {{
            font-size: 10pt;
            font-weight: bold;
            color: #ffffff;
            background-color: transparent;
            border: none;
            padding: 0;
        }}

        #objectExplorerLabel:disabled {{
            color: #ffffff;
        }}

        #objectExplorerHeader {{
            background-color: #9FA6AF;
            border-bottom: 1px solid #8B929B;
        }}

        QMenuBar {{
            background-color: #F7F8FA;
            border: none;
            border-bottom: 1px solid #D3D8DF;
        }}

        QMenuBar::item {{
            background: transparent;
            padding: 4px 12px;
            margin: 0px;
        }}

        QMenuBar::item:selected {{
        background-color: #DDE2E8;
        color: #1f2937;
        }}

        QMenuBar::separator {{
        width: 0px;
        background: transparent;
        }}

        QTableView QTableCornerButton::section {{ background-color: {header_color}; border: 1px solid {border_color}; }}
        #resultsHeader QPushButton, #editorHeader QPushButton {{ background-color: #ffffff; border: 1px solid {border_color}; padding: 5px 15px; font-size: 9pt; }}
        #resultsHeader QPushButton:hover, #editorHeader QPushButton:hover {{ background-color: {primary_color}; }}
        #resultsHeader QPushButton:checked, #editorHeader QPushButton:checked {{ background-color: {selection_color}; border-bottom: 1px solid {selection_color}; font-weight: bold; color: white; }}
        #resultsHeader, #editorHeader {{ background-color: #F4F6F8; padding-bottom: -1px; border-bottom: 1px solid #D6DBE2; }}
        #tab_toolbar {{ background-color: #ECEFF3; border-top: 1px solid #D7DCE3; border-bottom: 1px solid #C9CFD8; }}
        #messageView, #history_details_view, QTextEdit, QPlainTextEdit {{ font-family: Consolas, monospace; font-size: 10pt; background-color: white; border: 1px solid {border_color}; }}
        #tab_status_label {{ padding: 3px 5px; background-color: {alternate_row_color}; border-top: 1px solid {border_color}; }}
        QGroupBox {{ font-size: 9pt; font-weight: bold; color: {text_color_on_primary}; }}
        QTabWidget::pane {{ border-top: 1px solid {border_color}; }}
        QTabBar::tab {{ background: #ECEFF3; border: 1px solid {border_color}; padding: 6px 12px; border-bottom: none; font-size: 9pt; }}
        QTabBar::tab:selected {{ background: {selection_color}; color: white; }}
        QComboBox {{ border: 1px solid {border_color}; padding: 2px; background-color: white; }}

        QLineEdit#table_search_box {{
            background-color: #ffffff;
            border: 1px solid #cccccc;
            border-radius: 14px;
            padding: 2px 10px 2px 30px;
            font-size: 9pt;
            color: #333333;
        }}
        QLineEdit#table_search_box:hover {{
            border: 1px solid #adb5bd;
        }}
        QLineEdit#table_search_box:focus {{
            border: 1px solid #8f8f8f;
            background-color: #ffffff;
        }}
    """)
