from __future__ import annotations

import copy
import math
import re
from dataclasses import dataclass, field


CONSTRAINT_KEYS = (
    "category",
    "material",
    "color",
    "size",
    "style",
    "brand",
    "budget",
    "feature",
    "use_case",
)
ALLOWED_ATTRIBUTES = frozenset((*CONSTRAINT_KEYS, "other"))

QUESTION_ORDER = (
    "category",
    "material",
    "feature",
    "color",
    "style",
    "size",
    "use_case",
    "other",
    "budget",
    "brand",
)

QUESTION_MESSAGES = {
    "category": "What type of product are you looking for?",
    "material": "Do you have a material preference?",
    "color": "Do you have a color preference?",
    "size": "What size or fit do you need?",
    "style": "What style do you prefer?",
    "brand": "Do you have a preferred brand?",
    "budget": "What budget should I stay within?",
    "feature": "Which product feature matters most to you?",
    "use_case": "What will you mainly use the product for?",
    "other": "Is there another requirement that matters to you?",
}

PROFILE_QUESTION_PREFERENCES = {
    "material": "material",
    "fit": "size",
    "comfort": "feature",
    "durability": "feature",
    "performance": "feature",
    "weather": "use_case",
    "warmth": "use_case",
    "style": "style",
}

INFORMATION_VALUE_WEIGHTS = {
    "category": 4.0,
    "material": 4.0,
    "feature": 2.5,
    "color": 2.0,
    "style": 1.2,
    "size": 1.0,
    "use_case": 1.0,
    "brand": 0.6,
    "budget": 0.4,
}

MATERIALS = (
    "stainless steel",
    "polyester",
    "leather",
    "spandex",
    "acrylic",
    "cotton",
    "nylon",
    "wool",
    "silk",
    "rayon",
    "fabric",
    "alloy",
    "denim",
    "suede",
    "canvas",
    "rubber",
    "fleece",
    "velvet",
    "linen",
    "modal",
)
COLORS = (
    "rose gold",
    "black",
    "white",
    "blue",
    "red",
    "pink",
    "green",
    "brown",
    "gray",
    "grey",
    "purple",
    "yellow",
    "orange",
    "gold",
    "silver",
    "beige",
    "navy",
)
CATEGORY_WORDS = (
    "accessories",
    "activewear",
    "backpacks",
    "bodysuits",
    "bracelets",
    "cardigans",
    "earrings",
    "flip flops",
    "handbags",
    "jumpsuits",
    "necklaces",
    "sneakers",
    "sweatshirts",
    "swimsuits",
    "underwear",
    "wallets",
    "watches",
    "backpack",
    "bodysuit",
    "bracelet",
    "cardigan",
    "earring",
    "handbag",
    "jumpsuit",
    "necklace",
    "sneaker",
    "sweatshirt",
    "swimsuit",
    "wallet",
    "watch",
    "leggings",
    "sandals",
    "dresses",
    "jackets",
    "hoodies",
    "blouses",
    "sweaters",
    "shorts",
    "skirts",
    "shirts",
    "shoes",
    "boots",
    "belts",
    "purses",
    "jewelry",
    "gloves",
    "pants",
    "socks",
    "suits",
    "tops",
    "dress",
    "jacket",
    "hoodie",
    "blouse",
    "sweater",
    "skirt",
    "shirt",
    "belt",
    "purse",
    "glove",
    "suit",
    "coat",
    "hat",
    "ring",
    "bra",
)
STYLES = (
    "business casual",
    "formal",
    "casual",
    "vintage",
    "classic",
    "modern",
    "sporty",
    "slim fit",
    "relaxed fit",
    "oversized",
    "minimalist",
)
USE_CASES = (
    "basketball",
    "running",
    "hiking",
    "walking",
    "workout",
    "work",
    "gym",
    "winter",
    "outdoor",
    "travel",
    "wedding",
    "swimming",
)


def _alternatives(values: tuple[str, ...]) -> str:
    return "|".join(re.escape(value) for value in sorted(values, key=len, reverse=True))


