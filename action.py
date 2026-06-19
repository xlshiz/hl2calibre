import os
import traceback
from qt.core import QFileDialog, QMessageBox, QToolButton
from calibre.gui2.actions import InterfaceAction
try:
    from . import importer
    from .ui import ImportResultDialog
except ImportError:
    import importer
    from ui import ImportResultDialog


class HL2CalibreAction(InterfaceAction):
    name = 'hl2calibre'
    action_spec = ('导入标注', 'highlight.png', '导入 Moon+ Reader / KOReader 标注', None)
    action_add_menu = True
    action_type = 'current'
    # 点击按钮任意位置直接弹出菜单，避免用户找不到下拉箭头
    popup_type = QToolButton.ToolButtonPopupMode.InstantPopup

    def genesis(self):
        # 获取自动创建的菜单并添加子菜单项
        m = self.qaction.menu()
        m.clear()

        self.create_menu_action(m, 'scan-koreader-selected', '同步选中书的 KOReader 标注',
            triggered=self.sync_selected_koreader,
            description='仅同步当前选中书籍的 KOReader 标注')
        self.create_menu_action(m, 'import-moon-reader', '导入 Moon+ Reader 标注',
            triggered=self.import_moon_reader)
        self.create_menu_action(m, 'import-koreader', '导入 KOReader 标注',
            triggered=self.import_koreader)
        m.addSeparator()
        self.create_menu_action(m, 'scan-koreader-all', '同步所有书的 KOReader 标注',
            triggered=self.sync_all_koreader,
            description='自动检测连接的设备，同步所有匹配书籍的标注')

    def _get_selected_book(self) -> tuple:
        """获取当前选中的书籍。返回 (book_id, db) 或 (None, None)。"""
        rows = self.gui.library_view.selectionModel().selectedRows()
        if not rows:
            QMessageBox.warning(self.gui, '提示', '请先在库中选择一本书')
            return None, None
        if len(rows) > 1:
            QMessageBox.warning(self.gui, '提示', '请只选择一本书')
            return None, None
        book_id = self.gui.library_view.model().id(rows[0])
        db = self.gui.current_db.new_api

        epub_path = db.format_abspath(book_id, 'EPUB')
        if not epub_path:
            QMessageBox.warning(self.gui, '提示', '选中的书没有 EPUB 格式')
            return None, None
        return book_id, db

    def import_moon_reader(self):
        book_id, db = self._get_selected_book()
        if book_id is None:
            return

        filepath, _ = QFileDialog.getOpenFileName(
            self.gui, '选择 Moon+ Reader 标注文件', '',
            'Moon+ Reader 标注 (*.mrexpt);;所有文件 (*)',
        )
        if not filepath:
            return

        try:
            results = importer.import_mrexpt(db, book_id, filepath)
        except Exception as e:
            QMessageBox.critical(self.gui, '导入失败', f'{str(e)}\n\n{traceback.format_exc()}')
            return

        dialog = ImportResultDialog(results, self.gui)
        dialog.exec()

    def import_koreader(self):
        book_id, db = self._get_selected_book()
        if book_id is None:
            return

        filepath, _ = QFileDialog.getOpenFileName(
            self.gui, '选择 KOReader 侧边文件', '',
            'KOReader 侧边文件 (metadata.epub.lua);;Lua 文件 (*.lua);;所有文件 (*)',
        )
        if not filepath:
            return

        try:
            results = importer.import_koreader(db, book_id, filepath)
        except Exception as e:
            QMessageBox.critical(self.gui, '导入失败', f'{str(e)}\n\n{traceback.format_exc()}')
            return

        dialog = ImportResultDialog(results, self.gui, source='KOReader')
        dialog.exec()

    def _get_device(self):
        """获取连接的 KOReader 设备。返回 device 或 None。"""
        try:
            device = self.gui.device_manager.connected_device
        except Exception:
            device = None
        if device is None:
            QMessageBox.warning(self.gui, '提示', '未检测到已连接的设备\n请先连接您的 KOReader 设备')
        return device

    def _import_sidecar_data(self, db, book_id, sidecar_data):
        """将侧边文件内容写入临时文件后导入。

        Returns:
            import_koreader 的结果 dict
        """
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.lua', delete=False, mode='w', encoding='utf-8') as tf:
            tf.write(sidecar_data)
            temp_path = tf.name
        try:
            return importer.import_koreader(db, book_id, temp_path)
        finally:
            os.unlink(temp_path)

    def sync_selected_koreader(self):
        """同步选中书的 KOReader 标注。"""
        book_id, db = self._get_selected_book()
        if book_id is None:
            return

        device = self._get_device()
        if device is None:
            return

        # 获取选中书籍的 UUID
        mi = db.get_metadata(book_id)
        book_uuid = mi.uuid

        # 在设备上查找对应书籍
        sidecar_path = self._find_koreader_sidecar_by_uuid(device, book_uuid)
        if sidecar_path is None:
            QMessageBox.information(self.gui, '同步结果',
                f'在设备上未找到《{mi.title}》的 KOReader 侧边文件')
            return

        # 读取侧边文件
        sidecar_data = self._read_device_file(device, sidecar_path)
        if not sidecar_data:
            QMessageBox.warning(self.gui, '同步失败', f'无法读取设备上的侧边文件:\n{sidecar_path}')
            return

        # 导入
        try:
            results = self._import_sidecar_data(db, book_id, sidecar_data)
        except Exception as e:
            QMessageBox.critical(self.gui, '同步失败', f'{str(e)}\n\n{traceback.format_exc()}')
            return

        if results.get('errors') and not results.get('success'):
            QMessageBox.warning(self.gui, '同步结果', '导入失败:\n' + '\n'.join(results['errors']))
        else:
            dialog = ImportResultDialog(results, self.gui, source='KOReader')
            dialog.exec()

    def sync_all_koreader(self):
        """扫描连接的 KOReader 设备，自动同步所有匹配书籍的标注。"""
        db = self.gui.current_db.new_api

        device = self._get_device()
        if device is None:
            return

        # 在设备上查找所有 .sdr/metadata.epub.lua 文件
        sidecar_files = self._find_koreader_sidecars(device)

        if not sidecar_files:
            QMessageBox.information(self.gui, '扫描结果', '未在设备上找到 KOReader 侧边文件')
            return

        # 逐个匹配并导入
        total_imported = 0
        total_imported_books = 0
        total_skipped = 0
        total_errors = []

        for book_uuid, sidecar_path in sidecar_files:
            try:
                book_id = db.lookup_by_uuid(book_uuid)
                if book_id is None:
                    total_skipped += 1
                    continue

                epub_path = db.format_abspath(book_id, 'EPUB')
                if not epub_path:
                    total_skipped += 1
                    continue

                # 从设备读取侧边文件内容
                sidecar_data = self._read_device_file(device, sidecar_path)
                if not sidecar_data:
                    total_skipped += 1
                    continue

                results = self._import_sidecar_data(db, book_id, sidecar_data)
                count = results.get('success', 0)
                if count > 0:
                    total_imported += count
                    total_imported_books += 1
                if results.get('errors'):
                    total_errors.extend(results['errors'])

            except Exception as e:
                total_errors.append(f'[{book_uuid}] {e}')

        msg_parts = []
        if total_imported > 0:
            msg_parts.append(f'成功导入 {total_imported} 条标注（{total_imported_books} 本书）')
        if total_skipped > 0:
            msg_parts.append(f'跳过 {total_skipped} 本（未在库中匹配或无 EPUB）')
        if total_errors:
            msg_parts.append(f'\n错误:\n' + '\n'.join(total_errors[:5]))
        if not msg_parts:
            msg_parts.append('未发现可导入的标注')

        QMessageBox.information(self.gui, '同步结果', '\n'.join(msg_parts))

    def _find_koreader_sidecar_by_uuid(self, device, book_uuid) -> str:
        """在设备上查找指定 UUID 书籍的 KOReader 侧边文件路径。"""
        import re
        try:
            for book in device.books():
                if book.uuid == book_uuid:
                    book_path = book.path
                    if not book_path:
                        return None
                    sidecar_path = re.sub(
                        r'\.([^./\\]+)$',
                        r'.sdr/metadata.\1.lua',
                        book_path
                    )
                    if sidecar_path != book_path:
                        return sidecar_path
                    return None
        except Exception:
            pass
        return None

    def _find_koreader_sidecars(self, device) -> list:
        """在设备上发现所有 KOReader 侧边文件。

        Returns:
            [(calibre_uuid, sidecar_path), ...]
        """
        import re
        sidecars = []
        try:
            for book in device.books():
                book_path = book.path
                if not book_path:
                    continue
                # 构造侧边文件路径：book.epub → book.sdr/metadata.epub.lua
                sidecar_path = re.sub(
                    r'\.([^./\\]+)$',
                    r'.sdr/metadata.\1.lua',
                    book_path
                )
                if sidecar_path == book_path:
                    continue
                sidecars.append((book.uuid, sidecar_path))
        except Exception:
            pass
        return sidecars

    def _read_device_file(self, device, path: str) -> str:
        """从设备读取文件的全部内容。

        支持 USB (os.path) 和无线 (device.get_file) 两种方式。
        """
        import io

        # 尝试本地文件系统（USB 设备）
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception:
                pass

        # 尝试 device.get_file（无线连接）
        try:
            with io.BytesIO() as buf:
                device.get_file(path, buf)
                return buf.getvalue().decode('utf-8')
        except Exception:
            return None
