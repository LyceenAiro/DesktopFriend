# Language Resource Scheme

This project uses JSON language bundles under the root `lang/` directory.

## File Naming

- `zh_cn.json`: Simplified Chinese (fallback)
- `en_us.json`: English (example translation)
- Future locales: `<language>_<region>.json` (lowercase), e.g. `ja_jp.json`

## Key Rules

- Use flat dot-separated keys.
- Prefix by module scope:
  - `menu.*`
  - `settings.window.*`
  - `settings.tabs.*`
  - `resource_selector.*`
  - `error.*`
  - `common.*`
- Keep keys stable; only change values when updating copy.

## Value Rules

- Values support Python `str.format` placeholders, e.g. `{count}`, `{name}`.
- Keep placeholder names identical across locales.

## Runtime Loading

- Runtime API: `util/i18n.py` -> `tr(key, **kwargs)`.
- Locale source: `config/debug.cfg` field `locale`.
- Fallback order: active locale -> `zh_cn` -> default string -> key itself.

## How To Add New Text

1. Add a key to `lang/zh_cn.json`.
2. Add the same key to other locale files (e.g. `en_us.json`).
3. Replace hardcoded UI text with `tr("your.key")`.
4. For dynamic values use `tr("your.key", value=name)`.

## Current Switch Method

- Language is controlled only by config file:
  - Edit `config/debug.cfg`
  - Set `"locale": "zh_cn"` or `"locale": "en_us"`