MATERIAL_RE = re.compile(rf"\b({_alternatives(MATERIALS)})\b", re.IGNORECASE)
COLOR_RE = re.compile(rf"\b({_alternatives(COLORS)})\b", re.IGNORECASE)
CATEGORY_RE = re.compile(rf"\b({_alternatives(CATEGORY_WORDS)})\b", re.IGNORECASE)
STYLE_RE = re.compile(rf"\b({_alternatives(STYLES)})\b", re.IGNORECASE)
USE_CASE_RE = re.compile(rf"\b({_alternatives(USE_CASES)})\b", re.IGNORECASE)

REVEALED_VALUE_RE = re.compile(
    r"\bfor that,\s*what matters is:\s*(.+?)(?:\.\s*)?$",
    re.IGNORECASE,
)
DISCLOSED_REQUIREMENT_RE = re.compile(
    r"\b(?:a key requirement is|what i need is):\s*(.+?)(?:\.\s*)?$",
    re.IGNORECASE,
)
NO_PREFERENCE_RE = re.compile(
    r"\b(?:do not|don't) have (?:an? |any |an additional )?preference for\s+([a-z_]+)",
    re.IGNORECASE,
)
BRAND_RE = re.compile(
    r"\bbrand\s*(?:is|:)?\s*([a-z0-9][a-z0-9 &'’-]{1,50})",
    re.IGNORECASE,
)
SIZE_RE = re.compile(
    r"\bsize\s*(?:is|:)?\s*([a-z0-9][a-z0-9./-]{0,12})",
    re.IGNORECASE,
)
BUDGET_RE = re.compile(
    r"\b(?:budget(?:\s+(?:is|of|around))?|under|below|less than|up to|max(?:imum)?)"
    r"\s*\$?\s*(?P<amount>\d+(?:\.\d{1,2})?)"
    r"(?!\s*(?:-|–)?\s*(?:inches?|in\b|centimeters?|cm\b|millimeters?|mm\b|"
    r"ounces?|oz\b|pounds?|lbs?\b|percent|%|wrist|size\b))",
    re.IGNORECASE,
)
LABELED_VALUE_RE = re.compile(
    r"\b(category|material|colou?r|size|style|brand|budget|feature|use[_ ]?case)\b"
    r"\s*(?:is|:)\s*([^.;]+)",
    re.IGNORECASE,
)
LOOKING_FOR_RE = re.compile(
    r"\b(?:looking|shopping) for\s+(?:an?\s+|some\s+)?(.+?)(?=[.;]|,\s*but\b|$)",
    re.IGNORECASE,
)
DIRECT_REQUEST_RE = re.compile(
    r"\b(?:i\s+)?(?:need|want)\s+(?:an?\s+|some\s+)?(.+?)(?=[.;]|$)",
    re.IGNORECASE,
)
OVERRIDE_RE = re.compile(
    r"\b(?:actually|instead|ignore|rather|changed my mind|no longer)\b",
    re.IGNORECASE,
)
BLANKET_OVERRIDE_RE = re.compile(
    r"\b(?:ignore|forget) (?:my )?(?:earlier|previous|old) preference",
    re.IGNORECASE,
)
NEGATED_VALUE_RE = re.compile(
    r"\b(?:not|without|avoid|anything except)\s+(.+?)"
    r"(?=[.;]|,?\s+(?:but|instead|rather)\b|$)",
    re.IGNORECASE,
)
REQUEST_ATTRIBUTE_RE = re.compile(
    r"\bask me about (?:one |a )?specific attribute\b",
    re.IGNORECASE,
)
REQUIRED_INTENT_RE = re.compile(r"\b(?:need|must|require)\b", re.IGNORECASE)
DIALOGUE_ONLY_RE = re.compile(
    r"\b(?:show me more options|those options are not quite right yet|"
    r"ask me about one specific attribute|please use your judgment|"
    r"i don't have (?:an additional |a )?preference for [a-z_]+)\b",
    re.IGNORECASE,
)


