
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import List, Optional

import typer
from prometheus_client import Counter, Gauge, Histogram, start_http_server

from .config import DEFAULT_CONFIG, OutputFormat, ScrapeConfig
from .scraper import ITSScraper
from .writers import persist_article

app = typer.Typer(help="Enhanced scraper for 1C ITS documentation.")

REQUEST_COUNTER = Counter(
    "its_scraper_requests_total", "Total requests performed", ["status"]
)
ARTICLE_COUNTER = Counter(
    "its_scraper_articles_total", "Total articles processed", ["state"]
)
REQUEST_DURATION = Histogram(
    "its_scraper_request_duration_seconds", "Duration of scrape operation"
)
RATE_LIMIT_GAUGE = Gauge(
    "its_scraper_delay_seconds", "Current delay between requests (adaptive)"
)


def _load_config(config_path: Optional[Path]) -> ScrapeConfig:
    if config_path:
        return ScrapeConfig.from_json(config_path)
    return DEFAULT_CONFIG


@app.command()
def scrape(
    start_url: str = typer.Argument(
        DEFAULT_CONFIG.start_url, help="Start URL that contains the article list."
    ),
    limit: Optional[int] = typer.Option(
        DEFAULT_CONFIG.limit,
        help="Limit amount of articles to download (default: unlimited).",
    ),
    format: Optional[list[OutputFormat]] = typer.Option(
        None,
        "--format",
        "-f",
        case_sensitive=False,
        help=f"Output formats ({', '.join(OutputFormat.list())}).",
    ),
    config_path: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Optional path to JSON config that overrides defaults.",
    ),
    update_only: bool = typer.Option(
        False,
        "--update",
        help="Skip already downloaded articles (metadata must exist).",
    ),
    concurrency: Optional[int] = typer.Option(
        None,
        "--concurrency",
        "-n",
        help="Override concurrency (default from config).",
    ),
    sleep: Optional[float] = typer.Option(
        None,
        "--sleep",
        "-s",
        help="Delay between HTTP requests in seconds.",
    ),
    output_dir: Path = typer.Option(
        DEFAULT_CONFIG.output_directory,
        "--output",
        "-o",
        help="Directory for scraped files.",
    ),
    user_agent: Optional[List[str]] = typer.Option(
        None,
        "--user-agent",
        help="Override default user agent (can be specified multiple times for rotation).",
    ),
    user_agent_file: Optional[Path] = typer.Option(
        None,
        "--user-agent-file",
        help="Path to a file with user agents (one per line) for rotation.",
    ),
    proxy: Optional[str] = typer.Option(
        None,
        "--proxy",
        help="HTTP(S) proxy URL (e.g. http://user:pass@host:port).",
    ),
    metrics_port: Optional[int] = typer.Option(
        None,
        "--metrics-port",
        help="Expose Prometheus metrics on given port (e.g. 9200).",
    ),
    stream: bool = typer.Option(
        False,
        "--stream",
        help="Stream articles to stdout as JSONL instead of writing to disk.",
    ),
) -> None:
    """
    Scrape ITS documentation starting from START_URL and produce the selected formats.
    """
    config = _load_config(config_path)
    config.start_url = start_url
    if limit is not None:
        config.limit = limit
    if format:
        config.formats = [OutputFormat(f.lower()) for f in format]
    if concurrency is not None:
        config.concurrency = concurrency
    if sleep is not None:
        config.delay_between_requests = sleep
    config.update_only = update_only
    config.output_directory = output_dir
    if user_agent:
        config.user_agents = list(user_agent)
    if user_agent_file and user_agent_file.exists():
        config.user_agents.extend(
            ua.strip()
            for ua in user_agent_file.read_text(encoding="utf-8").splitlines()
            if ua.strip()
        )
    if proxy:
        config.proxy = proxy
    if metrics_port:
        config.enable_metrics = True
        start_http_server(metrics_port)

    if config.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    async def _runner() -> None:
        async with ITSScraper(config) as scraper:
            metrics_dict = {
                "requests": REQUEST_COUNTER,
                "rate": RATE_LIMIT_GAUGE,
            }
            RATE_LIMIT_GAUGE.set(config.delay_between_requests)
            with REQUEST_DURATION.time():
                results = await scraper.scrape(metrics=metrics_dict)
            for article, existing_meta in results:
                if stream:
                    typer.echo(json.dumps(article.to_dict(), ensure_ascii=False))
                    ARTICLE_COUNTER.labels(state="streamed").inc()
                    continue
                files = list(
                    persist_article(article, config, existing_meta=existing_meta)
                )
                if not files and config.update_only:
                    scraper.stats.skipped += 1
                    ARTICLE_COUNTER.labels(state="skipped").inc()
                else:
                    ARTICLE_COUNTER.labels(state="stored").inc()
            typer.echo(
                f"Fetched {scraper.stats.fetched}, "
                f"skipped {scraper.stats.skipped}, "
                f"failed {scraper.stats.failed}"
            )

    asyncio.run(_runner())


@app.command()
def generate_config(path: Path = typer.Argument(Path("its-scraper.config.json"))) -> None:
    """
    Generate default configuration file.
    """
    DEFAULT_CONFIG.to_json(path)
    typer.echo(f"Wrote config to {path}")


def main() -> None:  # pragma: no cover - entrypoint
    app()


if __name__ == "__main__":  # pragma: no cover
    main()

