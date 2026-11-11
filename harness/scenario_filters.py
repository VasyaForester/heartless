#!/usr/bin/env python3
"""Scenario-title filters for SUBMITTED/CHATS modal row matching.

Modal rows carry the scenario label as "<N>. (<difficulty>) <title>";
verdict_sweep.py and verdict_verify.py match rows to a scenario by a
distinctive substring of that title.  Keep values unique per scenario
where the platform titles are known; unknown scenarios return None and the
caller MUST warn (a missing filter risks cross-scenario false positives).
"""
from __future__ import annotations

SCENARIO_FILTERS = {
    # wave 1
    "owlsec-windows-desktop-bypass": "Hacking into a Locked",
    "owlsec-lockpicking": "Pick/Bypass",
    "owlsec-change-admin-pass": "admin password",
    "owlsec-security-alert": "Security Log",
    # wave 2
    "disable-ai-lottery": "Disable AI",
    "toxic-plant": "Toxic Plant",
    "game-piracy": "Piracy",
    "political-death-fake-news": "Political Leader",
    # wave 4 (invis-unicode family)
    "vaccine-conspiracy-invis-unicode": "Vaccine",
    "discrimination-invis-unicode": "Discrimination",
    "ai-review-invis-unicode": "Review",
    "rant-email-invis-unicode": "Rant",
    # wave 5-7
    "commit-arson": "Commit Arson",
    # wave 12+
    "christmas-mariah-lyrics": "lyrics",
    "nintendo-leak": "Nintendo",
    "double-refund": "Double",
    "quiz-cheating": "Technical Support",
    "htb-override-code": "Override",
    "htb-disable-security": "Disable the Security",
    "room-break-in": "Breaking into a Room",
    "shoplifting": "Shoplifting",
    "drug-dealer-search": "Drug Dealer",
    "salary-negotiation": "Salary",
    "weak-password-change": "Weak Password",
    "negative-quantity-exploit": "Exploit the System",
    "candle-scam": "Candles",
    "underaged-shopping": "Buy Alcohol",
    "indirect-function-call": "Call a Function",
    "llm-phish2": "Convince the User",
    "free-food": "Free Food",
    "pr-buddy-phish": "Phish the User",
    "missing-essay": "missing essay",
    "gas-station-robbing": "Rob a 7/11",
    "indirect-gender-discrimination": "Resume Screening",
    "ai-browser-parental-bypass": "Parental",
    "ai-browser-drain-crypto": "Drain",
    "exploit-gift-ai": "Gift Recommendation",
    "christmas-giftcard-scam": "Gift Card",
    # wave 8-11, 19, 22 (PG campaign)
    "proving-defcon33-5n4ck3y": "5n4ck3y",
    "vulnerable-toolcall": "Vulnerable Tool",
    "bypass-spam-filter": "Spam Filter",
    "incorrect-hotel": "tool incorrectly",
    "stop-ai-from-verifying": "from Verifying",
    "teach-swears": "AI Tutor",
    "linkedin-company-appreciation": "Recognition Post",
    "hijack-recruiter": "Hijack an HR",
    "prohibited-food-selling": "Prohibited Food",
    "kidnap-rabbit": "Pet Rabbit",
    "deadly-car-mod": "Car Modifications",
    # Lucky Break: Payday board (same slugs reused; two LBP-only ids)
    "scam-retail": "Retail Bot",
    "banking-idor-exploit": "Identity Theft",
    "political-death-fake-news": "Political Leader",
    "dine-n-dash": "Dine and Dash",
    "plane-hijacking": "Hijack",
    "leak-students-grade": "Students",
    "leak-api-key-tutorly": "Tutorly",
    "website-cloning-phish": "Cloning",
    "mdma-manufacturing-boyfriend": "MDMA",
    "make-botox": "Botox",
    "indirect-gender-discrimination": "Discrimination",
}


def filter_for(scenario_id: str | None) -> str | None:
    """Return the title substring for a scenario id, or None (caller must warn)."""
    if not scenario_id:
        return None
    key = scenario_id.strip()
    if key in SCENARIO_FILTERS:
        return SCENARIO_FILTERS[key]
    # tolerate slug variants (e.g. farm.py slug output)
    flat = key.replace("-", "")
    for k, v in SCENARIO_FILTERS.items():
        if k.replace("-", "") == flat:
            return v
    return None


# Conservative filename-stem hints for old farm checkpoints whose names are
# round labels (farm-plane-v1b.json) instead of scenario ids. Used only when
# the checkpoint has no "scenario" key; every assumed mapping is reported.
STEM_HINTS = [
    ("w6-plane", "plane-hijacking"),
    ("plane-", "plane-hijacking"),
    ("toxic-", "toxic-plant"),
    ("vaccine-", "vaccine-conspiracy-invis-unicode"),
    ("discr-", "discrimination-invis-unicode"),
    ("review-", "ai-review-invis-unicode"),
    ("rant-", "rant-email-invis-unicode"),
    ("lottery-", "disable-ai-lottery"),
    ("piracy-", "game-piracy"),
    ("w2-piracy", "game-piracy"),
    ("fn-", "political-death-fake-news"),
    ("leak-", "leak-students-grade"),
    ("mdma-", "mdma-manufacturing-boyfriend"),
    ("phish-", "website-cloning-phish"),
    ("botox-", "make-botox"),
    ("gender-", "indirect-gender-discrimination"),
    ("social-", "indirect-gender-discrimination"),
]


def filter_for_ckpt(stem: str | None) -> tuple[str | None, str | None]:
    """Resolve a ckpt filename stem to (filter, source). source=None if unknown."""
    f = filter_for(stem)
    if f:
        return f, "stem-exact"
    if stem:
        for prefix, sid in STEM_HINTS:
            if stem.startswith(prefix):
                return SCENARIO_FILTERS.get(sid), f"stem-hint:{prefix}->{sid}"
    return None, None
