#!/usr/bin/env python3
"""
Tag checklist generator for NMRK project.
Scans all HTML files and produces tag-checklist.md with exact line numbers.
"""

import re
import os
from pathlib import Path
from html.parser import HTMLParser

RULES = Path(__file__).parent / "rules.md"
OUTPUT = Path(__file__).parent / "tag-checklist.md"
HTML_FILES = sorted(Path(__file__).parent.glob("*.html"))


class TagExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
        self._line = 0
        self._pos_stack = []

    def feed(self, data):
        self._line = 1
        for i, ch in enumerate(data):
            if ch == "\n":
                self._line += 1
        super().feed(data)

    def setpos(self):
        line, col = self.getpos()
        return line

    def handle_starttag(self, tag, attrs):
        line = self.getpos()[0]
        self.tags.append((tag, line, dict(attrs)))

    def handle_endtag(self, tag):
        line = self.getpos()[0]
        self.tags.append((tag + "_end", line, {}))

    def handle_comment(self, data):
        line = self.getpos()[0]
        self.tags.append(("comment", line, {"text": data.strip()}))

    def handle_data(self, data):
        pass

    def handle_entityref(self, name):
        line = self.getpos()[0]
        self.tags.append(("entity", line, {"name": name}))

    def handle_charref(self, name):
        line = self.getpos()[0]
        self.tags.append(("charref", line, {"name": name}))


def extract_author(filepath):
    """Extract author name from meta tag."""
    text = filepath.read_text(encoding="utf-8")
    m = re.search(r'<meta\s+name=["\']author["\']\s+content=["\']([^"\']+)["\']', text, re.IGNORECASE)
    if m:
        return m.group(1)
    m = re.search(r'<meta\s+content=["\']([^"\']+)["\']\s+name=["\']author["\']', text, re.IGNORECASE)
    if m:
        return m.group(1)
    return None


def extract_all(filepath):
    """Extract all tags, comments, entities from an HTML file."""
    text = filepath.read_text(encoding="utf-8")
    parser = TagExtractor()
    parser.feed(text)
    return parser.tags


def find_entities(filepath):
    """Find HTML entities using regex for more reliable detection."""
    text = filepath.read_text(encoding="utf-8")
    entities = []
    for m in re.finditer(r'&(#\d+|#x[0-9a-fA-F]+|[a-zA-Z]+);', text):
        line = text[:m.start()].count("\n") + 1
        entities.append(("entity", line, {"text": m.group(0)}))
    return entities


def find_comments(filepath):
    """Find HTML comments."""
    text = filepath.read_text(encoding="utf-8")
    comments = []
    for m in re.finditer(r'<!--(.*?)-->', text, re.DOTALL):
        line = text[:m.start()].count("\n") + 1
        comments.append(("comment", line, {"text": m.group(1).strip()}))
    return comments


def classify_tags(tags):
    """Classify tags into required categories."""
    result = {
        "structural": [],      # header, nav, main, footer, section, article, aside
        "tables": [],          # table, caption, thead, tbody, tfoot, tr, th, td
        "lists": [],           # ul, ol, li, dl, dt, dd
        "forms": [],           # form, fieldset, legend, label, input, select, option, textarea, button
        "media": [],           # figure, figcaption, img
        "text_format": [],     # strong, em, b, i, mark, small, sub, sup, abbr
        "block_text": [],      # blockquote, q, cite, p, pre, code, kbd, samp
        "links": [],           # a (with mailto/tel/external detection)
        "headings": [],        # h1-h6
        "meta": [],            # doctype, html, meta, title, head, body
        "semantic": [],        # section, article, aside used as content containers
        "breaks": [],          # hr, br
        "containers": [],      # div, span
        "entities": [],        # HTML entities
        "comments": [],        # HTML comments
    }

    for tag, line, attrs in tags:
        t = tag.split("_end")[0].replace("_end", "")
        is_end = tag.endswith("_end")

        if is_end:
            continue

        if tag == "comment":
            result["comments"].append((line, attrs.get("text", "")))
            continue

        if tag in ("entity", "charref"):
            result["entities"].append((line, attrs.get("text", attrs.get("name", ""))))
            continue

        # Headings
        if t in ("h1", "h2", "h3", "h4", "h5", "h6"):
            result["headings"].append((t, line))
            continue

        # Structural
        if t in ("header", "nav", "main", "footer", "section", "article", "aside"):
            result["structural"].append((t, line))
            continue

        # Tables
        if t in ("table", "caption", "thead", "tbody", "tfoot", "tr", "th", "td"):
            result["tables"].append((t, line, attrs))
            continue

        # Lists
        if t in ("ul", "ol", "li", "dl", "dt", "dd"):
            result["lists"].append((t, line, attrs))
            continue

        # Forms
        if t in ("form", "fieldset", "legend", "label", "input", "select", "option", "textarea", "button"):
            result["forms"].append((t, line, attrs))
            continue

        # Media
        if t in ("figure", "figcaption", "img"):
            result["media"].append((t, line, attrs))
            continue

        # Text formatting
        if t in ("strong", "em", "b", "i", "mark", "small", "sub", "sup", "abbr"):
            result["text_format"].append((t, line, attrs))
            continue

        # Block text
        if t in ("blockquote", "q", "cite", "p", "pre", "code", "kbd", "samp"):
            result["block_text"].append((t, line, attrs))
            continue

        # Links
        if t == "a":
            href = attrs.get("href", "")
            kind = "internal"
            if href.startswith("mailto:"):
                kind = "mailto"
            elif href.startswith("tel:"):
                kind = "tel"
            elif href.startswith("http"):
                kind = "external"
            elif href.startswith("#"):
                kind = "same-page"
            result["links"].append((t, line, href, kind))
            continue

        # Breaks
        if t in ("hr", "br"):
            result["breaks"].append((t, line))
            continue

        # Containers
        if t in ("div", "span"):
            result["containers"].append((t, line, attrs))
            continue

        # Meta
        if t in ("doctype", "html", "meta", "title", "head", "body", "link"):
            result["meta"].append((t, line, attrs))
            continue

    return result


