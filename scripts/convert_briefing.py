#!/usr/bin/env python3
"""Convert market briefing markdown to structured JSON for the web frontend.

Usage:
    python scripts/convert_briefing.py input.md data/briefings.json

Parses the standard briefing markdown format (## sections, ### Key Updates /
Why It Matters / Bias, stock movers separated by ---, sources with URLs)
into a JSON array of briefing objects. If the output file already exists,
new briefings are appended (deduplicated by date+type).
"""
import json
import os
import re
import sys
from datetime import datetime


def parse_briefing(md: str) -> dict:
    """Parse a single briefing markdown file into a structured dict."""

    # Title and metadata
    title_match = re.match(r"# (.+)", md)
    title = title_match.group(1).strip() if title_match else ""

    briefing_type = "closing" if "closing" in title.lower() else "morning"
    date_match = re.search(r"(\d{4}-\d{2}-\d{2})", title)
    briefing_date = date_match.group(1) if date_match else datetime.now().strftime("%Y-%m-%d")

    # Split into sections by ##
    sections_raw = re.split(r"^## ", md, flags=re.MULTILINE)

    # Parse "At a Glance"
    glance = []
    if len(sections_raw) > 1:
        glance = [l[2:].strip() for l in sections_raw[1].split("\n") if l.startswith("- ")]

    parsed_sections = []
    movers = []
    watchpoints = []
    sources = []

    for section_text in sections_raw[2:] if len(sections_raw) > 2 else []:
        section_title = section_text.split("\n")[0].strip()

        if section_title == "Stock Movers and Watchlist":
            mover_blocks = section_text.split("---")
            for block in mover_blocks:
                block = block.strip()
                if not block or block.startswith("##"):
                    continue
                stock_match = re.search(r"\*\*Stock / Asset:\*\*\s*(.+)", block)
                catalyst_match = re.search(r"\*\*Today's Catalyst:\*\*\s*(.+)", block)
                bias_match = re.search(r"\*\*Bias:\*\*\s*(.+)", block)
                watch_match = re.search(r"\*\*What To Watch Tomorrow:\*\*\s*(.+)", block)
                if stock_match:
                    movers.append({
                        "stock": stock_match.group(1).strip(),
                        "catalyst": catalyst_match.group(1).strip() if catalyst_match else "",
                        "bias": bias_match.group(1).strip() if bias_match else "",
                        "watch": watch_match.group(1).strip() if watch_match else ""
                    })

        elif section_title == "Tomorrow's Watchpoints":
            watchpoints = [l[2:].strip() for l in section_text.split("\n") if l.startswith("- ")]

        elif section_title == "Sources":
            for line in section_text.split("\n"):
                if line.startswith("- "):
                    item = line[2:].strip()
                    if " — " in item:
                        parts = item.rsplit(" — ", 1)
                        sources.append({"title": parts[0].strip(), "url": parts[1].strip()})
                    elif " - " in item:
                        parts = item.rsplit(" - ", 1)
                        sources.append({"title": parts[0].strip(), "url": parts[1].strip()})
                    else:
                        sources.append({"title": item, "url": ""})

        else:
            # Standard section with Key Updates / Why It Matters / Bias
            sub_sections = re.split(r"^### ", section_text, flags=re.MULTILINE)
            updates = []
            analysis = ""
            bias = ""

            for sub in sub_sections:
                if sub.startswith("Key Updates"):
                    updates = [l[2:].strip() for l in sub.split("\n") if l.startswith("- ")]
                elif sub.startswith("Why It Matters"):
                    analysis = "\n".join(sub.split("\n")[1:]).strip()
                elif sub.startswith("Bias"):
                    bias = "\n".join(sub.split("\n")[1:]).strip()

            parsed_sections.append({
                "title": section_title,
                "updates": updates,
                "analysis": analysis,
                "bias": bias
            })

    return {
        "date": briefing_date,
        "type": briefing_type,
        "title": title,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "glance": glance,
        "sections": parsed_sections,
        "movers": movers,
        "watchpoints": watchpoints,
        "sources": sources
    }


def main():
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <input.md> <output.json>")
        print(f"  Converts briefing markdown to JSON for the web frontend.")
        print(f"  If output.json exists, new briefing is appended (dedup by date+type).")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2]

    with open(input_path, encoding="utf-8") as f:
        md = f.read()

    briefing = parse_briefing(md)

    # Load existing briefings if file exists, append
    briefings = []
    if os.path.exists(output_path):
        with open(output_path, encoding="utf-8") as f:
            briefings = json.load(f)

    # Deduplicate by date+type — replace if exists
    key = f"{briefing['date']}_{briefing['type']}"
    briefings = [b for b in briefings if f"{b['date']}_{b['type']}" != key]
    briefings.append(briefing)

    # Sort by date descending (newest first)
    briefings.sort(key=lambda b: b["date"], reverse=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(briefings, f, indent=2, ensure_ascii=False)

    print(f"Converted: {briefing['title']}")
    print(f"  Sections: {len(briefing['sections'])}, Movers: {len(briefing['movers'])}, Sources: {len(briefing['sources'])}")
    print(f"  Total briefings in {output_path}: {len(briefings)}")


if __name__ == "__main__":
    main()
