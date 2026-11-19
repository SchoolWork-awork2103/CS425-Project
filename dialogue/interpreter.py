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


# "less harsh" is milder, not harsher
HARSHER = re.compile(r"(?<!less )\b(?:harsh(?:er|ly)?|meaner|harder|nastier|crueller|crueler|brutal(?:ly)?|savage"
                     r"|ruthless|rougher|spicier|more (?:mean|brutal|savage)|no mercy|go hard|turn it up)\b")
MILDER = re.compile(r"\b(?:mild(?:er|ly)?|soft(?:er|ly)|gentle|gentler|gently|nicer|kinder|lighter|easier"
                    r"|less (?:mean|harsh|brutal|savage)|go easy|tone it down|take it easy|dial it back)\b")
GENERIC = re.compile(r"\b(?:generic|anything|whatever|surprise me|any roast)\b")
CONTINUATION = re.compile(r"\b(?:another|again|one more|redo|different one)\b")
REQUEST_CUE = re.compile(r"\b(?:roast|diss|verse|poem|rhyme|another|again|one more|redo|different one)\b")
NEGATION = {"not", "don't", "dont", "never", "no", "stop", "without"}
REMOVE_CUE = re.compile(r"\b(?:remove|drop|forget|leave out|take out|without|no longer)\b")
REPLACE_CUE = re.compile(r"\b(?:instead|replace|switch to|change (?:it )?to|swap to)\b")


def _cue(pattern, text):
    """True when the pattern occurs without a negation in the three words before it ("don't make it meaner")."""
    return any(not NEGATION & set(text[:m.start()].split()[-3:]) for m in pattern.finditer(text))


class NLUInterpreter:
    """The Phase 6 joint model (seven intents, TRAIT spans), mapped onto the policy contract.

    The model has no remove/replace/generic intents and its make_meaner head is the weakest (pipeline.md, Phase 6),
    so keyword rules sit on top:
      - intensity words (harsh, meaner, softer, go easy, ...) set the intensity before the intent head is trusted,
        unless negated ("don't make it meaner"); a span that is only an intensity word ("be meaner") is not a trait.
        Without one, make_meaner / make_softer count only for a message that names no trait and asks for no
        continuation, since the head also fires on "add healthy again" and "try a different one"
      - roast/verse/another/... and generic/anything make it a request even if the intent head says otherwise
      - trait keys and their other forms (calm, loyalty) the tagger left out are added from the message itself
      - remove words before a trait ("drop the bookish part", "I'm not confident") remove it; "not" counts only
        before the trait word itself, since "not lazy" describes hardworking
      - "instead" / "replace ... with" replace the traits; "replace X with Y" removes X and adds Y
      - "generic roast" with no trait asks for a generic roast
    A trait guessed by embedding similarity is used and noted in last_notes ("use the nearest trait and say so");
    an unknown one is asked about, with its nearest trait as the suggestion.
    """

    def __init__(self, nlu, catalogue):
        self.nlu, self.catalogue = nlu, catalogue
        self.last_attempts = 0
        self.last_salvaged = False
        self.last_notes = []

    def mentions(self, parsed, text):
        """(trait or None, how, span, position in text, nearest) for every trait the message mentions."""
        from nlu.normalize import other_form
        found = []
        for f in parsed["traits"]:
            span = f["span"].strip()[:240]         # a blank span cannot be clarified, and would
            if not span:                           # fail the whole turn at policy validation
                continue
            low = span.casefold()
            if GENERIC.fullmatch(low.split()[0]) or (HARSHER.search(low) or MILDER.search(low)) and f.get("how") not in ("key", "synonym"):
                continue                           # "generic" passes other_form for generous
            found.append((f["trait"], f.get("how"), span, text.find(low), f.get("nearest")))
        seen = {f[0] for f in found}
        for m in re.finditer(r"[a-z]+", text):    # the tagger misses plain trait words ("confident and calm")
            if GENERIC.fullmatch(m.group()):
                continue
            for key in self.catalogue.entries:
                if key not in seen and (m.group() == key or other_form(m.group(), key)):
                    found.append((key, "key", m.group(), m.start(), None))
                    seen.add(key)
        return found

    def interpret(self, message, state):
        self.last_attempts = 1
        self.last_salvaged = False
        self.last_notes = []
        text = " ".join(message.casefold().replace("’", "'").split())
        parsed = self.nlu.parse(message)
        intent = parsed["intent"]
        harsher, milder, generic = _cue(HARSHER, text), _cue(MILDER, text), bool(GENERIC.search(text))
        kind = {"greet": "greet", "goodbye": "goodbye", "out_of_scope": "out_of_scope"}.get(intent, "request")
        if kind != "request" and not (harsher or milder or generic or REQUEST_CUE.search(text)):
            return TurnInterpretation(kind=kind)
        mentions = self.mentions(parsed, text)
        intensity, unresolved = None, []
        if harsher and milder:
            unresolved.append(Unresolved("meaner or softer", [], "add", "intensity"))
        elif harsher or milder:
            intensity = "harsh" if harsher else "mild"
        elif not mentions and not CONTINUATION.search(text):
            # with no intensity word, the intent head alone; it also fires on trait edits and "try a different one"
            intensity = {"make_meaner": "harsh", "make_softer": "mild"}.get(intent)

        with_at = text.find(" with ") if re.search(r"\breplace\b", text) else -1
        adds, removes = [], []
        for trait, how, span, at, nearest in mentions:
            words = span.casefold().split()
            prev = (text[:at] if at >= 0 else "").split()[-3:]
            removed = (bool(REMOVE_CUE.search(" ".join(prev))) or words[0] in ("remove", "drop", "forget")
                       or how == "key" and "not" in [*prev[-2:], words[0]] or 0 <= at < with_at)
            if trait in self.catalogue.keys:
                (removes if removed else adds).append(trait)
                if how == "nearest" and not removed:
                    self.last_notes.append(f"(Reading '{span}' as {trait}.)")
            elif not removed:
                unresolved.append(Unresolved(span, [nearest] if nearest in self.catalogue.keys else []))
        if with_at >= 0 and not adds:              # the tagger often misses the trait after "with"
            rule = getattr(getattr(self.nlu, "normalizer", None), "rule", None)
            found = rule(text[with_at + 6:]) if rule else None
            if found and found["trait"] in self.catalogue.keys:
                adds.append(found["trait"])
        updates = [TraitUpdate("remove", removes)] if removes else []
        if adds:
            replace = REPLACE_CUE.search(text) and not removes
            updates.append(TraitUpdate("replace" if replace else "add", adds))
        return TurnInterpretation(kind="answer" if state.awaiting else "request", request_generation=True,
                                  trait_updates=updates, intensity=intensity,
                                  generic_requested=generic and not updates and not unresolved, unresolved=unresolved)
