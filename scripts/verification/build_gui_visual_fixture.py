"""Build a local, visibly labelled UI-only review file from synthetic API evidence.

Never load customer data here. This file is not proof of browser-to-backend IO.
The executable GUI itself does not contain a demo/fake API mode.
"""
import argparse
import base64
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--analysis-json", type=Path, required=True)
    parser.add_argument("--synthetic-source-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    record = json.loads(args.analysis_json.read_text())
    result = record.get("result", record)
    sources = {}
    for row in result["objects"] + result["modules"]:
        path = row["input_ref"]["relative_path"]
        root = args.synthetic_source_directory.resolve()
        candidate = (root / path).resolve()
        if not candidate.is_relative_to(root):
            raise ValueError("unsafe fixture path")
        raw = candidate.read_bytes()
        import hashlib
        if hashlib.sha256(raw).hexdigest() != row["input_ref"]["raw_sha256"]:
            raise ValueError("fixture bytes mismatch")
        sources[path] = {"text": raw.decode("utf-8-sig"), "encoding": "UTF-8", "size_bytes": len(raw), "input_ref": row["input_ref"]}
    assets = ROOT / "rentgen_core" / "gui_assets"
    model = (assets / "model.js").read_text().replace("export function", "function")
    app = (assets / "app.js").read_text()
    app = re.sub(r"^import[^\n]+\n", "const esc=escapeHTML;\n", app)
    app = app.replace("token:location.hash.slice(1)", "token:''")
    start = app.index("async function api("); end = app.index("function toast(", start)
    app = app[:start] + """async function api(path,options={}){if(path==='/api/session')return {project_name:'Синтетический пример'};if(path.startsWith('/api/source?')){const key=new URLSearchParams(path.split('?')[1]).get('path');if(previewSources[key])return previewSources[key];}throw {code:'VISUAL_PREVIEW_ONLY'};}\n""" + app[end:]
    app += "\nif(location.hash!=='#empty'){state.result=previewResult;state.filename='synthetic-export.zip';state.completedAt='2026-10-06T02:00:00Z';state.job='visual-only';render();} $('runtime-status').textContent='Визуальное QA · синтетический пример · API не подключён';"
    data = "const previewResult=" + json.dumps(result,ensure_ascii=False) + ";const previewSources=" + json.dumps(sources,ensure_ascii=False) + ";\n"
    data = data.replace("<", "\\u003c")
    html = (assets / "index.html").read_text()
    html = html.replace('<link rel="stylesheet" href="/app.css">', '<style>' + (assets / "app.css").read_text() + '</style>')
    html = html.replace('<script type="module" src="/app.js"></script>', '')
    icon = 'data:image/svg+xml;base64,' + base64.b64encode((assets / 'mark.svg').read_bytes()).decode()
    html = html.replace('/mark.svg',icon)
    html = html.replace('</body>', '<script>(async()=>{\n' + model + '\n' + data + app + '\n})();</script></body>')
    args.output.write_text(html)
    print(args.output)

if __name__ == '__main__':
    main()
