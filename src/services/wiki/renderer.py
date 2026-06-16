"""
Wiki Markdown Renderer (Extended)
Handles custom syntax extensions using Marko.
"""

import re

import marko
from marko.block import BlockElement
from marko.inline import InlineElement

# --- Custom Elements ---


class WikiLink(InlineElement):
    """
    Parses [[Slug]] or [[Slug|Label]]
    """

    pattern = re.compile(r"\[\[(.*?)(?:\|(.*?))?\]\]")
    priority = 5

    def __init__(self, match):
        self.target = match.group(1)
        self.label = match.group(2) or self.target


class Transclusion(BlockElement):
    """
    Parses {{code:path.to.object}}
    """

    pattern = re.compile(r"\{\{code:(.*?)\}\}")
    priority = 5

    def __init__(self, match):
        self.target = match.group(1)

    @classmethod
    def match(cls, source):
        return source.expect_re(cls.pattern)

    @classmethod
    def parse(cls, source):
        m = source.match
        source.consume()
        return cls(m)


# --- Custom Renderer Mixin ---


class WikiRendererMixin:
    def render_wiki_link(self, element):
        return f'<a href="/wiki/pages/{element.target}" class="wiki-link">{element.label}</a>'

    def render_transclusion(self, element):
        return (
            f'<div class="code-transclusion" data-target="{element.target}">'
            f'<pre><code class="language-python"># Transcluded: {element.target}\n# (Content loading...)</code></pre>'
            f"</div>"
        )


# --- Extension Object ---


class WikiMarkoExtension:
    elements = [WikiLink, Transclusion]
    renderer_mixins = [WikiRendererMixin]
    parser_mixins = []  # Required by marko


# --- Main Renderer Class ---


class WikiRenderer:
    """
    Renders Extended Markdown for the Enterprise Wiki using Marko.
    """

    def __init__(self):
        self.markdown = marko.Markdown()
        self.markdown.use(WikiMarkoExtension)

    def render(self, text: str) -> str:
        """
        Render markdown to HTML.
        """
        if not text:
            return ""
        return self.markdown.convert(text)
