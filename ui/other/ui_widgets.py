from qfluentwidgets import ComboBox, SpinBox, DoubleSpinBox, CheckBox, LineEdit, BodyLabel


class WidgetMaker:

    @staticmethod
    def make(param, ro=False):
        t = param.w_type

        if t == "float_spin":
            w = DoubleSpinBox()
            if param.rng:
                w.setRange(float(param.rng[0]), float(param.rng[1]))
            w.setSingleStep(getattr(param, "step", 1.0))
            w.setValue(float(param.default))
            w.setReadOnly(ro)
            w.setToolTip(param.tip)
            return w, lambda: w.value()

        elif t == "int_spin":
            w = SpinBox()
            if param.rng:
                w.setRange(int(param.rng[0]), int(param.rng[1]))
            w.setValue(int(param.default))
            w.setReadOnly(ro)
            w.setToolTip(param.tip)
            return w, lambda: w.value()

        elif t == "combo":
            w = ComboBox()
            if param.opts:
                w.addItems(param.opts)
            w.setCurrentText(str(param.default))
            w.setEnabled(not ro)
            w.setToolTip(param.tip)
            return w, lambda: w.currentText()

        elif t == "check":
            w = CheckBox()
            w.setChecked(bool(param.default))
            w.setEnabled(not ro)
            w.setToolTip(param.tip)
            return w, lambda: w.isChecked()

        elif t == "text":
            w = LineEdit()
            w.setText(str(param.default))
            w.setReadOnly(ro)
            w.setToolTip(param.tip)
            return w, lambda: w.text()

        else:
            w = LineEdit()
            w.setText(str(param.default))
            return w, lambda: w.text()

    @staticmethod
    def make_row(param, ro=False):
        lb = BodyLabel(param.label)
        w, get = WidgetMaker.make(param, ro)
        return lb, w, get
