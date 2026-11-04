"""ui/optimize_style.py

Stylesheets and color palettes for the SQL Optimizer dialog,
multi-variant leaderboard table, KPI metrics strip, and inspection cards.
"""

OPTIMIZE_DIALOG_STYLE = """
QDialog#optimizeSqlDialog {
    background-color: #F8FAFC;
}

#optimizerHeaderFrame {
    background-color: #FFFFFF;
    border-bottom: 1px solid #E2E8F0;
    padding: 10px 16px;
}

#optimizerTitle {
    font-size: 11pt;
    font-weight: 700;
    color: #0F172A;
}

#optimizerSubtitle {
    font-size: 8.5pt;
    color: #64748B;
}

/* KPI Metrics Strip */
#kpiStripFrame {
    background-color: #FFFFFF;
    border-bottom: 1px solid #E2E8F0;
    padding: 6px 16px;
}

.kpi-title {
    font-size: 7.5pt;
    font-weight: 600;
    color: #64748B;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.kpi-val {
    font-size: 10.5pt;
    font-weight: 700;
    color: #0F172A;
}

.kpi-val-highlight {
    font-size: 10.5pt;
    font-weight: 700;
    color: #166534;
}

.kpi-val-alert {
    font-size: 10.5pt;
    font-weight: 700;
    color: #B45309;
}

/* Variant Leaderboard Table */
QTableWidget#variantTable {
    background-color: #FFFFFF;
    border: 1px solid #CBD5E1;
    border-radius: 4px;
    gridline-color: #F1F5F9;
    font-size: 8.5pt;
    color: #0F172A;
    selection-background-color: #EFF6FF;
    selection-color: #1E293B;
}

QTableWidget#variantTable::item {
    padding: 4px 6px;
    border-bottom: 1px solid #F1F5F9;
}

QTableWidget#variantTable::item:selected {
    background-color: #EFF6FF;
    color: #0F172A;
}

QHeaderView::section {
    background-color: #F1F5F9;
    color: #475569;
    font-weight: 600;
    font-size: 8pt;
    padding: 5px 6px;
    border: none;
    border-bottom: 1px solid #CBD5E1;
    border-right: 1px solid #E2E8F0;
    text-align: left;
}

/* Editors */
QTextEdit#originalSqlEditor, QTextEdit#optimizedSqlEditor, QTextEdit#selectedVariantEditor {
    background-color: #FFFFFF;
    color: #0F172A;
    border: 1px solid #CBD5E1;
    border-radius: 3px;
    font-family: "Cascadia Code", "Consolas", "Courier New", monospace;
    font-size: 9pt;
    padding: 6px;
}

QTextEdit#originalSqlEditor:focus, QTextEdit#optimizedSqlEditor:focus, QTextEdit#selectedVariantEditor:focus {
    border-color: #94A3B8;
}

/* Finding & Advisor Cards */
#findingCard {
    background-color: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 4px;
    padding: 8px 10px;
    margin-bottom: 6px;
}

#findingCard:hover {
    border-color: #CBD5E1;
}

.severity-badge {
    font-size: 7.5pt;
    font-weight: 700;
    padding: 1px 5px;
    border-radius: 3px;
    text-transform: uppercase;
}

.severity-badge[severity="HIGH"] {
    background-color: #FEE2E2;
    color: #991B1B;
}

.severity-badge[severity="MEDIUM"] {
    background-color: #FEF3C7;
    color: #92400E;
}

.severity-badge[severity="INFO"] {
    background-color: #F1F5F9;
    color: #475569;
}

#indexCodeBox {
    background-color: #F8FAFC;
    border: 1px solid #CBD5E1;
    border-radius: 3px;
    font-family: "Cascadia Code", "Consolas", "Courier New", monospace;
    font-size: 8pt;
    padding: 4px;
    color: #1E293B;
}

QTabWidget::pane {
    border: 1px solid #CBD5E1;
    border-top: none;
    background-color: #FFFFFF;
}

QTabBar::tab {
    background-color: #F1F5F9;
    color: #64748B;
    border: 1px solid #CBD5E1;
    border-top: 2px solid transparent;
    border-bottom: 1px solid #CBD5E1;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    padding: 5px 14px;
    font-size: 8.5pt;
    font-weight: 500;
    margin-right: 2px;
}

QTabBar::tab:hover:!selected {
    background-color: #E2E8F0;
    color: #1E293B;
}

QTabBar::tab:selected {
    background-color: #FFFFFF;
    color: #0F172A;
    border: 1px solid #CBD5E1;
    border-top: 2px solid #2563EB;
    border-bottom: 1px solid #FFFFFF;
    font-weight: 500;
}

/* Simulation Result Box */
#simResultBox {
    background-color: #F0FDF4;
    border: 1px solid #BBF7D0;
    border-radius: 4px;
    padding: 8px 10px;
    margin-top: 6px;
}

#simResultBox[picked="false"] {
    background-color: #F8FAFC;
    border-color: #CBD5E1;
}

.sim-status {
    font-size: 8pt;
    font-weight: 700;
    color: #166534;
}

.sim-status[picked="false"] {
    color: #64748B;
}

.sim-metric {
    font-size: 8pt;
    font-weight: 600;
    color: #0F172A;
}

.sim-detail {
    font-size: 7.5pt;
    color: #64748B;
}

/* Batch Optimizer Styles */
QDialog#batchOptimizerDialog {
    background-color: #F8FAFC;
}

.status-badge-needs-tuning {
    background-color: #FEF3C7;
    color: #92400E;
    font-size: 7.5pt;
    font-weight: 700;
    border-radius: 3px;
    padding: 2px 6px;
    text-transform: uppercase;
}

.status-badge-optimal {
    background-color: #DCFCE7;
    color: #166534;
    font-size: 7.5pt;
    font-weight: 700;
    border-radius: 3px;
    padding: 2px 6px;
    text-transform: uppercase;
}
"""
