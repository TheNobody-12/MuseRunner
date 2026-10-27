"""SHA-256 hash-chained compliance logger for tamper-evident audit trails.

Every event is appended as a JSON line to ``audit_trail.jsonl``.  Each
entry includes its own SHA-256 digest *and* the digest of the previous
entry, forming a tamper-evident chain that can be verified offline by
replaying the file from the genesis entry.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from src.core.schemas import AuditEntry


class ComplianceAuditLogger:
    """Append-only, hash-chained JSONL audit logger."""

    GENESIS_HASH: str = "0" * 64

    def __init__(self, log_path: str = "audit_trail.jsonl") -> None:
        self._path = Path(log_path)
        self._sequence: int = 0
        self._previous_hash: str = self.GENESIS_HASH

        # If the file already exists, resume from the last entry
        if self._path.exists():
            self._resume_from_existing()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def log(
        self,
        event_type: str,
        payload_summary: str,
        redacted_fields: list[str] | None = None,
    ) -> AuditEntry:
        """Append a hash-chained audit entry and return it."""
        self._sequence += 1

        timestamp = datetime.now(timezone.utc).isoformat()
        redacted = redacted_fields or []

        # Build the hash input: sequence + timestamp + event + payload + prev hash
        hash_input = (
            f"{self._sequence}|{timestamp}|{event_type}|"
            f"{payload_summary}|{','.join(redacted)}|{self._previous_hash}"
        )
        sha256_hash = hashlib.sha256(hash_input.encode()).hexdigest()

        entry = AuditEntry(
            sequence_id=self._sequence,
            timestamp=timestamp,
            event_type=event_type,
            payload_summary=payload_summary,
            redacted_fields=redacted,
            sha256_hash=sha256_hash,
            previous_hash=self._previous_hash,
        )

        # Append to JSONL
        with self._path.open("a", encoding="utf-8") as f:
            f.write(entry.model_dump_json() + "\n")

        # Advance the chain
        self._previous_hash = sha256_hash

        return entry

    def verify_chain(self) -> bool:
        """Read the log file and verify the full hash chain is intact.

        Returns True if the chain is valid, False if any entry is tampered.
        """
        if not self._path.exists():
            return True  # empty chain is trivially valid

        previous_hash = self.GENESIS_HASH

        with self._path.open("r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue

                entry = AuditEntry.model_validate_json(line)

                if entry.previous_hash != previous_hash:
                    return False

                # Recompute hash
                hash_input = (
                    f"{entry.sequence_id}|{entry.timestamp}|{entry.event_type}|"
                    f"{entry.payload_summary}|{','.join(entry.redacted_fields)}|"
                    f"{entry.previous_hash}"
                )
                expected = hashlib.sha256(hash_input.encode()).hexdigest()

                if entry.sha256_hash != expected:
                    return False

                previous_hash = entry.sha256_hash

        return True

    def read_entries(self) -> list[AuditEntry]:
        """Read and parse all audit entries from the log file."""
        if not self._path.exists():
            return []
        entries: list[AuditEntry] = []
        with self._path.open("r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped:
                    entries.append(AuditEntry.model_validate_json(stripped))
        return entries

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _resume_from_existing(self) -> None:
        """Read the last line of an existing log to resume the chain."""
        last_line: str = ""
        with self._path.open("r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped:
                    last_line = stripped

        if last_line:
            entry = AuditEntry.model_validate_json(last_line)
            self._sequence = entry.sequence_id
            self._previous_hash = entry.sha256_hash
