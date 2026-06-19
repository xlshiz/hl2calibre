# hl2calibre

A Calibre plugin for importing book annotations (highlights and notes) from **Moon+ Reader** (.mrexpt) and **KOReader** (metadata.epub.lua) into Calibre's native annotation system.

---

> hl2calibre 是一个 Calibre 插件，用于将 **Moon+ Reader**（静读天下）和 **KOReader** 上的标注（高亮、批注）导入到 Calibre 的原生标注系统中，可在 Calibre EPUB 查看器中查看和管理。

---

## Features / 功能

- **Moon+ Reader** — Import `.mrexpt` files exported from Moon+ Reader
- **KOReader** — Import `metadata.epub.lua` sidecar files
- **Device Sync** — Sync annotations directly from a connected KOReader device (USB or wireless), for one book or all books at once
- **Annotation Browser** — Imported annotations appear in Calibre's built-in annotation browser
- **EPUB Viewer** — Highlights render in Calibre's EPUB viewer with correct colors and styles

---

## Installation / 安装

1. Download `hl2calibre.zip` from the [releases page](https://github.com/your/repo/releases)
2. In Calibre: **Preferences → Plugins → Load plugin from file**
3. Select the downloaded `.zip` file
4. Restart Calibre

---

## Usage / 使用

### Toolbar Button

After installation, a **导入标注** button appears on the Calibre toolbar. Clicking it shows a menu with 4 options:

| # | Menu Item | Action | 说明 |
|---|-----------|--------|------|
| 1 | **Sync KOReader annotations for selected book** | Syncs the currently selected book from a connected KOReader device | 同步当前选中书的标注 |
| 2 | **Import Moon+ Reader annotations** | Opens a file dialog to select a `.mrexpt` file | 导入 Moon+ Reader 标注文件 |
| 3 | **Import KOReader annotations** | Opens a file dialog to select a `metadata.epub.lua` file | 导入 KOReader 侧边文件 |
| — | *Separator* | | |
| 4 | **Sync all KOReader annotations** | Scans connected device and syncs all matching books | 同步所有书的标注 |

### Basic workflow

1. Select **one book** in your Calibre library (must have EPUB format)
2. Click the **导入标注** toolbar button
3. Choose the appropriate menu item
4. Follow the prompts (file selection or device detection)
5. Open the book in Calibre's EPUB viewer to see your highlights

### KOReader Sync Details

- **USB connection**: Plug in your KOReader device via USB. Calibre should detect it automatically.
- **Wireless**: Connect via KOReader's wireless connection feature, then ensure Calibre shows the device as connected.
- The plugin matches books by UUID — Calibre books and KOReader books must have matching UUIDs.

### KOReader Drawner Type Mapping / 标注类型映射

| KOReader Drawner | Calibre Style | 说明 |
|------------------|--------------|------|
| `lighten` | color (e.g. yellow, green) | 高亮背景色 |
| `underscore` | underline (wavy) | 下划线 |
| `strikeout` | line-through | 删除线 |
| `invert` | invert | 反色 |

---

## Requirements / 要求

- **Calibre 6.0+** (tested with Calibre 7.x)
- **EPUB format** books only
- Python 3 (bundled with Calibre)
- No external dependencies

---

## Development / 开发

```bash
# Run tests (from project root)
python -m pytest tests/ -v

# Build plugin
python3 -c "
import zipfile
zf = zipfile.ZipFile('hl2calibre.zip', 'w', zipfile.ZIP_DEFLATED)
for f in [
    '__init__.py', 'action.py', 'mrexpt_parser.py', 'book_matcher.py',
    'cfi_encoder.py', 'converter.py', 'importer.py', 'ui.py',
    'koreader_parser.py', 'koreader_xpath_cfi.py', 'slpp.py',
    'plugin-import-name-hl2calibre.txt'
]:
    zf.write(f, f)
zf.write('images/icon.png', 'images/icon.png')
zf.close()
"
```

---

## Credits / 致谢

This plugin builds upon the work and insights from these open-source projects:

- **[koreader-to-calibre-highlights](https://github.com/renke/koreader-to-calibre-highlights)** by renke — KOReader XPath-to-CFI conversion approach
- **[koreader-calibre-plugin](https://github.com/kyxap/koreader-calibre-plugin)** by kyxap — KOReader sidecar file parsing and device sync patterns (including the `slpp.py` Lua parser)

Thanks to the KOReader and Calibre communities for making annotation portability possible.

---

> 感谢以下开源项目为本插件提供的参考和启发：
> - **renke/koreader-to-calibre-highlights** — KOReader XPath 转 CFI 方案
> - **kyxap/koreader-calibre-plugin** — KOReader 侧边文件解析与设备同步模式（含 slpp.py Lua 解析器）

## License

MIT