ConstraintValue = str | float | None


@dataclass(frozen=True, slots=True)
class ConstraintEvidence:
    value: str | float
    source_turn: int
    source_message: str
    source_kind: str


def empty_constraints() -> dict[str, ConstraintValue]:
    return {key: None for key in CONSTRAINT_KEYS}


def empty_evidence() -> dict[str, list[ConstraintEvidence]]:
    return {key: [] for key in CONSTRAINT_KEYS}


def empty_exclusions() -> dict[str, set[str]]:
    return {key: set() for key in CONSTRAINT_KEYS}


@dataclass
class SessionState:
    user_profile: dict
    constraints: dict[str, ConstraintValue] = field(default_factory=empty_constraints)
    constraint_evidence: dict[str, list[ConstraintEvidence]] = field(
        default_factory=empty_evidence
    )
    excluded_constraints: dict[str, set[str]] = field(default_factory=empty_exclusions)
    history: list[dict[str, object]] = field(default_factory=list)
    last_asked_attribute: str | None = None
    asked_attributes: set[str] = field(default_factory=set)
    no_preference_attributes: set[str] = field(default_factory=set)
    consecutive_no_preference: int = 0
    other_questions_asked: int = 0
    override_seen: bool = False
    last_search_diagnostics: dict[str, object] = field(default_factory=dict)
    category_context: str | None = None
    initial_preference_clues: set[str] = field(default_factory=set)

    @classmethod
    def create(cls, user_profile: dict) -> SessionState:
        return cls(user_profile=copy.deepcopy(user_profile))

    def search_text(self) -> str:
        values: list[str] = []
        seen: set[str] = set()
        for key in CONSTRAINT_KEYS:
            value = self.constraints[key]
            if value is None:
                continue
            text = str(value).strip()
            lowered = text.casefold()
            if text and lowered not in seen:
                seen.add(lowered)
                values.append(text)
        return " ".join(values)

    def constraint_priorities(self) -> dict[str, str]:
        """Classify current constraints for retrieval without changing state."""
        priorities: dict[str, str] = {}
        for attribute, evidence in self.constraint_evidence.items():
            if not evidence:
                continue
            latest = evidence[-1]
            if attribute in {"category", "budget"} or latest.source_kind in {
                "override",
                "disclosed",
                "clarification",
                "required",
            }:
                priorities[attribute] = "required"
            else:
                priorities[attribute] = "preferred"
        return priorities

    def retrieval_query(self) -> str:
        parts = [self.category_context or "", self.search_text()]
        return " ".join(dict.fromkeys(part.strip() for part in parts if part.strip()))

    def semantic_query(self) -> str:
        """Describe validated session constraints without conversational filler."""
        parts: list[str] = []
        category_context = (self.category_context or "").strip()
        if category_context:
            parts.append(f"category: {category_context}")
        for attribute in CONSTRAINT_KEYS:
            value = self.constraints[attribute]
            if value is None:
                continue
            text = str(value).strip()
            if not text:
                continue
            entry = f"{attribute.replace('_', ' ')}: {text}"
            if entry not in parts:
                parts.append(entry)
        return "; ".join(parts)

    def retrieval_query_for(self, message: str) -> str:
        stable = self.retrieval_query()
        useful_message = DIALOGUE_ONLY_RE.sub(" ", message)
        useful_message = re.sub(r"\s+", " ", useful_message).strip(" .,;:")
        if not useful_message:
            return stable
        parts = [self.category_context or "", useful_message, self.search_text()]
        return " ".join(dict.fromkeys(part.strip() for part in parts if part.strip()))


def _clean_value(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" \t\r\n.,;:-").lower()


def _last_match(pattern: re.Pattern[str], message: str) -> str | None:
    matches = list(pattern.finditer(message))
    return _clean_value(matches[-1].group(1)) if matches else None


