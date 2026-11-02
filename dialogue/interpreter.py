"""Qwen interpretation and an explicit adapter for the existing NLU baseline."""
import difflib
import json
import re

from .prompts import messages
from .types import (InterpretationError, TraitUpdate, TurnInterpretation, Unresolved,
                    unique_json_pairs)

VALID_MODES = ("add", "remove", "replace")


def _user_names(key, message):
    """True when the user's own words contain the invented key (or a close typo)."""
    if not key.strip():
        return False
    low = message.casefold().replace("_", " ")
    if key.replace("_", " ") in low:
        return True
    words = [w for w in re.findall(r"[a-z]+", low) if len(w) >= 4]
    return any(difflib.SequenceMatcher(None, key, w).ratio() >= 0.8 for w in words)


def _salvage_unknown_traits(text, allowed, intensity_aliases, message=""):
    """Recover an interpretation whose trait_updates name non-catalogue keys.

    Two model behaviours produce this. A genuine unsupported trait ("I am strong"
    -> add strong) is kept as a clarification question, because silently dropping
    the trait the user just named loses their request. An invented trait for a
    message that names none ("roast me" -> add braggart) is dropped. The rest is
    re-validated; any other failure is left to the retry.
    """
    try:
        data = json.loads(text, object_pairs_hook=unique_json_pairs)
    except (ValueError, TypeError):
        return None
    if type(data) is not dict:
        return None
    updates = data.get("trait_updates")
    if type(updates) is not list:
        return None

    def wellformed(update):
        return (type(update) is dict and set(update) == {"mode", "traits"}
                and update.get("mode") in VALID_MODES and type(update.get("traits")) is list
                and all(type(t) is str for t in update["traits"]))

    kept, recovered, changed = [], [], False
    for update in updates:
        if wellformed(update) and all(t in allowed for t in update["traits"]):
            kept.append(update)
            continue
        changed = True
        if not wellformed(update):
            continue
        known = [t for t in update["traits"] if t in allowed]
        if known:
            kept.append({"mode": update["mode"], "traits": known})
        for t in update["traits"]:
            if t not in allowed and _user_names(t, message):
                recovered.append({"text": t, "candidates": [], "mode": update["mode"], "target": "traits"})
    if not changed:
        return None
    if recovered:
        existing = data.get("unresolved")
        shape_ok = (type(existing) is list
                    and all(type(u) is dict and set(u) == {"text", "candidates", "mode", "target"}
                            and u["mode"] in VALID_MODES for u in existing))
        if not shape_ok:
            return None  # cannot merge without inventing fields; let the corrected retry try
        data["unresolved"] = existing + recovered
    data["trait_updates"] = kept
    try:
        return TurnInterpretation.from_dict(data, allowed, intensity_aliases)
    except InterpretationError:
        return None


class QwenInterpreter:
    def __init__(self, service, catalogue, retries=1, max_input_tokens=4096, max_new_tokens=384,
                 intensity_aliases=None):
        if not 0 <= retries <= 2:
            raise ValueError("Interpretation retries must be between 0 and 2")
        self.service, self.catalogue = service, catalogue
        self.retries, self.max_input_tokens, self.max_new_tokens = retries, max_input_tokens, max_new_tokens
        self.intensity_aliases = intensity_aliases
        self.last_attempts = 0
        self.last_salvaged = False

    def interpret(self, message, state):
        self.last_attempts = 0
        self.last_salvaged = False
        for attempt in range(self.retries + 1):
            self.last_attempts += 1
            text = self.service.interpret(messages(message, state, self.catalogue, retry=attempt > 0),
                                          self.max_input_tokens, self.max_new_tokens)
            try:
                return TurnInterpretation.from_json(text, self.catalogue.keys, self.intensity_aliases)
            except InterpretationError:
                salvaged = _salvage_unknown_traits(text, self.catalogue.keys, self.intensity_aliases, message)
                if salvaged is not None:
                    self.last_salvaged = True
                    return salvaged
                if attempt == self.retries:
                    raise


class NLUInterpreter:
    """Baseline: existing seven intents, normalized into the same policy contract.

    Add/remove/replace and negation are not inferred here: evaluate those gaps explicitly.
    """

    def __init__(self, nlu, catalogue):
        self.nlu, self.catalogue = nlu, catalogue
        self.last_attempts = 0
        self.last_salvaged = False

    def interpret(self, message, state):
        self.last_attempts = 1
        self.last_salvaged = False
        parsed = self.nlu.parse(message)
        intent = parsed["intent"]
        kind = {"greet": "greet", "goodbye": "goodbye", "out_of_scope": "out_of_scope"}.get(intent, "request")
        if kind != "request":
            return TurnInterpretation(kind=kind)
        keys, unknown = [], []
        for found in parsed["traits"]:
            if found["trait"] in self.catalogue.keys:
                keys.append(found["trait"])
            else:
                span = found["span"].strip()[:240]  # a blank span cannot be clarified, and would
                if not span:                        # fail the whole turn at policy validation
                    continue
                nearest = found.get("nearest")
                unknown.append(Unresolved(span, [nearest] if nearest in self.catalogue.keys else []))
        return TurnInterpretation(kind="answer" if state.awaiting else "request", request_generation=True,
                                  trait_updates=[TraitUpdate("add", keys)] if keys else [],
                                  intensity={"make_meaner": "harsh", "make_softer": "mild"}.get(intent),
                                  unresolved=unknown)
