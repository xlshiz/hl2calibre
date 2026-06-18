import traceback
from qt.core import QFileDialog, QMessageBox
from calibre.gui2.actions import InterfaceAction
try:
    from . import importer
    from .ui import ImportResultDialog
except ImportError:
    import importer
    from ui import ImportResultDialog


class HL2CalibreAction(InterfaceAction):
    name = 'hl2calibre'
    action_spec = ('导入标注', 'highlight.png', '导入 Moon+ Reader 标注', None)
    action_add_menu = True
    action_type = 'current'

    def genesis(self):
        self.qaction.triggered.connect(self.import_annotations)

    def import_annotations(self):
        # Get selected book
        rows = self.gui.library_view.selectionModel().selectedRows()
        if not rows:
            QMessageBox.warning(self.gui, '提示', '请先在库中选择一本书')
            return
        if len(rows) > 1:
            QMessageBox.warning(self.gui, '提示', '请只选择一本书')
            return

        book_id = self.gui.library_view.model().id(rows[0])
        db = self.gui.current_db.new_api

        # Verify book has EPUB
        epub_path = db.format_abspath(book_id, 'EPUB')
        if not epub_path:
            QMessageBox.warning(self.gui, '提示', '选中的书没有 EPUB 格式')
            return

        # Select mrexpt file
        filepath, _ = QFileDialog.getOpenFileName(
            self.gui, '选择 Moon+ Reader 标注文件', '',
            'Moon+ Reader 标注 (*.mrexpt);;所有文件 (*)',
        )
        if not filepath:
            return

        # Import
        try:
            results = importer.import_mrexpt(db, book_id, filepath)
        except Exception as e:
            QMessageBox.critical(self.gui, '导入失败', f'{str(e)}\n\n{traceback.format_exc()}')
            return

        dialog = ImportResultDialog(results, self.gui)
        dialog.exec()