def _category_from_message(message: str) -> str | None:
    looking_matches = list(LOOKING_FOR_RE.finditer(message))
    direct_matches = list(DIRECT_REQUEST_RE.finditer(message))
    request_segments = [match.group(1) for match in (*looking_matches, *direct_matches)]
    for segment in reversed(request_segments):
        category = _last_match(CATEGORY_RE, segment)
        if category:
            return category

    if not looking_matches:
        return None
    candidate = _clean_value(looking_matches[-1].group(1))
    if candidate in {"something", "something to wear", "anything", "clothing item"}:
        return None
    words = candidate.split()
    return candidate if 0 < len(words) <= 12 else None


def _category_context_from_message(message: str) -> str | None:
    matches = [*LOOKING_FOR_RE.finditer(message), *DIRECT_REQUEST_RE.finditer(message)]
    if not matches:
        return None
    candidate = _clean_value(matches[-1].group(1))
    if candidate in {"something", "something to wear", "anything", "clothing item"}:
        return None
    if _last_match(CATEGORY_RE, candidate) is None:
        return None
    return candidate if 0 < len(candidate.split()) <= 18 else None


def _initial_preference_clues(message: str) -> set[str]:
    matches = [*LOOKING_FOR_RE.finditer(message), *DIRECT_REQUEST_RE.finditer(message)]
    if not matches:
        return set()
    remainder = message[matches[-1].end() :].strip(" .,;:")
    if not remainder:
        return set()
    return {
        _clean_value(clause)
        for clause in re.split(r"[.;]", remainder)
        if _clean_value(clause)
    }


def _budget_from_message(message: str) -> float | None:
    matches = list(BUDGET_RE.finditer(message))
    return float(matches[-1].group("amount")) if matches else None


def _merge_update(
    updates: dict[str, ConstraintValue],
    attribute: str,
    value: str | float,
) -> None:
    current = updates.get(attribute)
    if current is None or attribute not in {"material", "feature", "use_case"}:
        updates[attribute] = value
        return

    current_text = str(current).strip()
    value_text = str(value).strip()
    if not value_text or value_text.casefold() in current_text.casefold():
        return
    updates[attribute] = f"{current_text}; {value_text}"


def _labeled_updates(message: str) -> dict[str, ConstraintValue]:
    updates: dict[str, ConstraintValue] = {}
    for match in LABELED_VALUE_RE.finditer(message):
        key = match.group(1).lower().replace("colour", "color").replace(" ", "_")
        value = _clean_value(match.group(2))
        if key == "budget":
            budget = _budget_from_message(match.group(0))
            if budget is not None:
                updates[key] = budget
        elif key in CONSTRAINT_KEYS and value:
            updates[key] = value
    return updates


def _classify_value(value: str) -> str:
    if _budget_from_message(value) is not None:
        return "budget"
    if re.search(r"\brubber sole\b", value, re.IGNORECASE):
        return "feature"
    if MATERIAL_RE.search(value):
        return "material"
    if COLOR_RE.search(value):
        return "color"
    if SIZE_RE.search(value):
        return "size"
    if STYLE_RE.search(value):
        return "style"
    if USE_CASE_RE.search(value):
        return "use_case"
    if BRAND_RE.search(value):
        return "brand"
    return "feature"


def _revealed_updates(value: str, asked_attribute: str | None) -> dict[str, str]:
    if asked_attribute in CONSTRAINT_KEYS:
        return {asked_attribute: value}

    updates: dict[str, ConstraintValue] = {}
    clauses = [_clean_value(clause) for clause in value.split(";")]
    for clause in clauses:
        if not clause:
            continue
        _merge_update(updates, _classify_value(clause), clause)
    return {key: str(item) for key, item in updates.items() if item is not None}


