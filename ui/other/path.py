import os
import shlex
from pathlib import Path
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QWidget
from qfluentwidgets import LineEdit, PushButton


def to_paths(text):
    try:
        ps = []
        for t in shlex.split(text.strip(), posix=(os.name != 'nt')):
            p = Path(t.strip(' "'))
            if p.exists():
                ps.append(p)
        return ps
    except Exception:
        return []


def to_one(text):
    raw = text.strip(' "')
    return raw if raw else None


class DropEdit(LineEdit):
    done = Signal(str)

    def __init__(self, replace=True, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._rep = replace
        self.textChanged.connect(self._on_change)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            super().dragEnterEvent(e)

    def dropEvent(self, e):
        # 检查空格
        urls = e.mimeData().urls()
        if urls:
            p = urls[0].toLocalFile()
            txt = f'"{p}"' if " " in p else p
            self.setText(txt)
        e.acceptProposedAction()

    def _on_change(self, text):
        self.done.emit(text)


class PathPick(QWidget):
    # 路径选择

    def __init__(self, src_input=None, parent=None):
        super().__init__(parent)
        self.src = src_input
        self.lay = QHBoxLayout(self)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.lay.setSpacing(8)

        self.edit = DropEdit(replace=True)
        self.edit.setPlaceholderText("留空则使用输入路径")

        self.btn_b = PushButton("选择位置")
        self.btn_b.clicked.connect(self._browse)
        self.btn_s = PushButton("同输入源")
        self.btn_s.clicked.connect(self._sync)

        self.lay.addWidget(self.edit)
        self.lay.addWidget(self.btn_b)
        self.lay.addWidget(self.btn_s)

    def _browse(self):
        dp = ""
        if self.src:
            ps = to_paths(self.src.text())
            if ps:
                dp = str(ps[0])
        p, _ = QFileDialog.getSaveFileName(self, "选择输出位置", dp, "所有文件 (*)")
        if p:
            self.edit.setText(p)

    def _sync(self):
        if self.src:
            ps = to_paths(self.src.text())
            if ps:
                self.edit.setText(str(ps[0].parent))

    def text(self):
        return self.edit.text()


class FilePick(QWidget):
    def __init__(self, title, filter_str="所有文件 (*.*)", is_dir=False, parent=None):
        super().__init__(parent)
        self.filter = filter_str
        self.is_dir = is_dir
        self.lay = QHBoxLayout(self)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.lay.setSpacing(8)

        self.edit = DropEdit(replace=True)
        self.btn = PushButton(title)
        self.btn.clicked.connect(self._pick)

        self.lay.addWidget(self.edit)
        self.lay.addWidget(self.btn)

    def _pick(self):
        if self.is_dir:
            path = QFileDialog.getExistingDirectory(self, self.btn.text())
        else:
            path, _ = QFileDialog.getOpenFileName(self, self.btn.text(), "", self.filter)
        if path:
            txt = f'"{path}"'
            self.edit.setText(txt)

    def text(self):
        return self.edit.text()

    def setText(self, text):
        self.edit.setText(text)
