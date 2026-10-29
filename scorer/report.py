"""The calibration as one self-contained page.

The same inputs always produce the same bytes: no timestamps, no machine paths.
The page identifies its sample and limits.
"""
import argparse
import os
import sys
from html import escape

from scorer.calibrate import MissingCaseError, bar_words, document, false_passes_read, has_reading, not_bar_words, render_markdown, write_text
from scorer.stats import canonical_json


_CSS = os.path.join(os.path.dirname(__file__), "..", "ui", "ledger.css")


def esc(value):
    return escape("" if value is None else str(value), quote=True)


def _css_text(path=None):
    with open(path or _CSS, encoding="utf-8") as handle:
        return handle.read()


def _command(doc):
    cases = " --cases " + doc["cases_path"] if "cases_path" in doc else ""
    return "python3 -m scorer.report %s%s --out reports/calibration-v1.html --json reports/calibration-v1.json" % (doc["run"], cases)


def _summary(doc):
    rows = doc["codes"]
    return {
        "meeting": sum(1 for row in rows if row["meets_bar"]),
        "checks": len(rows),
        "false_passes": sum(len(row["false_passes"]) for row in rows),
        "lacks": sum(len(row["false_fails"]) for row in rows),
    }


def _numbers_pill(meets):
    """What meets_bar is: the two numbers in stats.MIN_AGREEMENT and stats.MIN_KAPPA."""
    if meets:
        return "ok", bar_words()
    return "alarm", not_bar_words()


def _notes(doc):
    found = []
    for row in doc["codes"]:
        readings = row["readings"]
        for kind, bucket in (("flag the labels lack", row["false_fails"]), ("false pass", row["false_passes"])):
            for case_id in sorted(bucket):
                found.append((row["code"], case_id, kind, readings.get(case_id)))
    return found


