from qt.core import (
    QDialog, QVBoxLayout, QLabel, QPushButton,
    QTextEdit, QProgressBar, QDialogButtonBox,
)


class ImportResultDialog(QDialog):
    def __init__(self, results, parent=None):
        super().__init__(parent)
        self.setWindowTitle('导入结果')
        self.setMinimumWidth(450)
        self._build_ui(results)

    def _build_ui(self, results):
        layout = QVBoxLayout(self)
        success = results.get('success', 0)
        skipped = results.get('skipped', 0)
        failed = results.get('failed', 0)
        summary = QLabel(
            f'✓ 成功导入: {success} 条标注\n'
            f'⊘ 跳过: {skipped} 条\n'
            f'✗ 失败: {failed} 条'
        )
        layout.addWidget(summary)

        details = results.get('details', [])
        errors = results.get('errors', [])
        if details or errors:
            detail_text = QTextEdit()
            detail_text.setReadOnly(True)
            lines = []
            for d in details:
                lines.append(f'《{d.get("title", "未知")}》: {d.get("count", 0)} 条')
                for w in d.get('warnings', []):
                    lines.append(f'  ⚠ {w}')
            for e in errors:
                lines.append(f'✗ {e}')
            detail_text.setPlainText('\n'.join(lines))
            layout.addWidget(detail_text)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.close)
        layout.addWidget(buttons)


class ProgressDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('正在导入...')
        self.setMinimumWidth(350)
        self.setModal(True)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        self.status_label = QLabel('准备中...')
        layout.addWidget(self.status_label)
        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)

    def update_progress(self, current, total, message):
        self.status_label.setText(message)
        if total > 0:
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(current)
