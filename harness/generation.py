#!/usr/bin/env python3
"""Deterministic delta generation.

The old `loop.make_variant` embedded a wall-clock timestamp and a random
suffix, which made replay impossible.  This module takes the nonce as data;
the caller persists it and can reconstruct the exact same input offline.
"""
from __future__ import annotations

from lbcore import DELTAS

DELTA_VERSION = 1


def generate(base_text: str, delta: str, nonce: str,
             delta_version: int = DELTA_VERSION) -> str:
    if int(delta_version) != DELTA_VERSION:
        raise ValueError(f"unsupported delta version {delta_version}")
    if delta not in DELTAS:
        raise ValueError(f"unknown delta {delta!r}; known: {sorted(DELTAS)}")
    if delta == "append_nonce":
        text = base_text + "\n\n[ref LBP-" + str(nonce) + "]"
    else:
        text = DELTAS[delta](base_text)
    return text + "\n\n(ref: " + str(nonce) + ")"