def extract_constraints(state: SessionState, message: str) -> dict[str, ConstraintValue]:
    updates = _labeled_updates(message)

    revealed = REVEALED_VALUE_RE.search(message)
    if revealed:
        value = _clean_value(revealed.group(1))
        if value:
            for attribute, revealed_value in _revealed_updates(
                value,
                state.last_asked_attribute,
            ).items():
                _merge_update(updates, attribute, revealed_value)

    disclosed = DISCLOSED_REQUIREMENT_RE.search(message)
    if disclosed:
        value = _clean_value(disclosed.group(1))
        if value:
            updates.setdefault(_classify_value(value), value)

    direct_values = {
        "category": _category_from_message(message),
        "material": _last_match(MATERIAL_RE, message),
        "color": _last_match(COLOR_RE, message),
        "style": _last_match(STYLE_RE, message),
        "use_case": _last_match(USE_CASE_RE, message),
    }
    for key, value in direct_values.items():
        if value and key not in updates:
            updates[key] = value

    size_matches = list(SIZE_RE.finditer(message))
    if size_matches and "size" not in updates:
        updates["size"] = _clean_value(size_matches[-1].group(1))

    brand_matches = list(BRAND_RE.finditer(message))
    if brand_matches and "brand" not in updates:
        updates["brand"] = _clean_value(brand_matches[-1].group(1))

    budget = _budget_from_message(message)
    if budget is not None and "budget" not in updates:
        updates["budget"] = budget

    return updates


def _refresh_constraint(state: SessionState, attribute: str) -> None:
    evidence = state.constraint_evidence[attribute]
    if not evidence:
        state.constraints[attribute] = None
        return

    if attribute not in {"material", "feature", "use_case"}:
        state.constraints[attribute] = evidence[-1].value
        return

    values: list[str] = []
    seen: set[str] = set()
    for item in evidence:
        text = str(item.value).strip()
        normalized = text.casefold()
        if text and normalized not in seen:
            seen.add(normalized)
            values.append(text)
    state.constraints[attribute] = "; ".join(values) if values else None


def _clear_attribute(state: SessionState, attribute: str) -> None:
    state.constraint_evidence[attribute].clear()
    state.constraints[attribute] = None


def _remove_matching_evidence(
    state: SessionState,
    attribute: str,
    value: str,
) -> bool:
    normalized = value.strip().casefold()
    if not normalized:
        return False
    retained = [
        item
        for item in state.constraint_evidence[attribute]
        if normalized not in str(item.value).strip().casefold()
    ]
    if len(retained) == len(state.constraint_evidence[attribute]):
        return False
    state.constraint_evidence[attribute] = retained
    _refresh_constraint(state, attribute)
    return True


def _record_constraint(
    state: SessionState,
    attribute: str,
    value: str | float,
    source_turn: int,
    source_message: str,
    source_kind: str,
    replace: bool,
) -> None:
    if attribute == "budget" and isinstance(value, str):
        parsed_budget = _budget_from_message(value)
        if parsed_budget is not None:
            value = parsed_budget

    evidence = state.constraint_evidence[attribute]
    if replace:
        evidence.clear()

    values = (
        [_clean_value(clause) for clause in str(value).split(";") if _clean_value(clause)]
        if attribute == "feature" and isinstance(value, str)
        else [value]
    )
    for item_value in values:
        normalized = str(item_value).strip().casefold()
        already_recorded_this_turn = any(
            str(item.value).strip().casefold() == normalized
            and item.source_turn == source_turn
            for item in evidence
        )
        if not already_recorded_this_turn:
            evidence.append(
                ConstraintEvidence(
                    value=item_value,
                    source_turn=source_turn,
                    source_message=source_message,
                    source_kind=source_kind,
                )
            )
        state.excluded_constraints[attribute].discard(normalized)
    state.no_preference_attributes.discard(attribute)
    _refresh_constraint(state, attribute)


def _source_kind(
    message: str,
    attribute: str,
    source_turn: int,
    is_override: bool,
) -> str:
    if is_override:
        return "override"
    if REVEALED_VALUE_RE.search(message):
        return "clarification"
    if DISCLOSED_REQUIREMENT_RE.search(message):
        return "disclosed"
    if REQUIRED_INTENT_RE.search(message):
        return "required"
    if source_turn == 1 and attribute != "category":
        return "initial_preference"
    return "direct"


