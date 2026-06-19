# hl2calibre — Calibre 标注导入插件设计文档

## 概述

hl2calibre 是一个 Calibre 外部 ZIP 插件，用于将 Moon+ Reader（静读天下）导出的 `.mrexpt` 标注文件中的高亮和批注导入到 Calibre 的标注系统中。

### 目标
- 解析 Moon+ Reader 的 `.mrexpt` 标注文件
- 解析 KOReader 的 `metadata.epub.lua` 侧边文件
- 通过 Calibre 已选中的书籍导入（无需自动匹配）
- 精确定位标注在 EPUB 中的位置（CFI）
- 将标注写入 Calibre 的标注数据库，可在 EPUB 查看器中显示
- 支持设备扫描自动同步 KOReader 标注

### 非目标
- 双向同步（仅单向导入）
- 非 EPUB 格式支持

## 插件结构

```
hl2calibre.zip
├── plugin-import-name-hl2calibre.txt
├── __init__.py              # InterfaceActionBase 注册
├── action.py                # InterfaceAction: 工具栏菜单、文件对话框
├── mrexpt_parser.py         # .mrexpt 文件解析器
├── koreader_parser.py       # KOReader sidecar Lua 解析器
├── koreader_xpath_cfi.py    # KOReader XPath → Calibre CFI 转换
├── slpp.py                  # Lua 解析器（SLPP）
├── book_matcher.py          # 书籍匹配逻辑（备用，当前未使用）
├── cfi_encoder.py           # 文本位置 → EPUB CFI 转换
├── converter.py             # 标注记录 → Calibre 标注格式转换
├── importer.py              # 导入编排（协调各模块）
├── ui.py                    # 导入结果对话框
└── images/
    └── icon.png             # 插件图标
```

## 核心流程

```
用户点击"导入标注" → 选择 .mrexpt 文件 → 导入当前选中的书籍
                                              ↓
                              mrexpt_parser 解析记录
                                              ↓
                              cfi_encoder 在 EPUB 中搜索文本
                              → 生成 CFI 路径（含 id 断言）
                                              ↓
                              converter 转换为 Calibre 标注格式
                                              ↓
                              db.merge_annotations_for_book() 写入
                                              ↓
                              用户在 EPUB 查看器中看到高亮
```

## Moon+ Reader .mrexpt 格式

### 文件结构
纯文本，UTF-8 编码。前 3 行为文件头，后续为 `#` 分隔的记录，每条记录 16 行。

### 记录字段（16 行/条）

| 索引 | 说明 | 示例 |
|------|------|------|
| 0 | 序号（递增） | `26` |
| 1 | 书名 | `数学女孩3：哥德尔不完备定理` |
| 2 | 文件路径（原始） | `/sdcard/Books/xxx.epub` |
| 3 | 文件路径（小写） | `/sdcard/books/xxx.epub` |
| 4 | 章节号（非 spine 索引） | `52` |
| 5 | 未知（通常为 0） | `0` |
| 6 | 章节内字符偏移 | `483` |
| 7 | 高亮文本长度 | `26` |
| 8 | 颜色编码（有符号32位补码） | `-28160` |
| 9 | 时间戳（毫秒） | `1671754358620` |
| 10 | 未知标志 | |
| 11 | 批注/笔记（可空） | |
| 12 | 高亮原文 | `集合的外延表示法中...` |
| 13-15 | 未知标志 | |

### 颜色解码
```python
hex((0xFFFFFFFF + code + 1) & 0xFFFFFFFF)[2:].zfill(8)[2:]
# 例: -28160 → FF9200 (orange)
```

### 特殊处理
- `<BR>` → `\n`
- `\uFFFC` → 移除

## CFI 编码

### CFI 格式
查看器存储的 CFI 格式（`start_cfi` / `end_cfi` 字段）：
```
/2/4[body_id]/element_step/text_step:char_offset
│  │   │         │           │          └── 文本节点内字符偏移
│  │   │         │           └── 文本节点步骤（text=1, tail=elem_step+1）
│  │   │         └── 元素在兄弟中的 CFI 步骤
│  │   └── body 元素的 id 断言（关键！）
│  └── body 步骤（通常为 4）
└── html 步骤（通常为 2）
```

### 编码流程

1. **构建文本映射**：遍历 HTML DOM，记录每个文本节点的位置
2. **搜索高亮文本**：在拼接的纯文本中查找
3. **定位文本节点**：找到包含目标位置的元素和偏移
4. **计算 CFI 路径**：从目标元素向上遍历到根，计算每级的 CFI 步骤
5. **添加文本节点步骤**：`/1`（text）或 `/elem_step+1`（tail）
6. **添加 id 断言**：如果元素有 `id` 属性，添加 `[id]`

