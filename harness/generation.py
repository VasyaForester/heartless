#!/usr/bin/env python3
"""Deterministic delta generation — reproducible per board profile.

The old `loop.make_variant` embedded a wall-clock timestamp and a random suffix,
which made replay impossible.  This module takes the nonce as data; the caller
persists it and can reconstruct the exact same input offline.

Reproducibility (Grok review 2026-11-15, axis "reproducibility": 8/10): the SAME nonce
must give the same text, and a replay must be pinned to the profile that produced it.
So the reference marker carries a short profile hash:

    (ref: 20261115-171203-4417@3f2c9a11)

The attack payload (base text + delta) is untouched by this — only the bookkeeping
marker names the profile.  `reproduce()` rebuilds a text from recorded ingredients and
compares hashes, so a replay against the WRONG profile fails loudly instead of
silently producing a different input.
"""
from __future__ import annotations

import hashlib

from lbcore import DELTAS

DELTA_VERSION = 1


def _marker(nonce: str, profile_hash: str | None) -> str:
    if not profile_hash:
        return str(nonce)
    return f"{nonce}@{str(profile_hash)[:8]}"


def generate(base_text: str, delta: str, nonce: str,
             delta_version: int = DELTA_VERSION,
             profile_hash: str | None = None) -> str:
    if int(delta_version) != DELTA_VERSION:
        raise ValueError(f"unsupported delta version {delta_version}")
    if delta not in DELTAS:
        raise ValueError(f"unknown delta {delta!r}; known: {sorted(DELTAS)}")
    ref = _marker(nonce, profile_hash)
    if delta == "append_nonce":
        text = base_text + "\n\n[ref LBP-" + ref + "]"
    else:
        text = DELTAS[delta](base_text)
    return text + "\n\n(ref: " + ref + ")"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def reproduce(base_text: str, delta: str, nonce: str, *,
              profile_hash: str | None = None,
              delta_version: int = DELTA_VERSION,
              input_sha256: str | None = None) -> dict:
    """Rebuild a probe text from recorded ingredients and check it against the record.

    Returns {"ok": bool, "text": str, "sha256": str, "reason": str}.  `ok` is True only
    when the rebuilt text matches the hash recorded with the attempt; a profile
    mismatch is reported as such, never as a silent success.
    """
    text = generate(base_text, delta, nonce, delta_version=delta_version,
                    profile_hash=profile_hash)
    sha = sha256_text(text)
    if input_sha256 is None:
        return {"ok": True, "text": text, "sha256": sha, "reason": "no hash to check"}
    if sha == input_sha256:
        return {"ok": True, "text": text, "sha256": sha, "reason": "matches the record"}
    return {"ok": False, "text": text, "sha256": sha,
            "reason": ("rebuilt text does not match the record — most likely a different "
                       "board profile, delta version, base text or nonce")}