def _is_initial_preference(
    state: SessionState,
    value: str | float,
    source_turn: int,
) -> bool:
    if source_turn != 1:
        return False
    normalized = str(value).strip().casefold()
    return any(
        normalized in clue or clue in normalized
        for clue in state.initial_preference_clues
    )


def _mark_no_preference(state: SessionState, message: str) -> bool:
    match = NO_PREFERENCE_RE.search(message)
    if not match:
        return False
    attribute = match.group(1).lower()
    if attribute not in ALLOWED_ATTRIBUTES:
        attribute = state.last_asked_attribute or "other"
    state.no_preference_attributes.add(attribute)
    state.consecutive_no_preference += 1
    if attribute in CONSTRAINT_KEYS:
        _clear_attribute(state, attribute)
    return True


def _clear_overridden_values(state: SessionState, message: str) -> set[str]:
    cleared_attributes: set[str] = set()
    if BLANKET_OVERRIDE_RE.search(message):
        for key in CONSTRAINT_KEYS:
            if key == "category":
                continue
            retained = [
                item
                for item in state.constraint_evidence[key]
                if item.source_kind != "initial_preference"
                and not any(
                    clue in str(item.value).casefold()
                    or str(item.value).casefold() in clue
                    for clue in state.initial_preference_clues
                )
            ]
            if len(retained) != len(state.constraint_evidence[key]):
                state.constraint_evidence[key] = retained
                _refresh_constraint(state, key)
                cleared_attributes.add(key)

    lowered = message.lower()
    for key in CONSTRAINT_KEYS:
        for item in list(state.constraint_evidence[key]):
            value = str(item.value).strip().casefold()
            escaped = re.escape(value)
            if re.search(rf"\b(?:not|without|ignore)\b[^.;]*\b{escaped}\b", lowered):
                state.excluded_constraints[key].add(value)
                if _remove_matching_evidence(state, key, value):
                    cleared_attributes.add(key)

    for match in NEGATED_VALUE_RE.finditer(message):
        value = _clean_value(match.group(1))
        if not value or value in {"my earlier preference", "my previous preference"}:
            continue
        attribute = _classify_value(value)
        state.excluded_constraints[attribute].add(value)
        _remove_matching_evidence(state, attribute, value)
        cleared_attributes.add(attribute)

    return cleared_attributes


def _clear_for_category_change(state: SessionState) -> set[str]:
    cleared_attributes: set[str] = set()
    for attribute in CONSTRAINT_KEYS:
        if attribute == "category":
            continue
        if state.constraints[attribute] is not None:
            _clear_attribute(state, attribute)
            cleared_attributes.add(attribute)
    return cleared_attributes


def _reopen_cleared_questions(
    state: SessionState,
    cleared_attributes: set[str],
) -> None:
    for attribute in cleared_attributes:
        if state.constraints[attribute] is not None:
            continue
        state.asked_attributes.discard(attribute)
        state.no_preference_attributes.discard(attribute)


def update_state(state: SessionState, message: str) -> bool:
    """Apply deterministic parsing and report whether the message changed state."""
    source_turn = 1 + sum(item["role"] == "user" for item in state.history)
    state.history.append({"role": "user", "message": message})
    category_context = _category_context_from_message(message)
    if category_context:
        state.category_context = category_context
    if source_turn == 1:
        state.initial_preference_clues = _initial_preference_clues(message)
    if _mark_no_preference(state, message):
        return True

    is_override = OVERRIDE_RE.search(message) is not None
    updates = extract_constraints(state, message)
    if updates:
        state.consecutive_no_preference = 0
    cleared_attributes: set[str] = set()
    if is_override or NEGATED_VALUE_RE.search(message):
        if is_override:
            state.override_seen = True
        previous_category = state.constraints["category"]
        cleared_attributes.update(_clear_overridden_values(state, message))
        new_category = updates.get("category")
        if (
            is_override
            and previous_category is not None
            and new_category is not None
            and str(previous_category).casefold() != str(new_category).casefold()
        ):
            cleared_attributes.update(_clear_for_category_change(state))

    for key, value in updates.items():
        if value is None:
            continue
        if any(
            excluded_value in str(value).casefold()
            for excluded_value in state.excluded_constraints[key]
        ):
            continue
        source_kind = _source_kind(message, key, source_turn, is_override)
        if source_kind == "direct" and _is_initial_preference(
            state, value, source_turn
        ):
            source_kind = "initial_preference"
        _record_constraint(
            state=state,
            attribute=key,
            value=value,
            source_turn=source_turn,
            source_message=message,
            source_kind=source_kind,
            replace=(
                key in cleared_attributes
                or key not in {"material", "feature", "use_case"}
            ),
        )

    _reopen_cleared_questions(state, cleared_attributes)
    return (
        bool(updates)
        or is_override
        or REQUEST_ATTRIBUTE_RE.search(message) is not None
    )


