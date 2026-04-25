# 语言资源方案

本项目使用 `lang/` 目录下的 JSON 文件作为语言包。

## 文件命名

- `zh_cn.json`：简体中文（回退语言）
- `en_us.json`：英语（示例翻译）
- 未来语言：`<language>_<region>.json`（小写），例如 `ja_jp.json`

## 键名规则

- 使用点号分隔的扁平键名。
- 按模块范围添加前缀：
  - `menu.*`
  - `settings.window.*`
  - `settings.tabs.*`
  - `resource_selector.*`
  - `error.*`
  - `common.*`
- 保持键名稳定；仅在更新文案时修改值。

## 值规则

- 值支持 Python `str.format` 占位符，例如 `{count}`、`{name}`。
- 保持所有语言中占位符名称一致。

## 运行时加载

- 运行时 API：`util/i18n.py` -> `tr(key, **kwargs)`。
- 语言来源：`config/debug.cfg` 中的 `locale` 字段。
- 回退顺序：当前语言 -> `zh_cn` -> 默认字符串 -> 键名本身。

## 如何添加新文本

1. 在 `lang/zh_cn.json` 中添加键。
2. 在其他语言文件（如 `en_us.json`）中添加相同的键。
3. 将代码中的硬编码文本替换为 `tr("your.key")`。
4. 动态值使用 `tr("your.key", value=name)`。

## 当前切换方式

- 语言仅通过配置文件控制：
  - 编辑 `config/debug.cfg`
  - 设置 `"locale": "zh_cn"` 或 `"locale": "en_us"`

## 使用 Mod 新增和修正语言包

推荐使用 Mod 来为项目添加新的语言包或覆盖现有翻译。你只需在 Mod 的 `lang/` 目录下放置与主项目 `lang/` 目录结构相同的 JSON 语言文件即可。Mod 加载器会自动合并这些语言键，且 Mod 中的键值会优先于主项目的同键值，让你可以灵活地扩展或修正翻译内容。
