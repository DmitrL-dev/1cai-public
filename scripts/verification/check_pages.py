#!/usr/bin/env python3
"""Dependency-free checks for the public static Pages artifact. Run from any cwd."""
from __future__ import annotations
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / 'site'

class Document(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids: list[str] = []
        self.links: list[tuple[str, str]] = []
        self.els: list[tuple[str, dict[str, str]]] = []
    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        self.els.append((tag, attrs))
        if 'id' in attrs:
            self.ids.append(attrs['id'])
        for key in ('href', 'src'):
            if attrs.get(key):
                self.links.append((tag, attrs[key]))
        assert not any(key.startswith('on') for key in attrs), f'Inline handler in {tag}'


def validate() -> None:
    assert SITE.is_dir(), 'Missing site/'
    assert not any(path.is_symlink() for path in SITE.rglob('*')), 'Site artifact must not contain symlinks'
    files = sorted(path for path in SITE.rglob('*') if path.is_file())
    assert (SITE / '.nojekyll').is_file(), 'Missing .nojekyll'
    assert (SITE / '404.html').is_file(), 'Missing 404 page'
    concept_images = {SITE / 'assets' / 'ide-concept' / f'{name}.png'
                      for name in ('editor', 'review', 'assistant')}
    assert all(path.suffix.lower() in {'.html', '.css', '.js', '.svg', ''}
               or path in concept_images for path in files), 'Unexpected site artifact'
    assert all(path.is_file() and path.read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
               for path in concept_images), 'Missing or invalid concept PNG'
    assert all(path.stat().st_size < 350_000 for path in concept_images), 'Concept image unexpectedly large'
    size = sum(path.stat().st_size for path in files)
    assert size < 1_100_000, f'Static artifact unexpectedly large: {size} bytes'
    for page in SITE.glob('*.html'):
        markup = page.read_text(encoding='utf-8')
        assert '<html lang="ru"' in markup, f'{page.name}: missing language'
        assert 'name="viewport"' in markup, f'{page.name}: missing viewport'
        assert re.search(r'<title>.+?</title>', markup), f'{page.name}: missing title'
        doc = Document()
        doc.feed(markup)
        assert len(set(doc.ids)) == len(doc.ids), f'{page.name}: duplicate id'
        for tag, target in doc.links:
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc:
                assert parsed.scheme == 'https', f'Insecure external URL: {target}'
                assert tag not in {'script', 'img'}, f'Unexpected external dependency: {target}'
                assert parsed.hostname in {'github.com', 'dmitrl-dev.github.io'}, f'Unexpected external destination: {target}'
                repo_prefix = '/DmitrL-dev/1cai-public/blob/main/'
                if parsed.hostname == 'github.com' and parsed.path.startswith(repo_prefix):
                    repo_path = (ROOT / unquote(parsed.path[len(repo_prefix):])).resolve()
                    assert repo_path.is_relative_to(ROOT) and repo_path.is_file(), f'Missing repository document: {target}'
            elif parsed.path:
                if parsed.path == '/1cai-public/':
                    assert page.name == '404.html'
                    continue
                local = (page.parent / unquote(parsed.path)).resolve()
                assert local.is_relative_to(SITE), f'Link leaves artifact: {target}'
                assert local.is_file(), f'Broken local asset: {target}'
            if not parsed.path and not parsed.scheme and parsed.fragment:
                assert unquote(parsed.fragment) in doc.ids, f'Broken anchor: {target}'
        for tag, attrs in doc.els:
            for key in ('aria-controls', 'aria-labelledby'):
                for ref in attrs.get(key, '').split():
                    assert ref in doc.ids, f'Unresolved {key}: {ref}'
            if tag == 'img':
                assert 'alt' in attrs, 'Missing image alternative'
        if page.name == 'index.html':
            assert sum(tag == 'h1' for tag, _ in doc.els) == 1, 'Expected one h1'
            tabs = [attrs for _, attrs in doc.els if attrs.get('role') == 'tab']
            panels = [attrs for _, attrs in doc.els if attrs.get('role') == 'tabpanel']
            assert len(tabs) == len(panels) == 3, 'Expected three walkthrough steps'
            assert sum(tab.get('aria-selected') == 'true' for tab in tabs) == 1
            assert sum('hidden' not in panel for panel in panels) == 1
            assert 'не скриншот продукта' in markup.lower(), 'Missing illustration disclosure'
            assert 'Синтетический пример' in markup, 'Missing demo disclosure'
            assert 'Не запускались в демо' in markup, 'Demo must not fabricate checks'
            assert 'core-v0.1.0-dev17' in markup and 'companion-v0.1.18' in markup
            assert 'id="nextgen"' in markup and 'IDE-DEVELOPMENT-PLAN.md' in markup
            assert 'Статические макеты' in markup and 'не снимки работающей IDE' in markup
            assert 'Новая среда ещё не входит' in markup
            assert all(f'assets/ide-concept/{name}.png' in markup
                       for name in ('editor', 'review', 'assistant'))
    js = (SITE / 'site.js').read_text()
    assert not re.search(r'\b(fetch|XMLHttpRequest|localStorage|sessionStorage|eval)\s*[.(]', js), 'Unexpected network/storage/dynamic code'
    css = (SITE / 'styles.css').read_text()
    assert 'prefers-reduced-motion:reduce' in css
    assert 'focus-visible' in css
    assert '@import' not in css and 'http' not in css, 'Unexpected external CSS dependency'
    print(f'PASS: {len(files)} files; {size:,} bytes; assets, anchors, tab relationships, privacy and content boundaries checked.')
    print('Browser rendering, interaction, contrast and external HTTP status are separate checks.')

if __name__ == '__main__':
    validate()