def generate_checklist(all_data):
    """Generate markdown checklist from classified data."""
    lines = []
    lines.append("# Tag Checklist — NMRK Project")
    lines.append("")
    lines.append("Generated automatically by `generate_checklist.py`")
    lines.append("")

    # Authors summary
    authors_map = {}
    for filename, (author, _) in all_data.items():
        if author:
            authors_map.setdefault(author, []).append(filename)
    if authors_map:
        lines.append("## Authors")
        lines.append("| Author | Files |")
        lines.append("|---|---|")
        for author, files in sorted(authors_map.items()):
            lines.append(f"| **{author}** | {', '.join(files)} |")
        lines.append("")
        lines.append("---")
        lines.append("")

    for filename, (author, data) in all_data.items():
        if author:
            lines.append(f"## {filename} `@{author}`")
        else:
            lines.append(f"## {filename}")
        lines.append("")

        # Structural
        lines.append("### Structural")
        lines.append("| Tag | Line |")
        lines.append("|---|---:|")
        for t, line in data["structural"]:
            lines.append(f"| `<{t}>` | {line} |")
        lines.append("")

        # Headings
        lines.append("### Headings")
        lines.append("| Tag | Line |")
        lines.append("|---|---:|")
        for t, line in data["headings"]:
            lines.append(f"| `<{t}>` | {line} |")
        lines.append("")

        # Tables
        if data["tables"]:
            lines.append("### Tables")
            lines.append("| Tag | Line | Notes |")
            lines.append("|---|---:|---|")
            for item in data["tables"]:
                t, line, attrs = item
                notes = ""
                if "scope" in attrs:
                    notes = f'scope="{attrs["scope"]}"'
                elif "class" in attrs:
                    notes = f'class="{attrs["class"]}"'
                lines.append(f"| `<{t}>` | {line} | {notes} |")
            lines.append("")

        # Lists
        if data["lists"]:
            lines.append("### Lists")
            lines.append("| Tag | Line | Notes |")
            lines.append("|---|---:|---|")
            for item in data["lists"]:
                t, line, attrs = item
                notes = ""
                if "start" in attrs:
                    notes = f'start="{attrs["start"]}"'
                elif "type" in attrs:
                    notes = f'type="{attrs["type"]}"'
                lines.append(f"| `<{t}>` | {line} | {notes} |")
            lines.append("")

        # Forms
        if data["forms"]:
            lines.append("### Forms")
            lines.append("| Tag | Line | Notes |")
            lines.append("|---|---:|---|")
            for item in data["forms"]:
                t, line, attrs = item
                notes = []
                if "type" in attrs:
                    notes.append(f'type="{attrs["type"]}"')
                if "name" in attrs:
                    notes.append(f'name="{attrs["name"]}"')
                if "for" in attrs:
                    notes.append(f'for="{attrs["for"]}"')
                if "id" in attrs:
                    notes.append(f'id="{attrs["id"]}"')
                if "method" in attrs:
                    notes.append(f'method="{attrs["method"]}"')
                if "action" in attrs:
                    notes.append(f'action="{attrs["action"]}"')
                if "required" in attrs:
                    notes.append("required")
                if "placeholder" in attrs:
                    notes.append(f'placeholder="{attrs["placeholder"]}"')
                if "value" in attrs:
                    notes.append(f'value="{attrs["value"]}"')
                if "checked" in attrs:
                    notes.append("checked")
                if "selected" in attrs:
                    notes.append("selected")
                lines.append(f"| `<{t}>` | {line} | {', '.join(notes)} |")
            lines.append("")

        # Media
        if data["media"]:
            lines.append("### Media")
            lines.append("| Tag | Line | Notes |")
            lines.append("|---|---:|---|")
            for item in data["media"]:
                t, line, attrs = item
                notes = ""
                if "src" in attrs:
                    notes = attrs["src"]
                lines.append(f"| `<{t}>` | {line} | {notes} |")
            lines.append("")

        # Text formatting
        if data["text_format"]:
            lines.append("### Text Formatting")
            lines.append("| Tag | Line | Notes |")
            lines.append("|---|---:|---|")
            for item in data["text_format"]:
                t, line, attrs = item
                notes = ""
                if "title" in attrs:
                    notes = f'title="{attrs["title"]}"'
                lines.append(f"| `<{t}>` | {line} | {notes} |")
            lines.append("")

        # Block text
        if data["block_text"]:
            lines.append("### Block Text")
            lines.append("| Tag | Line |")
            lines.append("|---|---:|")
            for t, line, _ in data["block_text"]:
                lines.append(f"| `<{t}>` | {line} |")
            lines.append("")

        # Links
        if data["links"]:
            lines.append("### Links")
            lines.append("| Type | Line | Href |")
            lines.append("|---|---:|---|")
            for item in data["links"]:
                _, line, href, kind = item
                lines.append(f"| `{kind}` | {line} | {href} |")
            lines.append("")

        # Breaks
        if data["breaks"]:
            lines.append("### Breaks")
            lines.append("| Tag | Line |")
            lines.append("|---|---:|")
            for t, line in data["breaks"]:
                lines.append(f"| `<{t}>` | {line} |")
            lines.append("")

        # Containers
        if data["containers"]:
            lines.append("### Containers (div/span)")
            lines.append("| Tag | Line | Notes |")
            lines.append("|---|---:|---|")
            for item in data["containers"]:
                t, line, attrs = item
                notes = attrs.get("class", "")
                lines.append(f"| `<{t}>` | {line} | {notes} |")
            lines.append("")

        # Meta
        lines.append("### Meta & Root")
        lines.append("| Tag | Line | Notes |")
        lines.append("|---|---:|---|")
        for item in data["meta"]:
            t, line, attrs = item
            notes = ""
            if "lang" in attrs:
                notes = f'lang="{attrs["lang"]}"'
            elif "charset" in attrs:
                notes = attrs["charset"]
            elif "name" in attrs:
                notes = f'{attrs["name"]}="{attrs.get("content", "")}"'
            elif "content" in attrs:
                notes = attrs["content"]
            lines.append(f"| `<{t}>` | {line} | {notes} |")
        lines.append("")

        # Entities
        if data["entities"]:
            lines.append("### HTML Entities")
            lines.append("| Entity | Line |")
            lines.append("|---|---:|")
            seen = set()
            for line, text in sorted(data["entities"]):
                key = (text, line)
                if key not in seen:
                    seen.add(key)
                    lines.append(f"| `{text}` | {line} |")
            lines.append("")

        # Comments
        if data["comments"]:
            lines.append("### Comments")
            lines.append("| Line | Text |")
            lines.append("|---:|---|")
            for line, text in data["comments"]:
                short = text[:80] + ("..." if len(text) > 80 else "")
                lines.append(f"| {line} | {short} |")
            lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def main():
    all_data = {}
    for filepath in HTML_FILES:
        filename = filepath.name
        author = extract_author(filepath)
        tags = extract_all(filepath)
        entities = find_entities(filepath)
        comments = find_comments(filepath)

        # Deduplicate: remove parser-generated comments and entities (regex ones are more accurate)
        tags_clean = [t for t in tags if t[0] not in ("comment", "entity", "charref")]
        combined = tags_clean + entities + comments
        classified = classify_tags(combined)
        all_data[filename] = (author, classified)

    checklist = generate_checklist(all_data)
    OUTPUT.write_text(checklist, encoding="utf-8")
    print(f"Generated {OUTPUT} with {len(HTML_FILES)} files")


if __name__ == "__main__":
    main()
