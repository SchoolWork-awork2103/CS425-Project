"""Qwen interpretation and an explicit adapter for the existing NLU baseline."""
import json

from .prompts import messages
from .types import InterpretationError, TraitUpdate, TurnInterpretation, Unresolved


def _salvage_unknown_traits(text, allowed, intensity_aliases):
    """Recover an interpretation whose trait_updates name non-catalogue keys.

    The model occasionally invents traits for messages that name none
    ("roast me" -> add braggart). The whole offending update is dropped and the
    rest is re-validated; any other failure is left to the retry.
    """
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON field")
            result[key] = value
        return result

    try:
        data = json.loads(text, object_pairs_hook=unique)
    except (ValueError, TypeError):
        return None
    if type(data) is not dict:
        return None
    updates = data.get("trait_updates")
    if type(updates) is not list:
        return None
    kept, changed = [], False
    for update in updates:
        if (type(update) is dict and set(update) == {"mode", "traits"}
                and type(update.get("traits")) is list
                and all(type(t) is str and t in allowed for t in update["traits"])):
            kept.append(update)
        else:
            changed = True
    if not changed:
        return None
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
                salvaged = _salvage_unknown_traits(text, self.catalogue.keys, self.intensity_aliases)
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
                nearest = found.get("nearest")
                unknown.append(Unresolved(found["span"][:240], [nearest] if nearest in self.catalogue.keys else []))
        return TurnInterpretation(kind="answer" if state.awaiting else "request", request_generation=True,
                                  trait_updates=[TraitUpdate("add", keys)] if keys else [],
                                  intensity={"make_meaner": "harsh", "make_softer": "mild"}.get(intent),
                                  unresolved=unknown)
