"""Pre-inference PII vault & regex/token redaction for zero-trust compliance.

The ZeroTrustSanitizer scans free-text payloads (DOM snapshots, user inputs,
BDD specs) for sensitive data patterns and replaces them with reversible
{{REDACTED_<TYPE>_<N>}} tokens *before* any payload leaves the local machine.

The original values are held in a local-only vault dict keyed by token.
The vault is NEVER serialized or sent over the network.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class RedactedToken:
    """Metadata about a single redaction replacement."""
    token: str          # e.g. "{{REDACTED_SSN_1}}"
    category: str       # e.g. "SSN"
    original_hash: str  # SHA-256 of the original value (NOT the raw value)


# ---------------------------------------------------------------------------
# ZeroTrustSanitizer
# ---------------------------------------------------------------------------

class ZeroTrustSanitizer:
    """Deterministic regex-based PII scrubber.

    Supported categories:
        SSN         — US Social Security Numbers  (XXX-XX-XXXX)
        SIN         — Canadian Social Insurance Numbers  (XXX XXX XXX)
        EMAIL       — Email addresses
        CREDIT_CARD — 16-digit card numbers with optional separators
        API_KEY     — Bearer / sk_ / pk_ / key_ / token_ style secrets
    """

    PATTERNS: dict[str, str] = {
        "SSN": r"\b\d{3}-\d{2}-\d{4}\b",
        "SIN": r"\b\d{3}\s\d{3}\s\d{3}\b",
        "EMAIL": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "CREDIT_CARD": r"\b(?:\d{4}[- ]?){3}\d{4}\b",
        "API_KEY": r"\b(?:sk|pk|key|token|bearer)[_-][A-Za-z0-9]{16,}\b",
    }

    def __init__(self) -> None:
        # token → original raw value  (local-only vault, never serialized)
        self._vault: dict[str, str] = {}
        # per-category running counter for unique token IDs
        self._counters: dict[str, int] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def sanitize(self, text: str) -> tuple[str, list[RedactedToken]]:
        """Replace all recognised PII in *text* with ``{{REDACTED_*}}`` tokens.

        Returns
        -------
        tuple[str, list[RedactedToken]]
            The sanitized text and the list of tokens that were inserted.
        """
        tokens: list[RedactedToken] = []

        for category, pattern in self.PATTERNS.items():
            compiled = re.compile(pattern, re.IGNORECASE)
            matches = list(compiled.finditer(text))

            for match in matches:
                original = match.group()
                # Increment counter for this category
                self._counters.setdefault(category, 0)
                self._counters[category] += 1
                count = self._counters[category]

                token_str = f"{{{{REDACTED_{category}_{count}}}}}"

                # Store in vault
                self._vault[token_str] = original

                # Build metadata (hash the original, never store raw externally)
                original_hash = hashlib.sha256(original.encode()).hexdigest()

                tokens.append(RedactedToken(
                    token=token_str,
                    category=category,
                    original_hash=original_hash,
                ))

                # Replace only this specific occurrence
                text = text[:match.start()] + token_str + text[match.end():]
                # Re-run finditer since offsets shifted — break and rescan
                break  # one replacement per rescan to keep offsets correct

            # Rescan for remaining matches in this category
            while True:
                compiled = re.compile(pattern, re.IGNORECASE)
                m = compiled.search(text)
                if m is None:
                    break

                original = m.group()
                self._counters[category] += 1
                count = self._counters[category]
                token_str = f"{{{{REDACTED_{category}_{count}}}}}"

                self._vault[token_str] = original
                original_hash = hashlib.sha256(original.encode()).hexdigest()
                tokens.append(RedactedToken(
                    token=token_str,
                    category=category,
                    original_hash=original_hash,
                ))
                text = text[:m.start()] + token_str + text[m.end():]

        return text, tokens

    def restore(self, text: str) -> str:
        """Replace ``{{REDACTED_*}}`` tokens back with original values from the vault."""
        for token_str, original in self._vault.items():
            text = text.replace(token_str, original)
        return text

    def reset(self) -> None:
        """Clear the vault and counters (e.g. between test runs)."""
        self._vault.clear()
        self._counters.clear()
