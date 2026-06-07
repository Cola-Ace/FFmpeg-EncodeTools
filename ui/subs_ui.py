from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QVBoxLayout
from qfluentwidgets import (
    BodyLabel, CardWidget, RadioButton, SpinBox, SubtitleLabel,
)

from ui.main_ui import BasePage
from ui.other.path import DropEdit, PathPick, to_paths, to_one


class SubsPage(BasePage):

    def __init__(self):
        super().__init__("字幕清洗", "tab_clean")
        c = CardWidget()
        l = QVBoxLayout(c)
        l.addWidget(SubtitleLabel("字幕清洗"))
        g = QGridLayout()
        self.sub_in = DropEdit()
        self.sub_in.done.connect(self._auto_out)
        self.out_pick = PathPick(self.sub_in)
        self.rb_wash = RadioButton("仅清洗")
        self.rb_wash.setChecked(True)
        self.rb_split = RadioButton("清洗并等分")
        self.sp_n = SpinBox()
        self.sp_n.setRange(2, 99)
        self.sp_n.setEnabled(False)
        self.rb_split.toggled.connect(self.sp_n.setEnabled)
        mr = QHBoxLayout()
        mr.addWidget(self.rb_wash)
        mr.addWidget(self.rb_split)
        mr.addWidget(BodyLabel("等分份数"))
        mr.addWidget(self.sp_n)
        mr.addStretch()
        g.addWidget(BodyLabel("字幕文件"), 0, 0)
        g.addWidget(self.sub_in, 0, 1)
        g.addWidget(BodyLabel("输出位置"), 1, 0)
        g.addWidget(self.out_pick, 1, 1)
        g.addWidget(BodyLabel("处理模式"), 2, 0)
        g.addLayout(mr, 2, 1)
        l.addLayout(g)
        self.cards.addWidget(c)

    def _auto_out(self, text):
        ps = to_paths(text)
        if ps and not self.out_pick.edit.text().strip():
            self.out_pick.edit.setText(str(ps[0].with_name(f"{ps[0].stem}.txt")))

    def get_job(self):
        subs = to_paths(self.sub_in.text())
        if not subs:
            return None, "请选择字幕文件。"
        return "clean", {
            "vid_list": subs,
            "mode": "split" if self.rb_split.isChecked() else "clean",
            "split_n": self.sp_n.value() if self.rb_split.isChecked() else None,
            "out_dir": to_one(self.out_pick.text()),
        }
