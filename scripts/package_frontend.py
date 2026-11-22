"""Package public site with content-addressed script and stylesheet URLs."""
from pathlib import Path
from hashlib import sha256
import shutil
import json
import re

src = Path("site")
out = Path("dist-pages")
if out.exists():
    shutil.rmtree(out)
shutil.copytree(src, out)
html_path = out / "index.html"
html = html_path.read_text(encoding="utf-8")
names = {}
for original, attr in (("app.js", "src"), ("style.css", "href")):
    asset = out / original
    content = asset.read_bytes()
    version = sha256(content).hexdigest()[:16]
    name = f"{asset.stem}.{version}{asset.suffix}"
    (out / name).write_bytes(content)
    pattern = re.escape(attr + '="' + original) + r'(?:\?[^"]*)?"'
    html, count = re.subn(pattern, f'{attr}="{name}"', html)
    assert count == 1, (original, count)
    names[original] = name
assert '<h1 id="heading">每日精选' in html
client_script = (out / names["app.js"]).read_text(encoding="utf-8")
assert re.search(r"\blet data=.*\bmode='daily',", client_script), "Daily must remain the homepage"
css = (out / names["style.css"]).read_text()
for name in ("lighthouse-hero", "lighthouse-postcard", "ai-art", "shopping-art", "media-art", "other-art"):
    file = out / "art" / (name + ".webp")
    head = file.read_bytes()[:12]
    assert head[:4] == b"RIFF" and head[8:12] == b"WEBP", name
    assert f'art/{name}.webp' in css, name
# Visible release identifier makes stale HTML verifiable without developer tools.
release = sha256(("\n".join(names.values()) + html).encode()).hexdigest()[:10]
html = html.replace("</footer>", f" · 前端版本 {release}</footer>")
html_path.write_text(html, encoding="utf-8")
(out / "version.json").write_text(json.dumps({"release": release, "assets": names, "defaultView": "daily"}, ensure_ascii=False), encoding="utf-8")
print("Published frontend release:", release, names)
