# hl2calibre — Calibre 标注导入插件设计文档

## 概述

hl2calibre 是一个 Calibre 外部 ZIP 插件，用于将 Moon+ Reader（静读天下）导出的 `.mrexpt` 标注文件中的高亮和批注导入到 Calibre 的标注系统中。

### 目标
- 解析 Moon+ Reader 的 `.mrexpt` 标注文件
- 通过 Calibre 已选中的书籍导入（无需自动匹配）
- 精确定位标注在 EPUB 中的位置（CFI）
- 将标注写入 Calibre 的标注数据库，可在 EPUB 查看器中显示

### 非目标
- KOReader 标注同步
- 双向同步（仅单向导入）
- 非 EPUB 格式支持

## 插件结构

```
hl2calibre.zip
├── plugin-import-name-hl2calibre.txt
├── __init__.py              # InterfaceActionBase 注册
├── action.py                # InterfaceAction: 工具栏菜单、文件对话框
├── mrexpt_parser.py         # .mrexpt 文件解析器
├── book_matcher.py          # 书籍匹配逻辑（备用，当前未使用）
├── cfi_encoder.py           # 文本位置 → EPUB CFI 转换
├── converter.py             # mrexpt 记录 → Calibre 标注格式转换
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

### 文本节点步骤

CFI 路径必须以文本节点步骤结尾，否则 `:offset` 会被误解为子节点索引：

| 内容类型 | 文本步骤 | 示例 |
|---------|---------|------|
| 元素的 `.text` | `/1` | `/2/4/2652/1:1` |
| 元素的 `.tail` | `/elem_step+1` | `/2/4/4498/4499:0` |

### 查看器的 CFI 完整结构

查看器在显示时会拼接 spine 步骤：
```
epubcfi(/{spine_step}{start_cfi})
```
其中 `spine_step = 2 * (spine_index + 1)`。

## 标注格式

### 写入 Calibre 的标注结构
```python
{
    'type': 'highlight',
    'uuid': 'mrexpt-{book_id}-{seq}-{timestamp_ms}' 的 MD5,
    'highlighted_text': '高亮原文',
    'notes': '批注内容',
    'timestamp': '当前时间 ISO8601',  # 使用当前时间，不用 mrexpt 时间
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
    'start_cfi': '/2/4[hl2calibre-xxx]/2652/1:1',
    'end_cfi': '/2/4[hl2calibre-xxx]/2652/1:4',
}
```

### 关键字段说明

| 字段 | 必须 | 说明 |
|------|------|------|
| `start_cfi` | 是 | 查看器用此定位高亮起始位置 |
| `end_cfi` | 是 | 查看器用此定位高亮结束位置，缺失会导致高亮不渲染 |
| `spine_name` | 是 | 必须与 OPF 中的 href 完全匹配，否则会被过滤 |
| `spine_index` | 是 | spine 索引（查看器用此拼接完整 CFI） |
| `style.type` | 是 | 必须为 `'builtin'`，否则 `highlight_style_as_css` 用默认颜色 |
| `user` | - | 必须为 `'viewer'`，否则查看器不显示 |

## 导入流程

### importer.py 主流程
1. 验证书名匹配（mrexpt 书名 vs Calibre 选中书籍）
2. 清理查看器本地缓存（防止旧 `removed` 条目覆盖）
3. 搜索 EPUB 中的文本，计算 CFI
4. 转换为 Calibre 标注格式
5. 调用 `db.merge_annotations_for_book()` 写入

### 性能优化
- `flat_text` 和 `node_map` 缓存：每个 spine 只构建一次
- `best_spine` 优化：记住上一次成功的 spine，优先尝试

## 用户界面

### 工具栏菜单
- 按钮："导入标注"
- 前置条件：必须先在库中选中一本书

### 文件对话框
- 标题："选择 Moon+ Reader 标注文件"
- 过滤器：`*.mrexpt`

### 结果对话框
显示成功/跳过/失败数量和详情。

## 依赖

- Calibre 内置模块（无需额外安装）
- Python 3, lxml（Calibre 自带）
- 无外部依赖