### id 断言（关键机制）

查看器的 CFI 解码器在处理路径步骤时，如果遇到 `[id]` 断言：
```javascript
// cfi.pyj: node_for_path_step()
if assertion:
    q = document.getElementById(assertion)
    if q and id_is_unique(assertion):
        return q  // 直接返回，跳过步骤导航！
```

**这意味着**：只要 CFI 包含正确的 id 断言，解码器就能准确定位元素，完全不依赖步骤值的准确性。这是让标注在查看器中正确显示的关键。

## KOReader 标注导入

### KOReader 侧边文件格式

KOReader 为每本 EPUB 电子书维护一个侧边 Lua 文件：
  `<书名>.sdr/metadata.epub.lua`

该文件为 Lua table 格式，标注存储位置因版本而异：

**旧格式**（两个独立 dict）：
- `highlight` dict：纯高亮（按页码为整数 key 分组，值为 1-indexed 列表）
- `bookmarks` dict：书签（含高亮和纯书签）

**新格式**（统一 annotations dict，更常见）：
- `annotations` dict：整数 key，每个值包含标注信息
  - `drawer`/`color`：渲染样式（有 pos0/pos1 的为高亮）
  - `page` 字段：纯书签只有此 XPath 字段，无 pos0/pos1

解析优先级：annotations > highlight > bookmarks

### XPath 位置格式

KOReader 使用 XPath 格式定位文本：
```
/body/DocFragment[N]/body/div/p[12]/text()[M].offset
```

| 部分 | 说明 | 示例 |
|------|------|------|
| `DocFragment[N]` | Spine 索引（1-based） | `DocFragment[7]` → spine_index=6 |
| `/body/div/p[12]` | Spine HTML 内的 XPath | `p[12]` → 第 12 个 p 元素 |
| `text()[M]` | 第 M 个文本节点（1-based） | `text()[1]` = 元素.text, `text()[2]` = 第一个子元素的 tail |
| `.offset` | 文本节点内的字符偏移 | `.0` = 开头 |

### 解析流程

```
用户点击

CFI 路径必须以文本节点步骤结尾，否则 `:offset` 会被误解为子节点索引：

| 内容类型 | 文本步骤 | 示例 |
|---------|---------|------|
| 元素的 `.text` | `/1` | `/2/4/2652/1:1` |
| 元素的 `.tail` | `/elem_step+1` | `/2/4/4498/4499:0` |

### 查看器的 CFI 完整结构

## KOReader 导入流程

### 手动导入
```
用户选择一本书 → 选择 metadata.epub.lua 侧边文件
                                              ↓
                   koreader_parser 解析 Lua 文件
                                              ↓
                   提取 annotation（highlight + bookmarks）
                                              ↓
                   koreader_xpath_cfi 解析 XPath
                   → 在 EPUB spine HTML 中用 lxml XPath 定位元素
                   → 使用 _encode_cfi_path 转为 CFI 路径
                                              ↓
                   converter.convert_koreader_record 转换格式
                                              ↓
                   db.merge_annotations_for_book() 写入
                                              ↓
                   用户在 EPUB 查看器中看到高亮
