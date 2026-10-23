import re
from typing import Dict, Any, List, Tuple

class ReplyValidator:
    """
    Implements the Code node validator specified in Section 10 & 17B:
    1. RERA number check in first reply or any message mentioning a price.
    2. Every ₹ amount must match the live price list within ₹1,000.
    3. Price list freshness check (<24h).
    4. Banned phrases check: guarantee, assured, 100%, offer ends, possession by.
    5. Length limit (max 120 words / 600 characters).
    """

    BANNED_PATTERNS = [
        re.compile(r"\bguarantee\b", re.IGNORECASE),
        re.compile(r"\bassured\b", re.IGNORECASE),
        re.compile(r"\b100%\b", re.IGNORECASE),
        re.compile(r"\boffer ends\b", re.IGNORECASE),
        re.compile(r"\bpossession by\b", re.IGNORECASE),
        re.compile(r"\bconfirmed possession\b", re.IGNORECASE),
        re.compile(r"\bcheapest\b", re.IGNORECASE)
    ]

    AMOUNT_REGEX = re.compile(r"₹\s*([\d,.]+)\s*(crore|cr|lakh|l)?", re.IGNORECASE)

    @classmethod
    def extract_amounts(cls, text: str) -> List[int]:
        amounts = []
        for match in cls.AMOUNT_REGEX.finditer(text):
            num_str = match.group(1).replace(",", "")
            unit = (match.group(2) or "").lower()
            try:
                num = float(num_str)
                if unit in ("crore", "cr"):
                    num *= 10_000_000
                elif unit in ("lakh", "l"):
                    num *= 100_000
                amounts.append(round(num))
            except ValueError:
                continue
        return amounts

    @classmethod
    def validate_reply(
        cls,
        reply: str,
        is_first_reply: bool,
        rera_number: str,
        allowed_prices: List[int],
        price_list_fresh: bool,
        max_words: int = 120
    ) -> Tuple[bool, List[str]]:
        reasons = []

        # 1. RERA Number Check
        has_amount = "₹" in reply or bool(cls.AMOUNT_REGEX.search(reply))
        if (is_first_reply or has_amount) and (rera_number not in reply):
            reasons.append(f"RERA registration number '{rera_number}' is missing from reply.")

        # 2. Amount and Freshness Check
        extracted_amounts = cls.extract_amounts(reply)
        if extracted_amounts:
            if not price_list_fresh:
                reasons.append("Price was quoted, but live price list is older than 24 hours (price quote halted).")
            for amt in extracted_amounts:
                # Within ₹1,000 tolerance of any live available price
                matches = any(abs(allowed - amt) <= 1000 for allowed in allowed_prices)
                if not matches:
                    reasons.append(f"Amount ₹{amt:,} does not match any live inventory unit.")

        # 3. Banned Phrases Check
        for pat in cls.BANNED_PATTERNS:
            if pat.search(reply):
                reasons.append(f"Contains prohibited commitment/marketing phrase matching '{pat.pattern}'.")

        # 4. Length Check
        words = reply.strip().split()
        if len(words) > max_words:
            reasons.append(f"Reply exceeds maximum length of {max_words} words (actual: {len(words)}).")

        is_valid = len(reasons) == 0
        return is_valid, reasons
