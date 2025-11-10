thonimport csv
import json
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List

logger = logging.getLogger(__name__)

class Exporter:
    """
    Simple exporter for JSON and CSV formats.
    """

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            logger.error("Failed to create output directory %s: %s", self.output_dir, exc)
            raise

    def export_json(self, records: Iterable[Dict[str, Any]], path: Path) -> None:
        """
        Write records to a JSON file with UTF-8 encoding.
        """
        records_list: List[Dict[str, Any]] = list(records)
        try:
            with path.open("w", encoding="utf-8") as f:
                json.dump(records_list, f, ensure_ascii=False, indent=2)
            logger.info("JSON output written to %s (%d records)", path, len(records_list))
        except OSError as exc:
            logger.error("Failed to write JSON output to %s: %s", path, exc)
            raise

    def export_csv(self, records: Iterable[Dict[str, Any]], path: Path) -> None:
        """
        Write records to a CSV file. The header is inferred from the union of keys.
        """
        records_list: List[Dict[str, Any]] = list(records)
        if not records_list:
            logger.warning("No records to export to CSV.")
            return

        # Infer header
        header_keys: List[str] = []
        for record in records_list:
            for key in record.keys():
                if key not in header_keys:
                    header_keys.append(key)

        try:
            with path.open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=header_keys)
                writer.writeheader()
                for record in records_list:
                    writer.writerow(record)
            logger.info("CSV output written to %s (%d records)", path, len(records_list))
        except OSError as exc:
            logger.error("Failed to write CSV output to %s: %s", path, exc)
            raise