thonimport argparse
import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from extractors.instagram_parser import InstagramParser
from extractors.utils_data import (
    load_inputs,
    load_settings,
    sanitize_usernames,
)
from outputs.exporter import Exporter

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger("instagram_following_scraper")

def resolve_paths() -> Dict[str, Path]:
    """
    Resolve important project paths relative to this file.
    """
    src_dir = Path(__file__).resolve().parent
    project_root = src_dir.parent

    paths = {
        "project_root": project_root,
        "src_dir": src_dir,
        "config": src_dir / "config",
        "data": project_root / "data",
        "default_input": project_root / "data" / "inputs.sample.json",
        "default_output": project_root / "data" / "sample_output.json",
        "settings_file": src_dir / "config" / "settings.json",
    }
    return paths

def parse_args(paths: Dict[str, Path]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Instagram Following Scraper - extract following lists for given usernames."
    )
    parser.add_argument(
        "-i",
        "--input",
        type=str,
        default=str(paths["default_input"]),
        help="Path to input JSON file containing usernames (default: data/inputs.sample.json)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=str(paths["default_output"]),
        help="Path to output JSON file (default: data/sample_output.json)",
    )
    parser.add_argument(
        "--max-following",
        type=int,
        default=None,
        help="Maximum number of following profiles to fetch per user. "
        "Overrides value from settings.json if provided.",
    )
    parser.add_argument(
        "--format",
        type=str,
        choices=["json", "csv", "both"],
        default=None,
        help="Output format: json, csv, or both. Defaults to settings.json.",
    )
    return parser.parse_args()

def build_parser(settings: Dict[str, Any]) -> InstagramParser:
    return InstagramParser(
        base_url=settings.get("base_url", "https://www.instagram.com"),
        timeout=settings.get("request_timeout", 15),
        max_following=settings.get("max_following_per_user", 10000),
        user_agent=settings.get("user_agent"),
    )

def run() -> None:
    paths = resolve_paths()
    args = parse_args(paths)

    logger.info("Loading settings from %s", paths["settings_file"])
    settings = load_settings(paths["settings_file"])

    if args.max_following is not None:
        settings["max_following_per_user"] = args.max_following

    output_format = args.format or settings.get("default_output_format", "json")
    logger.info("Using output format: %s", output_format)

    input_path = Path(args.input).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    logger.info("Input file: %s", input_path)
    logger.info("Output file: %s", output_path)

    usernames = load_inputs(input_path)
    usernames = sanitize_usernames(usernames)
    if not usernames:
        logger.error("No valid usernames found in input file.")
        raise SystemExit(1)

    parser = build_parser(settings)
    exporter = Exporter(output_dir=output_path.parent)

    all_records: List[Dict[str, Any]] = []

    logger.info("Starting scrape for %d usernames", len(usernames))
    for username in usernames:
        try:
            logger.info("Fetching following list for user '%s'", username)
            profiles = parser.get_following(username=username)
            logger.info(
                "Fetched %d following profiles for '%s'", len(profiles), username
            )
            all_records.extend(profile.to_dict() for profile in profiles)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to fetch following for '%s': %s", username, exc)

    if not all_records:
        logger.warning("No records were fetched; nothing to export.")
        return

    logger.info("Total records fetched: %d", len(all_records))

    # Export as requested
    if output_format in ("json", "both"):
        exporter.export_json(all_records, output_path)

    if output_format in ("csv", "both"):
        csv_path = output_path.with_suffix(".csv")
        exporter.export_csv(all_records, csv_path)

    # Also create a compact summary file listing usernames and counts
    summary = {}
    for record in all_records:
        followed_by = record.get("followed_by")
        if not followed_by:
            continue
        summary.setdefault(followed_by, 0)
        summary[followed_by] += 1

    summary_path = output_path.with_name(output_path.stem + "_summary.json")
    try:
        with summary_path.open("w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        logger.info("Summary written to %s", summary_path)
    except OSError as exc:
        logger.error("Failed to write summary file: %s", exc)

    logger.info("Scraping complete.")

if __name__ == "__main__":
    run()