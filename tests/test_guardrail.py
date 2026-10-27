"""Tests for the Zero-Trust PII Guardrail and SHA-256 Audit Logger.

Validates that:
1. SSNs and emails are scrubbed into {{REDACTED_*}} tokens
2. Original PII values do NOT appear in sanitized output
3. The vault can restore original values
4. Audit entries are appended with valid SHA-256 hashes
5. The hash chain is tamper-evident and verifiable
"""

from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path

from src.guardrails.sanitizer import ZeroTrustSanitizer
from src.guardrails.audit_logger import ComplianceAuditLogger


class TestZeroTrustSanitizer:
    """Tests for the PII redaction engine."""

    def test_ssn_is_redacted(self) -> None:
        sanitizer = ZeroTrustSanitizer()
        text = "Customer SSN is 123-45-6789, please process."
        clean, tokens = sanitizer.sanitize(text)

        assert "123-45-6789" not in clean
        assert "{{REDACTED_SSN_1}}" in clean
        assert any(t.category == "SSN" for t in tokens)

    def test_email_is_redacted(self) -> None:
        sanitizer = ZeroTrustSanitizer()
        text = "Contact: john.doe@example.com for details."
        clean, tokens = sanitizer.sanitize(text)

        assert "john.doe@example.com" not in clean
        assert "{{REDACTED_EMAIL_1}}" in clean
        assert any(t.category == "EMAIL" for t in tokens)

    def test_multiple_pii_types_redacted(self) -> None:
        sanitizer = ZeroTrustSanitizer()
        text = "Customer John Doe, SSN 123-45-6789, email john@example.com"
        clean, tokens = sanitizer.sanitize(text)

        # Originals must be gone
        assert "123-45-6789" not in clean
        assert "john@example.com" not in clean

        # Tokens must be present
        assert "{{REDACTED_SSN_1}}" in clean
        assert "{{REDACTED_EMAIL_1}}" in clean

        # Should have at least 2 tokens
        assert len(tokens) >= 2

    def test_token_hashes_are_sha256(self) -> None:
        sanitizer = ZeroTrustSanitizer()
        _, tokens = sanitizer.sanitize("SSN: 999-88-7777")

        for token in tokens:
            assert re.match(r"^[a-f0-9]{64}$", token.original_hash), (
                f"Expected SHA-256 hex digest, got: {token.original_hash}"
            )

    def test_vault_restore(self) -> None:
        sanitizer = ZeroTrustSanitizer()
        original_text = "SSN is 111-22-3333"
        clean, _ = sanitizer.sanitize(original_text)

        assert "111-22-3333" not in clean
        restored = sanitizer.restore(clean)
        assert "111-22-3333" in restored

    def test_credit_card_redacted(self) -> None:
        sanitizer = ZeroTrustSanitizer()
        text = "Card: 4111-1111-1111-1111 on file."
        clean, tokens = sanitizer.sanitize(text)

        assert "4111-1111-1111-1111" not in clean
        assert any(t.category == "CREDIT_CARD" for t in tokens)


class TestComplianceAuditLogger:
    """Tests for the SHA-256 hash-chained audit ledger."""

    def test_log_creates_entry_with_valid_hash(self, tmp_path: Path) -> None:
        log_file = tmp_path / "audit_trail.jsonl"
        logger = ComplianceAuditLogger(log_path=str(log_file))

        entry = logger.log(
            event_type="pii_redaction",
            payload_summary="Scrubbed 1 SSN and 1 email",
            redacted_fields=["SSN", "EMAIL"],
        )

        assert entry.sequence_id == 1
        assert entry.event_type == "pii_redaction"
        assert re.match(r"^[a-f0-9]{64}$", entry.sha256_hash)
        assert entry.previous_hash == "0" * 64  # genesis

        # Verify file was written
        assert log_file.exists()
        lines = log_file.read_text().strip().split("\n")
        assert len(lines) == 1

        # Verify JSON is valid
        parsed = json.loads(lines[0])
        assert parsed["sha256_hash"] == entry.sha256_hash

    def test_hash_chain_links_entries(self, tmp_path: Path) -> None:
        log_file = tmp_path / "audit_trail.jsonl"
        logger = ComplianceAuditLogger(log_path=str(log_file))

        entry1 = logger.log("step_executed", "Step 1 passed")
        entry2 = logger.log("step_executed", "Step 2 passed")
        entry3 = logger.log("pii_redaction", "Scrubbed SSN", ["SSN"])

        # Chain linkage
        assert entry2.previous_hash == entry1.sha256_hash
        assert entry3.previous_hash == entry2.sha256_hash

        # Sequence monotonicity
        assert entry1.sequence_id == 1
        assert entry2.sequence_id == 2
        assert entry3.sequence_id == 3

    def test_verify_chain_passes(self, tmp_path: Path) -> None:
        log_file = tmp_path / "audit_trail.jsonl"
        logger = ComplianceAuditLogger(log_path=str(log_file))

        logger.log("test_start", "Beginning test run")
        logger.log("pii_redaction", "Scrubbed 2 fields", ["SSN", "EMAIL"])
        logger.log("test_end", "Test run complete")

        assert logger.verify_chain() is True

    def test_verify_chain_detects_tampering(self, tmp_path: Path) -> None:
        log_file = tmp_path / "audit_trail.jsonl"
        logger = ComplianceAuditLogger(log_path=str(log_file))

        logger.log("test_start", "Beginning test run")
        logger.log("test_end", "Test run complete")

        # Tamper with the file: replace a hash character
        content = log_file.read_text()
        lines = content.strip().split("\n")
        tampered = json.loads(lines[0])
        tampered["sha256_hash"] = "a" * 64  # corrupt the hash
        lines[0] = json.dumps(tampered)
        log_file.write_text("\n".join(lines) + "\n")

        # Re-instantiate and verify — should detect corruption
        logger2 = ComplianceAuditLogger(log_path=str(log_file))
        assert logger2.verify_chain() is False


class TestEndToEndGuardrail:
    """Integration test: sanitize → audit → verify."""

    def test_sanitize_and_audit(self, tmp_path: Path) -> None:
        sanitizer = ZeroTrustSanitizer()
        log_file = tmp_path / "audit_trail.jsonl"
        logger = ComplianceAuditLogger(log_path=str(log_file))

        # Sanitize a PII-laden string
        raw = "Customer John Doe, SSN 123-45-6789, email john@example.com"
        clean, tokens = sanitizer.sanitize(raw)

        # Log the redaction event
        entry = logger.log(
            event_type="pii_redaction",
            payload_summary=f"Scrubbed {len(tokens)} PII fields from input",
            redacted_fields=[t.category for t in tokens],
        )

        # Verify the output
        assert "123-45-6789" not in clean
        assert "john@example.com" not in clean
        assert entry.sequence_id == 1
        assert logger.verify_chain() is True

        # Verify the log file
        lines = log_file.read_text().strip().split("\n")
        assert len(lines) == 1
        parsed = json.loads(lines[0])
        assert "SSN" in parsed["redacted_fields"]
        assert "EMAIL" in parsed["redacted_fields"]