def _candidate_information_value(stats: dict[str, int]) -> float:
    total = sum(stats.values())
    if total <= 1 or len(stats) <= 1:
        return 0.0
    entropy = -sum(
        (count / total) * math.log2(count / total)
        for count in stats.values()
        if count > 0
    )
    return entropy / math.log2(len(stats))


def choose_clarification(
    state: SessionState,
    turn: int,
    candidate_statistics: dict[str, dict[str, int]] | None = None,
) -> str | None:
    if turn >= 10:
        return None

    if (
        state.constraints["category"] is None
        and "category" not in state.asked_attributes
        and "category" not in state.no_preference_attributes
    ):
        return "category"

    other_is_available = "other" not in state.no_preference_attributes
    no_preference_limit = 1 if state.override_seen else 2
    if (
        state.consecutive_no_preference >= no_preference_limit
        and state.other_questions_asked < 2
        and other_is_available
    ):
        return "other"

    unresolved = [
        attribute
        for attribute in QUESTION_ORDER
        if attribute != "other"
        and attribute not in state.asked_attributes
        and attribute not in state.no_preference_attributes
        and state.constraints[attribute] is None
    ]
    if candidate_statistics:
        scored = [
            (
                _candidate_information_value(candidate_statistics.get(attribute, {}))
                * INFORMATION_VALUE_WEIGHTS.get(attribute, 1.0),
                -QUESTION_ORDER.index(attribute),
                attribute,
            )
            for attribute in unresolved
        ]
        best_score, _, best_attribute = max(scored, default=(0.0, 0, ""))
        if best_score >= 0.35:
            return best_attribute

    profile_attributes = [
        PROFILE_QUESTION_PREFERENCES.get(str(tag).casefold())
        for tag in state.user_profile.get("preference_tags", [])
    ]
    for attribute in profile_attributes:
        if attribute in unresolved:
            return attribute

    for attribute in QUESTION_ORDER:
        if attribute == "other":
            if state.other_questions_asked < 2 and other_is_available:
                return "other"
            continue
        already_resolved = (
            attribute in state.asked_attributes
            or attribute in state.no_preference_attributes
        )
        if already_resolved:
            continue
        if state.constraints[attribute] is None:
            return attribute

    latest_user_message = next(
        (
            str(item.get("message", ""))
            for item in reversed(state.history)
            if item.get("role") == "user"
        ),
        "",
    )
    if REQUEST_ATTRIBUTE_RE.search(latest_user_message):
        return "other"
    return None


def response_message(ask_attribute: str | None) -> str:
    if ask_attribute is None:
        return "Here are the closest matches I found."
    return QUESTION_MESSAGES[ask_attribute]


def record_response(
    state: SessionState,
    message: str,
    ask_attribute: str | None,
    recommendations: list[dict[str, str]],
) -> None:
    state.last_asked_attribute = ask_attribute
    if ask_attribute is not None:
        state.asked_attributes.add(ask_attribute)
    if ask_attribute == "other":
        state.other_questions_asked += 1
    state.history.append(
        {
            "role": "assistant",
            "message": message,
            "ask_attribute": ask_attribute,
            "recommendations": [item["parent_asin"] for item in recommendations],
        }
    )
