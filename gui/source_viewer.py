"""Trinh xem source MQL5: syntax highlight, so dong, find/replace, copy, save."""

from __future__ import annotations

import os
import re
import webbrowser

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QGuiApplication,
    QPainter,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from analyzer.classifier import classify
from analyzer.detector import detected_list
from analyzer.mq5_parser import analyze_source, find_matches
from models.source import SourceRecord
from utils.filename import sanitize_filename

MQL5_KEYWORDS = [
    "bool", "break", "case", "char", "class", "color", "const", "continue", "datetime",
    "default", "delete", "do", "double", "else", "enum", "extern", "false", "float", "for",
    "if", "input", "int", "long", "new", "operator", "private", "protected", "public",
    "return", "short", "sinput", "static", "string", "struct", "switch", "template", "this",
    "true", "typename", "uchar", "uint", "ulong", "ushort", "virtual", "void", "while",
]
MQL5_FUNCTIONS = [
    "OnInit", "OnDeinit", "OnTick", "OnStart", "OnCalculate", "OnTimer", "OnTrade",
    "OnTradeTransaction", "OnChartEvent", "OrderSend", "OrderSendAsync", "PositionOpen",
    "PositionSelect", "PositionsTotal", "SymbolInfoDouble", "AccountInfoDouble", "iMA",
    "iRSI", "iMACD", "iBands", "iATR", "iADX", "iStochastic", "CopyBuffer", "CopyRates",
    "Print", "Comment", "Alert", "NormalizeDouble", "ObjectCreate", "FileOpen", "WebRequest",
]


class Mql5Highlighter(QSyntaxHighlighter):
    """Highlight tu khoa, kieu, ham, chuoi, so, comment, #property/#include."""

    def __init__(self, document: QTextDocument) -> None:
        super().__init__(document)
        self.rules: list[tuple[re.Pattern[str], QTextCharFormat]] = []

        def fmt(color: str, bold: bool = False, italic: bool = False) -> QTextCharFormat:
            f = QTextCharFormat()
            f.setForeground(QColor(color))
            if bold:
                f.setFontWeight(QFont.Bold)
            f.setFontItalic(italic)
            return f

        keyword_fmt = fmt("#0000cd", bold=True)
        for word in MQL5_KEYWORDS:
            self.rules.append((re.compile(rf"\b{word}\b"), keyword_fmt))

        func_fmt = fmt("#7b1fa2")
        for word in MQL5_FUNCTIONS:
            self.rules.append((re.compile(rf"\b{word}\b"), func_fmt))

        self.rules.append((re.compile(r"#\w+"), fmt("#b8860b", bold=True)))
        self.rules.append((re.compile(r'"[^"\n]*"'), fmt("#008000")))
        self.rules.append((re.compile(r"'[^'\n]*'"), fmt("#008000")))
        self.rules.append((re.compile(r"\b\d+(\.\d+)?\b"), fmt("#c62828")))
        self.comment_fmt = fmt("#808080", italic=True)
        self.rules.append((re.compile(r"//[^\n]*"), self.comment_fmt))

        self.block_start = re.compile(r"/\*")
        self.block_end = re.compile(r"\*/")

    def highlightBlock(self, text: str) -> None:
        for pattern, char_format in self.rules:
            for match in pattern.finditer(text):
                self.setFormat(match.start(), match.end() - match.start(), char_format)

        self.setCurrentBlockState(0)
        start = 0
        if self.previousBlockState() != 1:
            match = self.block_start.search(text)
            start = match.start() if match else -1
        while start >= 0:
            end_match = self.block_end.search(text, start)
            if end_match:
                length = end_match.end() - start
                self.setCurrentBlockState(0)
            else:
                length = len(text) - start
                self.setCurrentBlockState(1)
            self.setFormat(start, length, self.comment_fmt)
            next_match = self.block_start.search(text, start + length)
            start = next_match.start() if next_match else -1


class LineNumberArea(QWidget):
    """Cot so dong ben trai editor."""

    def __init__(self, editor: CodeEditor) -> None:
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self) -> QSize:
        return QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event) -> None:
        self.editor.paint_line_numbers(event)


