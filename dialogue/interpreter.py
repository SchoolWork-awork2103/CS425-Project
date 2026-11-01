"""Qwen interpretation and an explicit adapter for the existing NLU baseline."""
from .prompts import messages
from .types import InterpretationError, TraitUpdate, TurnInterpretation, Unresolved


class QwenInterpreter:
    def __init__(self, service, catalogue, retries=1, max_input_tokens=4096, max_new_tokens=384):
        if not 0 <= retries <= 2:
            raise ValueError("Interpretation retries must be between 0 and 2")
        self.service, self.catalogue = service, catalogue
        self.retries, self.max_input_tokens, self.max_new_tokens = retries, max_input_tokens, max_new_tokens
        self.last_attempts = 0

    def interpret(self, message, state):
        self.last_attempts = 0
        for attempt in range(self.retries + 1):
            self.last_attempts += 1
            text = self.service.interpret(messages(message, state, self.catalogue, retry=attempt > 0),
                                          self.max_input_tokens, self.max_new_tokens)
            try:
                return TurnInterpretation.from_json(text, self.catalogue.keys)
            except InterpretationError:
                if attempt == self.retries:
                    raise


class NLUInterpreter:
    """Baseline: existing seven intents, normalized into the same policy contract.

    Add/remove/replace and negation are not inferred here: evaluate those gaps explicitly.
    """
    def __init__(self, nlu, catalogue):
        self.nlu, self.catalogue = nlu, catalogue
        self.last_attempts = 0

    def interpret(self, message, state):
        self.last_attempts = 1
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
