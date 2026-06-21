"""
Telegram response formatting helpers.

The bot may run in consoles, containers and customer environments with mixed
encodings, so user-facing fallback text is kept in ASCII.
"""

from typing import Dict


class TelegramFormatter:
    """Format Telegram bot responses."""

    @staticmethod
    def format_search_results(results: Dict) -> str:
        """Format semantic search results."""
        if not results or not results.get("results"):
            return "No results found. Try a more specific query."

        items = results.get("results", [])
        count = len(items)
        text = f"**Found {count} result(s)**\n\n"

        for i, item in enumerate(items[:5], 1):
            name = item.get("name", "Unknown")
            module = item.get("module", "")
            score = item.get("score", 0)
            description = item.get("description", "")

            text += f"**{i}. {name}**\n"

            if module:
                text += f"`{module}`\n"

            if description:
                desc_short = description[:150] + "..." if len(description) > 150 else description
                text += f"{desc_short}\n"

            if score:
                text += f"Relevance: {score:.1%}\n"

            text += "\n"

        if count > 5:
            text += f"_...and {count - 5} more result(s)_\n\n"

        text += "Need code? Use /show <number>."
        return text

    @staticmethod
    def format_code(code: str, language: str = "bsl") -> str:
        """Format code with Telegram Markdown code fences."""
        return f"```{language}\n{code}\n```"

    @staticmethod
    def format_generated_code(result: Dict) -> str:
        """Format generated code response."""
        code = result.get("code", "")
        explanation = result.get("explanation", "")
        function_name = result.get("function_name", "")

        text = "**Generated code**\n\n"

        if function_name:
            text += f"Function: `{function_name}`\n\n"

        if explanation:
            text += f"**Explanation:**\n{explanation}\n\n"

        text += f"**Code:**\n{TelegramFormatter.format_code(code)}\n\n"
        text += "_Review and test this code before use._"
        return text

    @staticmethod
    def format_dependencies(result: Dict) -> str:
        """Format dependency analysis response."""
        function_name = result.get("function", "")
        module_name = result.get("module", "")

        text = "**Dependency analysis**\n\n"
        text += f"Function: `{function_name}`\n"
        text += f"Module: `{module_name}`\n\n"

        uses = result.get("uses", [])
        if uses:
            text += f"**Uses ({len(uses)}):**\n"
            for func in uses[:10]:
                text += f"  -> `{func}`\n"
            if len(uses) > 10:
                text += f"  _...and {len(uses) - 10} more_\n"
            text += "\n"

        used_by = result.get("used_by", [])
        if used_by:
            text += f"**Used by ({len(used_by)}):**\n"
            for func in used_by[:10]:
                text += f"  <- `{func}`\n"
            if len(used_by) > 10:
                text += f"  _...and {len(used_by) - 10} more_\n"
            text += "\n"

        if result.get("graph_url"):
            text += f"[Graph visualization]({result['graph_url']})\n"

        return text

    @staticmethod
    def format_error(error: str) -> str:
        """Format an error response."""
        return f"**Error:**\n\n{error}\n\nTry rephrasing the request or use /help."

    @staticmethod
    def format_help() -> str:
        """Return command help."""
        return """**1C AI Assistant**

**Commands:**

`/search <query>` - semantic code search
Example: `/search VAT calculation`

`/generate <description>` - generate BSL code
Example: `/generate discount calculation function`

`/deps <module> <function>` - dependency analysis
Example: `/deps SalesServer CalculateVAT`

`/stats` - your usage statistics
`/premium` - Premium information
`/help` - this help

**Natural questions:**
Send a question in plain text and the bot will try to help.

You can also upload `.bsl`, `.os` or `.txt` files for local BSL diagnostics.
"""

    @staticmethod
    def format_stats(stats: Dict) -> str:
        """Format user usage statistics."""
        requests_today = stats.get("requests_today", 0)
        requests_total = stats.get("requests_total", 0)
        limit_today = stats.get("limit_today", 100)
        is_premium = stats.get("is_premium", False)

        text = "**Your statistics**\n\n"

        if is_premium:
            text += "**Premium account** - unlimited.\n\n"
        else:
            remaining = max(0, limit_today - requests_today)
            text += f"Requests today: {requests_today}/{limit_today}\n"
            text += f"Remaining: {remaining}\n\n"

        text += f"Total requests: {requests_total}\n"

        if not is_premium and requests_today >= limit_today * 0.8:
            text += f"\nYou have used {requests_today}/{limit_today} requests today.\n"
            text += "Use /premium to discuss higher limits."

        return text

    @staticmethod
    def format_premium_info() -> str:
        """Return Premium information."""
        return """**Premium capabilities**

- Higher request limits
- Priority processing
- Extended code analysis
- API integration
- Result export
- Additional AI agents

Interested in Premium access? Create a GitHub issue with your use case:
https://github.com/DmitrL-dev/1cai-public/issues
"""