class CodeEditor(QPlainTextEdit):
    """QPlainTextEdit + so dong + font monospace."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setReadOnly(False)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        font = QFont("Consolas")
        font.setStyleHint(QFont.Monospace)
        font.setPointSize(10)
        self.setFont(font)
        self.line_numbers = LineNumberArea(self)
        self.blockCountChanged.connect(self._update_width)
        self.updateRequest.connect(self._update_area)
        self._update_width()
        self.highlighter = Mql5Highlighter(self.document())

    # ------------------------------------------------------------------
    def line_number_area_width(self) -> int:
        digits = max(3, len(str(max(1, self.blockCount()))))
        return 12 + self.fontMetrics().horizontalAdvance("9") * digits

    def _update_width(self) -> None:
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def _update_area(self, rect: QRect, dy: int) -> None:
        if dy:
            self.line_numbers.scroll(0, dy)
        else:
            self.line_numbers.update(0, rect.y(), self.line_numbers.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_width()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_numbers.setGeometry(QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height()))

    def paint_line_numbers(self, event) -> None:
        painter = QPainter(self.line_numbers)
        painter.fillRect(event.rect(), QColor("#f0f0f0"))
        block = self.firstVisibleBlock()
        number = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()
        painter.setPen(QColor("#808080"))
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.drawText(
                    0,
                    int(top),
                    self.line_numbers.width() - 6,
                    self.fontMetrics().height(),
                    Qt.AlignRight,
                    str(number + 1),
                )
            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            number += 1


class SourceViewer(QWidget):
    """Panel xem source: header info, editor, find/replace, analysis, cac nut hanh dong."""

    saved = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.record: SourceRecord | None = None

        self.header = QLabel("Chua chon source nao")
        self.header.setWordWrap(True)
        self.header.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.editor = CodeEditor()
        self.editor.setPlaceholderText("Source code se hien thi o day sau khi crawl/download.")

        self.find_input = QLineEdit()
        self.find_input.setPlaceholderText("Find (OnTick, CTrade, OrderSend...)")
        self.replace_input = QLineEdit()
        self.replace_input.setPlaceholderText("Replace with")
        self.case_sensitive = QCheckBox("Aa")
        self.case_sensitive.setToolTip("Phan biet chu hoa/thuong")
        self.btn_find = QPushButton("Find")
        self.btn_find_all = QPushButton("Count")
        self.btn_replace = QPushButton("Replace")
        self.btn_replace_all = QPushButton("Replace All")
        self.find_status = QLabel("")

        self.analysis = QLabel("")
        self.analysis.setWordWrap(True)

        self.btn_copy = QPushButton("COPY")
        self.btn_save = QPushButton("SAVE MQ5")
        self.btn_open = QPushButton("OPEN URL")

        self.btn_find.clicked.connect(self.find_next)
        self.btn_find_all.clicked.connect(self.count_matches)
        self.btn_replace.clicked.connect(self.replace_current)
        self.btn_replace_all.clicked.connect(self.replace_all)
        self.btn_copy.clicked.connect(self.copy_source)
        self.btn_save.clicked.connect(self.save_source)
        self.btn_open.clicked.connect(self.open_url)
        self.find_input.returnPressed.connect(self.find_next)

        self._build_layout()

    # ------------------------------------------------------------------
    def _build_layout(self) -> None:
        find_row = QHBoxLayout()
        find_row.addWidget(self.find_input, 2)
        find_row.addWidget(self.case_sensitive)
        find_row.addWidget(self.btn_find)
        find_row.addWidget(self.btn_find_all)
        find_row.addWidget(self.replace_input, 2)
        find_row.addWidget(self.btn_replace)
        find_row.addWidget(self.btn_replace_all)
        find_row.addWidget(self.find_status, 1)

        actions = QHBoxLayout()
        actions.addWidget(self.btn_copy)
        actions.addWidget(self.btn_save)
        actions.addWidget(self.btn_open)
        actions.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addWidget(self.header)
        layout.addLayout(find_row)
        layout.addWidget(self.editor, 1)
        layout.addWidget(self.analysis)
        layout.addLayout(actions)

    # ------------------------------------------------------------------
    def show_record(self, record: SourceRecord) -> None:
        """Nap record vao viewer; neu chua co source thi bao trang thai."""
        self.record = record
        code = record.source_code
        if not code and record.local_path and os.path.exists(record.local_path):
            with open(record.local_path, encoding="utf-8", errors="replace") as fh:
                code = fh.read()
                record.source_code = code
        self.header.setText(
            f"<b>{record.name}</b><br>Author: {record.author or '-'} | Type: {record.type.value}"
            f" | Status: {record.status.value}<br>URL: {record.source_url}"
            + (f"<br>File: {record.local_path}" if record.local_path else "")
            + (f"<br><span style='color:#b00'>{record.error}</span>" if record.error else "")
        )
        self.editor.setPlainText(code or "// Source chua duoc tai hoac khong public.")
        self.update_analysis()

    def update_analysis(self) -> None:
        code = self.editor.toPlainText()
        if not code or code.startswith("// Source chua"):
            self.analysis.setText("")
            return
        stats = analyze_source(code)
        features = detected_list(code)
        strategies = [s.value for s in classify(code)]
        self.analysis.setText(
            f"<b>Analysis:</b> Lines: {stats.lines} | Functions: {stats.functions} | "
            f"Inputs: {stats.inputs} | Includes: {stats.includes} | Classes: {stats.classes}<br>"
            f"<b>Detected:</b> {', '.join(features) or '-'}<br>"
            f"<b>Strategy:</b> {', '.join(strategies)}"
        )

    # ------------------------------------------------------------------
    def find_next(self) -> bool:
        needle = self.find_input.text()
        if not needle:
            return False
        flags = QTextDocument.FindFlags()
        if self.case_sensitive.isChecked():
            flags |= QTextDocument.FindCaseSensitively
        found = self.editor.find(needle, flags)
        if not found:
            cursor = self.editor.textCursor()
            cursor.movePosition(QTextCursor.Start)
            self.editor.setTextCursor(cursor)
            found = self.editor.find(needle, flags)
        self.find_status.setText("Found" if found else "Not found")
        return found

    def count_matches(self) -> int:
        needle = self.find_input.text()
        matches = find_matches(
            self.editor.toPlainText(), needle, self.case_sensitive.isChecked()
        )
        self.find_status.setText(f"Found {len(matches)} lines")
        return len(matches)

    def replace_current(self) -> None:
        if not self.find_next():
            return
        cursor = self.editor.textCursor()
        if cursor.hasSelection():
            cursor.insertText(self.replace_input.text())
        self.update_analysis()

    def replace_all(self) -> None:
        needle = self.find_input.text()
        if not needle:
            return
        text = self.editor.toPlainText()
        if self.case_sensitive.isChecked():
            new_text, count = text.replace(needle, self.replace_input.text()), text.count(needle)
        else:
            pattern = re.compile(re.escape(needle), re.IGNORECASE)
            new_text, count = pattern.subn(self.replace_input.text(), text)
        self.editor.setPlainText(new_text)
        self.find_status.setText(f"Replaced {count}")
        self.update_analysis()

    # ------------------------------------------------------------------
    def copy_source(self) -> None:
        QGuiApplication.clipboard().setText(self.editor.toPlainText())
        self.find_status.setText("Copied")

    def save_source(self) -> str:
        code = self.editor.toPlainText()
        if not code.strip():
            QMessageBox.information(self, "Save MQ5", "Khong co source de luu.")
            return ""
        default_name = sanitize_filename(
            self.record.filename if self.record and self.record.filename else "source.mq5"
        )
        path, _ = QFileDialog.getSaveFileName(
            self, "Save MQ5", os.path.join("downloads", default_name), "MQL5 (*.mq5 *.mqh *.mq4)"
        )
        if not path:
            return ""
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(code)
        self.find_status.setText(f"Saved: {os.path.basename(path)}")
        self.saved.emit(path)
        return path

    def open_url(self) -> None:
        if self.record and self.record.source_url:
            webbrowser.open(self.record.source_url)