def render_html(doc, css):
    """One page. Every dynamic string is escaped. css is inlined, not linked."""
    summary = _summary(doc)
    meeting_class = "stat good" if summary["meeting"] == summary["checks"] and summary["checks"] else "stat alarm"
    passes_class = "stat alarm" if summary["false_passes"] else "stat"
    lacks_class = "stat alarm" if summary["lacks"] else "stat"
    model = doc.get("model") or "unknown"
    lines = [
        "<!DOCTYPE html>",
        "<html lang=\"en\">",
        "<head>",
        "<meta charset=\"utf-8\">",
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">",
        "<title>Do the checks agree?</title>",
        "<link rel=\"preconnect\" href=\"https://fonts.googleapis.com\">",
        "<link rel=\"preconnect\" href=\"https://fonts.gstatic.com\" crossorigin>",
        "<link rel=\"stylesheet\" href=\"https://fonts.googleapis.com/css2?family=Bangers&amp;family=Creepster&amp;family=IBM+Plex+Mono:wght@400;500;600&amp;family=Patrick+Hand&amp;display=swap\">",
        "<style>",
        css.rstrip("\n"),
        "</style>",
        "</head>",
        "<body>",
        "<div class=\"wrap\">",
        "<header class=\"cover panel\">",
        "<p class=\"issue\"><span>%s</span><span class=\"mono\">%s · %s tickets</span></p>" % (
            esc(doc.get("run_label") or doc["run"]), esc(model), esc(doc["cases"]),
        ),
        "<h1 class=\"mast\"><small>Settlement grader</small>Do the checks agree?</h1>",
        "<p class=\"dek\">Eleven plain-code checks on this run, scored against the labels a human made.</p>",
        "<div class=\"stats\">",
        "<div class=\"%s\"><b>%s</b><span>checks at %s</span></div>" % (meeting_class, esc(summary["meeting"]), esc(bar_words())),
        "<div class=\"%s\"><b>%s</b><span>false passes</span></div>" % (passes_class, esc(summary["false_passes"])),
        "<div class=\"%s\"><b>%s</b><span>flags the labels lack</span></div>" % (lacks_class, esc(summary["lacks"])),
        "</div>",
        "<p class=\"prov\">%s</p>" % esc(doc.get("provenance")),
        "</header>",
        "<section class=\"sec panel\">",
        "<div class=\"sec-head\">",
        "<h2>The eleven checks</h2>",
        "<p>Caught is how many of the human-labelled failures this check flagged. A false pass is one it missed. A false fail is a flag the labels lack. Beside the pill, false passes read are n of n when there are any. A reading counts when its text is non-empty after trimming.</p>",
        "</div>",
        "<table class=\"ledger\">",
        "<thead><tr><th>Code</th><th>Caught</th><th>Agreement</th><th>Kappa</th><th>False passes</th><th>False fails</th><th>%s</th></tr></thead>" % esc(bar_words()),
        "<tbody>",
    ]
    for row in doc["codes"]:
        pill, word = _numbers_pill(row["meets_bar"])
        caught = "%s of %s" % (row["tp"], row["tp"] + row["fn"])
        read = false_passes_read(row)
        read_figure = ' <span class="mono">%s</span>' % esc(read) if read else ""
        agreement = "none" if row["agreement"] is None else "%.4f" % row["agreement"]
        kappa = "none" if row["kappa"] is None else "%.4f" % row["kappa"]
        lines.append("<tr>")
        lines.append("<td data-label=\"Code\"><span class=\"mono\">%s</span></td>" % esc(row["code"]))
        lines.append("<td data-label=\"Caught\"><span class=\"mono\">%s</span></td>" % esc(caught))
        lines.append("<td data-label=\"Agreement\"><span class=\"mono\">%s</span></td>" % esc(agreement))
        lines.append("<td data-label=\"Kappa\"><span class=\"mono\">%s</span></td>" % esc(kappa))
        lines.append("<td data-label=\"False passes\"><span class=\"mono\">%s</span></td>" % esc(len(row["false_passes"])))
        lines.append("<td data-label=\"False fails\"><span class=\"mono\">%s</span></td>" % esc(len(row["false_fails"])))
        lines.append(
            "<td data-label=\"%s\"><span><span class=\"pill %s\">%s</span>%s</span></td>"
            % (esc(bar_words()), pill, esc(word), read_figure)
        )
        lines.append("</tr>")
    lines.extend([
        "</tbody>",
        "</table>",
        "</section>",
        "<section class=\"sec panel\">",
        "<div class=\"sec-head\">",
        "<h2>Disagreements</h2>",
        "<p>Each disagreement needs a reading. The labels are the owner's to change.</p>",
        "</div>",
    ])
    notes = _notes(doc)
    if not notes:
        lines.append("<p>No disagreements on this run.</p>")
    for code, case_id, kind, reading in notes:
        read = has_reading(reading)
        reading_class, reading_word = ("read", "read") if read else ("alarm", "unread")
        lines.append("<article class=\"note\">")
        lines.append("<p><span class=\"mono\">%s · %s</span> <span class=\"pill %s\">%s</span></p>" % (esc(code), esc(case_id), reading_class, reading_word))
        lines.append("<p>This is a %s.</p>" % esc(kind))
        lines.append("<p class=\"reading\">%s</p>" % esc(reading if read else "No reading recorded."))
        lines.append("</article>")
    lines.extend([
        "</section>",
        "<p class=\"colophon\">Regenerated by <code class=\"mono\">%s</code>. Fonts load from Google Fonts.</p>" % esc(_command(doc)),
        "</div>",
        "</body>",
        "</html>",
        "",
    ])
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Write the calibration page. The result is in sample.")
    parser.add_argument("run_dir")
    parser.add_argument("--cases", dest="cases_path", default="data/gold.json",
                        help="the cases file the run was graded from (default data/gold.json)")
    parser.add_argument("--out", required=True)
    parser.add_argument("--json", dest="json_out")
    parser.add_argument("--md", dest="md_out")
    args = parser.parse_args(argv)
    try:
        doc = document(args.run_dir, cases_path=args.cases_path)
    except (MissingCaseError, FileNotFoundError) as error:
        parser.error(str(error))
    css = _css_text()
    write_text(args.out, render_html(doc, css))
    if args.json_out:
        write_text(args.json_out, canonical_json(doc))
    if args.md_out:
        write_text(args.md_out, render_markdown(doc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
