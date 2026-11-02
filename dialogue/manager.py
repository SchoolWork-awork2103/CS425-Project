"""Deterministic policy. All methods return new state; no model calls occur here."""
from copy import deepcopy
from .types import Decision, DialogueState, PendingQuestion, TraitUpdate, TurnInterpretation

RESET_REPLY = "Fresh start. What traits should I roast?"


class DialogueManager:
    def __init__(self, catalogue, history_limit=20, default_intensity="mild"):
        if default_intensity not in ("mild", "harsh") or history_limit < 1:
            raise ValueError("Invalid dialogue settings")
        self.catalogue, self.history_limit = catalogue, history_limit
        self.default_intensity = default_intensity

    def initial_state(self):
        return DialogueState(intensity=self.default_intensity)

    def control(self, message, state):
        """Only exact unambiguous controls bypass interpretation."""
        text = message.strip().casefold().rstrip(".!?")
        if text in {"reset", "/reset", "start over", "clear chat"}:
            return Decision("say", RESET_REPLY), self.initial_state()
        if not text:
            return Decision("say", "Tell me a trait, or ask for another roast."), deepcopy(state)
        if state.awaiting:
            if text in {"cancel", "never mind", "nevermind", "no", "nope"}:
                new = deepcopy(state)
                new.awaiting = None
                return Decision("say", "Cancelled. Your previous settings are still active."), new
            pending = state.awaiting
            if pending.expected == "choice" and pending.proposed.unresolved:
                item = pending.proposed.unresolved[0]
                if item.target == "intensity":
                    # The question lists mild first, so these resolve without a model (the NLU baseline cannot read them).
                    intensity = {"mild": "mild", "harsh": "harsh",
                                 "1": "mild", "first": "mild", "2": "harsh", "second": "harsh"}.get(text)
                    if intensity:
                        return self.step(TurnInterpretation(kind="answer", intensity=intensity), state)
                else:
                    options = item.candidates
                    choice = text if text in options else None
                    if text in {"yes", "yep", "correct"} and len(options) == 1:
                        choice = options[0]
                    indices = {"1": 0, "first": 0, "2": 1, "second": 1, "3": 2, "third": 2}
                    if text in indices and indices[text] < len(options):
                        choice = options[indices[text]]
                    if choice:
                        return self.step(TurnInterpretation(kind="answer", trait_updates=[TraitUpdate("add", [choice])]), state)
        return None

    def _clarify(self, turn, state, expected="choice"):
        state.awaiting = PendingQuestion(deepcopy(turn), expected, turn.request_generation)
        if expected == "traits":
            text = "What traits should I roast? For example, confident or bookish. You can also ask for a generic roast."
        else:
            item = turn.unresolved[0]
            if item.target == "intensity":
                text = "Should the roast be mild or harsh?"
            else:
                text = (f"For '{item.text}', do you mean {' or '.join(item.candidates)}?"
                        if item.candidates else f"What supported trait best describes '{item.text}'? For example, confident or bookish.")
            text += " You can cancel this change."
        return Decision("clarify", text), state

    def step(self, turn, state):
        # Validate typed inputs too; callers cannot bypass validation with dataclasses.
        turn = TurnInterpretation.from_dict(turn.to_dict(), self.catalogue.keys)
        state = deepcopy(state)
        canned = {"greet": "Hi! Tell me a trait you're proud of and I'll write an AABB roast.",
                  "goodbye": "See you! Your settings will be here until you reset.",
                  "out_of_scope": "I write playful four-line roasts. Tell me a trait to get started."}
        if turn.kind == "reset":
            return Decision("say", RESET_REPLY), self.initial_state()
        if turn.kind in canned:
            return Decision("say", canned[turn.kind]), state
        if state.awaiting and turn.kind == "answer":
            pending = state.awaiting
            proposal = deepcopy(pending.proposed)
            supplied = [t for u in turn.trait_updates if u.mode != "remove" for t in u.traits]
            if turn.generic_requested:
                proposal.unresolved = []
                proposal.trait_updates = []
                proposal.generic_requested = True
            elif proposal.unresolved and proposal.unresolved[0].target == "traits":
                item = proposal.unresolved[0]
                # The question carries the operation: add-mode answers resolve any question, and a
                # remove/replace question is also resolved by an answer given in its own mode.
                resolution = supplied or [t for u in turn.trait_updates
                                          if u.mode == item.mode for t in u.traits]
                if resolution:
                    proposal.unresolved.pop(0)
                    # Known and unknown traits may belong to the same replacement:
                    # "replace with smart and [ambiguous trait]" must retain smart.
                    replacements = [u for u in proposal.trait_updates if u.mode == "replace"]
                    if item.mode == "replace" and replacements:
                        replacements[-1].traits = list(dict.fromkeys([*replacements[-1].traits, *resolution]))
                    else:
                        proposal.trait_updates.append(TraitUpdate(item.mode, resolution))
            elif (proposal.unresolved and turn.intensity
                  and proposal.unresolved[0].target == "intensity"):
                proposal.unresolved.pop(0)
                # Off-topic edits in the same answer ("mild and confident") stage like a fresh request.
                if turn.trait_updates:
                    proposal.trait_updates.extend(deepcopy(turn.trait_updates))
            elif supplied:
                proposal.trait_updates.extend(deepcopy(turn.trait_updates))
            elif not turn.unresolved:
                # Keep a partial answer (e.g. "make it mild") while re-asking the open question.
                proposal.intensity = turn.intensity or proposal.intensity
                return self._clarify(proposal, state, pending.expected)
            proposal.unresolved.extend(deepcopy(turn.unresolved))
            proposal.intensity = turn.intensity or proposal.intensity
            proposal.request_generation = pending.resume_generation or turn.request_generation
            turn = proposal
        elif turn.kind == "answer" and not state.awaiting:
            turn.kind = "request"
        # An explicit fresh request supersedes pending work.
        state.awaiting = None
        if turn.unresolved:
            return self._clarify(turn, state)
        if turn.generic_requested:
            state.traits, state.generic = [], True
        for update in turn.trait_updates:
            before = list(state.traits)
            if update.mode == "replace":
                state.traits = list(update.traits)
            elif update.mode == "add":
                state.traits = list(dict.fromkeys([*state.traits, *update.traits]))
            else:
                state.traits = [t for t in state.traits if t not in update.traits]
            # No-op edits (e.g. "remove smart" with no smart) leave state unchanged, generic included.
            if state.traits != before:
                state.generic = False
        if turn.intensity:
            state.intensity = turn.intensity
        if turn.request_generation or turn.generic_requested:
            if not state.traits and not state.generic:
                # Settings are resolved; don't replay their updates after receiving traits.
                return self._clarify(TurnInterpretation(request_generation=True), state, "traits")
            return Decision("generate", traits=list(state.traits), intensity=state.intensity), state
        label = ", ".join(state.traits) or ("generic roast" if state.generic else "no traits yet")
        return Decision("say", f"Settings updated: {label}; {state.intensity}. Ask me for a roast."), state

    def record_success(self, state, poem):
        new = deepcopy(state)
        new.history = [*new.history, deepcopy(poem)][-self.history_limit:]
        new.last_plan = list(poem.planned_end_words)
        return new