```

## 标注格式

### 写入 Calibre 的标注结构
```python
{
    'type': 'highlight',
    'uuid': 'koreader-{book_id}-{idx}-{pos0}-{text[:50]}' 的 MD5,
    'highlighted_text': '高亮原文',
    'notes': '批注内容',
    'timestamp': '当前时间 ISO8601',  # 使用当前时间，不用 KOReader 原始时间
    'spine_index': 1,
    'spine_name': 'Text/part0000.xhtml',  # OPF 中的 href
    'toc_family_titles': ('Chapter 52',),
    'style': {
        'type': 'builtin',  # 必须！否则显示为黑色
        'kind': 'color',
        'which': 'orange',
        'light': 'FF9200',
        'dark': '7F4900',
    },
    'pos_type': 'epubcfi',
    'start_cfi': '/2/4[4OIQ0-b54a43f3eed14b80982501ccd34fe5ef]/2/6/1:0',
    'end_cfi': '/2/4[4OIQ0-b54a43f3eed14b80982501ccd34fe5ef]/2/6/1:138',
}
```

### 时间戳策略（重要）

`timestamp` 使用**导入时的当前时间**而非 KOReader 侧边文件中的原始标注时间。

原因：Calibre 的 `merge_annotations_for_book()` 按 uuid 分组后保留**时间戳最新的那条**。如果用 KOReader 原始时间：
1. 导入写入（时间戳 = 3 天前）
2. 用户删除标注 → 标记为 `removed: true`（时间戳 = 现在）
3. 再次导入 → merge 保留时间戳更新的 `removed` 版本 → 标注丢失！

使用当前时间导入后，重新导入总能产生最新时间戳，merge 时胜出。

### 关键字段说明

| 字段 | 必须 | 说明 |
|------|------|------|
| `start_cfi` | 是 | 查看器用此定位高亮起始位置 |
| `end_cfi` | 是 | 查看器用此定位高亮结束位置，缺失会导致高亮不渲染 |
| `spine_name` | 是 | 必须与 OPF 中的 href 完全匹配，否则会被过滤 |
| `spine_index` | 是 | spine 索引（查看器用此拼接完整 CFI） |
| `style.type` | 是 | 必须为 `'builtin'`，否则 `highlight_style_as_css` 用默认颜色 |
| `user` | - | 必须为 `'viewer'`，否则查看器不显示 |
| `uuid` | 是 | 确定性 MD5，确保重复导入时 merge 匹配 |

## 设备同步

两种同步方式共享以下流程：

**同步选中书：**
```
用户选中一本书 → 菜单第 1 项
                    ↓
        获取选中的 Calibre 书籍 + 连接的设备
                    ↓
        用书籍 UUID 在设备上匹配 → 构造侧边文件路径
                    ↓
        读取侧边文件 → 写入临时文件 → import_koreader()
                    ↓
        弹出详细结果对话框
```

**同步所有书：**
```
用户点击菜单第 4 项
                    ↓
        获取连接的设备
                    ↓
        遍历设备上所有书籍，构造侧边文件路径
                    ↓
        逐个按 UUID 匹配 Calibre 库中的书籍
                    ↓
        读取侧边文件 → 写入临时文件 → import_koreader()
                    ↓
        弹出汇总信息（成功 x 条 / 跳过 y 本）
```

## 用户界面

### 工具栏菜单（4 项）
```
┌─ 同步选中书的 KOReader 标注 ──┐  ← 常用操作放最前面
│ 导入 Moon+ Reader 标注         │
│ 导入 KOReader 标注             │
│────────────────────────────────│
│ 同步所有书的 KOReader 标注     │  ← 批量操作放最后，有分隔线
└────────────────────────────────┘
```

### 菜单顺序（3124）

| 位置 | 菜单项 | 说明 |
|------|--------|------|
| 1 | 同步选中书的 KOReader 标注 | 常用操作，优先放置 |
| 2 | 导入 Moon+ Reader 标注 | 选择 .mrexpt 文件 |
| 3 | 导入 KOReader 标注 | 选择 metadata.epub.lua 文件 |
| — | 分隔线 | — |
| 4 | 同步所有书的 KOReader 标注 | 批量操作，放最后 |

### 两种 KOReader 同步的区别

| 功能 | 选中书同步 | 全量同步 |
|------|-----------|---------|
| 触发 | 菜单第 1 项 | 菜单第 4 项 |
| 范围 | 当前选中的一本书 | 设备上所有匹配书籍 |
| 匹配方式 | UUID 精确匹配 | UUID 精确匹配 |
| 结果展示 | 导入结果对话框 | 汇总信息对话框 |
| 适用场景 | 日常阅读完后快速同步 | 首次同步或批量整理 |

### 前置条件
- 必须先在库中选中一本书
- 必须连接 KOReader 设备（USB 或无线）

## 导入流程

### KOReader 导入
1. 解析侧边 Lua 文件为 `KoreaderAnnotation` 列表
2. 从 EPUB 读取 OPF，构建 spine 名称列表
3. 为每条标注：解析 XPath → 加载对应 spine HTML → 用 lxml 定位元素 → 转为 CFI
4. 转换为 Calibre 标注格式
5. 调用 `db.merge_annotations_for_book()` 写入
6. 重建 FTS 索引（`reindex_annotations()`）

### Moon+ Reader 导入
1. 验证书名匹配（mrexpt 书名 vs Calibre 选中书籍）
2. 清理查看器本地缓存
3. 遍历 spine 项搜索高亮文本
4. 计算 CFI 路径（含 id 断言）
5. 转换为 Calibre 标注格式
6. 调用 `db.merge_annotations_for_book()` 写入

### 性能优化
- `flat_text` 和 `node_map` 缓存：每个 spine 只构建一次
- `best_spine` 优化：记住上一次成功的 spine，优先尝试
- `XPathResolver`: lazy-loading spine HTML，按需加载

## 依赖

- Calibre 内置模块（无需额外安装）
- Python 3, lxml（Calibre 自带）
- 无外部依赖
