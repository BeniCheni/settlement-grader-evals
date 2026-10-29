"""AA contrast from the stylesheet's own tokens. The lowest pair is what the page reports."""
import re
import unittest


_VAR = re.compile(r"--([A-Za-z0-9-]+)\s*:\s*([^;]+);")


def brace_block(css, header):
    start = css.find(header)
    if start < 0:
        raise AssertionError("missing %s" % header)
    open_at = css.find("{", start)
    depth = 0
    for index in range(open_at, len(css)):
        if css[index] == "{":
            depth += 1
        elif css[index] == "}":
            depth -= 1
            if depth == 0:
                return css[open_at + 1:index]
    raise AssertionError("unclosed %s" % header)


def parse_color(value):
    value = value.strip()
    if value.startswith("#") and len(value) == 7:
        return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5)), 1.0
    match = re.fullmatch(r"rgb\(\s*(\d+)\s+(\d+)\s+(\d+)\s*(?:/\s*([0-9.]+)\s*)?\)", value)
    if not match:
        raise ValueError(value)
    alpha = 1.0 if match.group(4) is None else float(match.group(4))
    return (int(match.group(1)), int(match.group(2)), int(match.group(3))), alpha


def composite(fg, alpha, bg):
    return tuple(int(round(fg[i] * alpha + bg[i] * (1.0 - alpha))) for i in range(3))


def _channel(value):
    scaled = value / 255.0
    if scaled <= 0.04045:
        return scaled / 12.92
    return ((scaled + 0.055) / 1.055) ** 2.4


def relative_luminance(rgb):
    red, green, blue = (_channel(part) for part in rgb)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(fg, bg):
    lighter = max(relative_luminance(fg), relative_luminance(bg))
    darker = min(relative_luminance(fg), relative_luminance(bg))
    return (lighter + 0.05) / (darker + 0.05)


def _solid(theme, name):
    rgb, alpha = parse_color(theme[name])
    if alpha < 1:
        raise AssertionError("%s is translucent" % name)
    return rgb


def theme_maps(css):
    dark = dict(_VAR.findall(brace_block(css, ":root{")))
    media = dict(_VAR.findall(brace_block(css, ':root:not([data-theme="dark"]){')))
    explicit = dict(_VAR.findall(brace_block(css, ':root[data-theme="light"]{')))
    light = dict(dark)
    light.update(explicit)
    return dark, light, media, explicit


def stat_scrim(css):
    block = brace_block(css, ".stat{")
    match = re.search(r"background:\s*rgb\(\s*(\d+)\s+(\d+)\s+(\d+)\s*/\s*([0-9.]+)\s*\)", block)
    if not match:
        raise AssertionError("stat background is not the draft scrim")
    rgb = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
    return rgb, float(match.group(4))


def text_pairs(theme, scrim):
    found = []

    def add(label, fg, bg):
        found.append((label, contrast_ratio(fg, bg)))

    for label, fg, bg in (
        ("ink on ground", "ink", "ground"),
        ("ink on panel", "ink", "panel"),
        ("ink on panel-2", "ink", "panel-2"),
        ("ink-2 on ground", "ink-2", "ground"),
        ("ink-2 on panel", "ink-2", "panel"),
        ("ink-2 on panel-2", "ink-2", "panel-2"),
        ("slime on panel", "slime", "panel"),
        ("blood on panel", "blood", "panel"),
        ("lamp-ink on panel-2", "lamp-ink", "panel-2"),
        ("cover-ink on cover-from", "cover-ink", "cover-from"),
        ("cover-ink on cover-to", "cover-ink", "cover-to"),
        ("cover-prov-ink on cover-prov-bg", "cover-prov-ink", "cover-prov-bg"),
    ):
        add(label, _solid(theme, fg), _solid(theme, bg))
    lamp_rgb, lamp_alpha = parse_color(theme["lamp-bg"])
    if lamp_alpha < 1:
        lamp_bg = composite(lamp_rgb, lamp_alpha, _solid(theme, "panel-2"))
    else:
        lamp_bg = lamp_rgb
    add("lamp-ink on lamp-bg", _solid(theme, "lamp-ink"), lamp_bg)
    scrim_rgb, scrim_alpha = scrim
    for end in ("cover-from", "cover-to"):
        backdrop = composite(scrim_rgb, scrim_alpha, _solid(theme, end))
        add("stat-alarm on %s" % end, _solid(theme, "stat-alarm"), backdrop)
        add("stat-good on %s" % end, _solid(theme, "stat-good"), backdrop)
        add("cover-ink on stat %s" % end, _solid(theme, "cover-ink"), backdrop)
    return found


def ranked_pairs(css):
    dark, light, media, explicit = theme_maps(css)
    if media != explicit:
        raise AssertionError("the two light-theme blocks disagree")
    scrim = stat_scrim(css)
    ranked = []
    for theme_name, theme in (("dark", dark), ("light", light)):
        for label, ratio in text_pairs(theme, scrim):
            ranked.append((ratio, theme_name, label))
    ranked.sort(key=lambda item: item[0])
    return ranked


def lowest_pair(css):
    return ranked_pairs(css)[0]


class ContrastTests(unittest.TestCase):
    def test_black_on_white_is_21(self):
        self.assertAlmostEqual(contrast_ratio((0, 0, 0), (255, 255, 255)), 21.0, places=2)

    def test_every_text_pair_in_ledger_css_meets_aa(self):
        with open("ui/ledger.css", encoding="utf-8") as handle:
            css = handle.read()
        self.assertNotIn("url(", css)
        ratio, theme, label = lowest_pair(css)
        self.assertGreaterEqual(ratio, 4.5, "%s %s is %.3f" % (theme, label, ratio))


if __name__ == "__main__":
    with open("ui/ledger.css", encoding="utf-8") as handle:
        css = handle.read()
    ratio, theme, label = lowest_pair(css)
    print("%.3f %s %s" % (ratio, theme, label))
    for item_ratio, item_theme, item_label in ranked_pairs(css)[:6]:
        print("%.3f %s %s" % (item_ratio, item_theme, item_label))
