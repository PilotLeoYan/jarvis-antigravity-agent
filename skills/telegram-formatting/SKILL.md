---
name: telegram-formatting
description: Verified mobile and Telegram formatting standards for optimal visual hierarchy and rendering.
---

# Telegram Formatting Standards

Empirically verified formatting rules to ensure optimal legibilidad on Telegram mobile and desktop clients:

## Supported Formatting Elements
- **Bold**: `**text**` (or `*text*` depending on markdown mode).
- *Italic*: `_text_` (or `*text*`).
- Bullet and numbered lists (`•`, `-`, `1.`).
- Blockquotes: `> quotation`.
- Markdown Links: `[label](url)`.
- Spoilers: `||hidden text||`.
- Code: Inline code (`code`) and multi-line fenced code blocks (```python ... ```).
- Emojis and horizontal separators (`---`).

## Critical Restrictions
- **NEVER combine bold and italic**: `***text***` causes Telegram markdown parsing failures.
- **DO NOT use Markdown `#` Headings**: Telegram does not render `#`, `##`, or `###` headings and displays literal `#` characters. Instead, use emojis combined with bold text (`📌 **Title**`, `⚙️ **Section**`).
- **NO LaTeX Formulas**: Render equations using unicode symbols or code blocks.
- **NO Markdown Tables**: Tables break on narrow mobile screens. Use structured lists instead.
- **Rich Emoji Usage**: Use descriptive emojis (`💡`, `🚀`, `⚙️`, `✅`, `📌`, `⚠️`, `📊`, `🧠`) functionally to denote states, highlight critical takeaways, and provide clean visual hierarchy.
- **High Information Density**: Eliminate conversational fluff and boilerplate pleasantries.
