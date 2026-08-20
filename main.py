"""Entry point: python main.py -> mo GUI MQL5 Source Crawler.

Chay CLI (khong GUI):
    python main.py --cli --keyword "Gold,XAUUSD" --pages 1 3 --max 20
"""

from __future__ import annotations

import argparse
import sys

from utils.logger import setup_logging


def run_gui() -> int:
    from PySide6.QtWidgets import QApplication

    from gui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("MQL5 Source Crawler")
    window = MainWindow()
    window.show()
    return app.exec()


def run_cli(args: argparse.Namespace) -> int:
    from crawler.crawler import CrawlConfig, Crawler
    from crawler.search import SearchQuery
    from exporter.exporter import Exporter
    from models.source import SourceType

    type_map = {
        "ea": SourceType.EA,
        "indicator": SourceType.INDICATOR,
        "script": SourceType.SCRIPT,
        "library": SourceType.LIBRARY,
    }
    config = CrawlConfig(
        keywords=SearchQuery.parse_keywords(args.keyword or ""),
        types=[type_map[t.lower()] for t in args.type],
        platforms=args.platform,
        page_from=args.pages[0],
        page_to=args.pages[1],
        max_results=args.max,
        delay=args.delay,
        download=not args.no_download,
        download_dir=args.download_dir,
        db_path=args.db,
    )
    crawler = Crawler(config, on_message=lambda m: print(m))
    records = crawler.run()
    if args.export:
        paths = Exporter(args.output_dir).export_all(records, config.db_path)
        for key, value in paths.items():
            print(f"{key}: {value}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="MQL5 Source Crawler")
    parser.add_argument("--cli", action="store_true", help="chay che do dong lenh")
    parser.add_argument("--keyword", default="", help="keyword, phan cach bang dau phay")
    parser.add_argument(
        "--type", nargs="*", default=["ea"], help="ea | indicator | script | library"
    )
    parser.add_argument("--platform", nargs="*", default=["mt5"], help="mt5 | mt4")
    parser.add_argument("--pages", nargs=2, type=int, default=[1, 1], metavar=("FROM", "TO"))
    parser.add_argument("--max", type=int, default=50, help="so ket qua toi da")
    parser.add_argument("--delay", type=float, default=2.0, help="delay giua cac request (giay)")
    parser.add_argument("--no-download", action="store_true", help="chi lay metadata")
    parser.add_argument("--download-dir", default="downloads")
    parser.add_argument("--output-dir", default="output")
    parser.add_argument("--db", default="output/database.db")
    parser.add_argument("--export", action="store_true", help="xuat CSV/JSON/XLSX/MQ5 sau khi chay")
    args = parser.parse_args(argv)

    setup_logging()
    return run_cli(args) if args.cli else run_gui()


if __name__ == "__main__":
    raise SystemExit(main())
