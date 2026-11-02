"""Validated turn contracts and session-owned state. No model dependencies."""
from dataclasses import asdict, dataclass, field
import json


class InterpretationError(ValueError):
    """Unusable interpretation; the caller should ask for clarification."""


def _object(value, fields):
    if type(value) is not dict or set(value) != set(fields):
        raise InterpretationError(f"Expected exactly these fields: {', '.join(fields)}")


def _keys(value, allowed, limit=40):
    if type(value) is not list or len(value) > limit:
        raise InterpretationError("Expected a bounded list of trait keys")
    if any(type(t) is not str or t not in allowed for t in value):
        raise InterpretationError("Unknown trait key")
    return list(dict.fromkeys(value))


@dataclass
class TraitUpdate:
    mode: str
    traits: list[str]


@dataclass
class Unresolved:
    text: str
    candidates: list[str] = field(default_factory=list)
    mode: str = "add"
    target: str = "traits"


@dataclass
class TurnInterpretation:
    kind: str = "request"
    request_generation: bool = False
    trait_updates: list[TraitUpdate] = field(default_factory=list)
    intensity: str | None = None
    generic_requested: bool = False
    unresolved: list[Unresolved] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data, allowed, intensity_aliases=None):
        _object(data, ("kind", "request_generation", "trait_updates", "intensity",
                       "generic_requested", "unresolved"))
        kind = data["kind"]
        if type(kind) is not str or kind not in {
                "request", "answer", "greet", "goodbye", "out_of_scope", "reset"}:
            raise InterpretationError("Invalid kind")
        if type(data["request_generation"]) is not bool or type(data["generic_requested"]) is not bool:
            raise InterpretationError("Flags must be booleans")
        intensity = data["intensity"]
        if intensity is not None and type(intensity) is str and intensity_aliases is not None:
            # App-level leniency for obvious synonyms of the two real values; the
            # contract itself stays strict unless aliases are passed in.
            intensity = intensity_aliases.get(intensity, intensity)
        if intensity is not None and intensity not in ("mild", "harsh"):
            raise InterpretationError("Invalid intensity")
        updates, unresolved = [], []
        if type(data["trait_updates"]) is not list or len(data["trait_updates"]) > 8:
            raise InterpretationError("Too many trait updates")
        for update in data["trait_updates"]:
            _object(update, ("mode", "traits"))
            if type(update["mode"]) is not str or update["mode"] not in {"add", "remove", "replace"}:
                raise InterpretationError("Invalid trait operation")
            keys = _keys(update["traits"], allowed)
            if not keys and update["mode"] != "replace":
                raise InterpretationError("An add/remove operation needs traits")
            updates.append(TraitUpdate(update["mode"], keys))
        if type(data["unresolved"]) is not list or len(data["unresolved"]) > 8:
            raise InterpretationError("Too many unresolved descriptions")
        for item in data["unresolved"]:
            _object(item, ("text", "candidates", "mode", "target"))
            if type(item["text"]) is not str or not item["text"].strip() or len(item["text"]) > 240:
                raise InterpretationError("Invalid unresolved description")
            if type(item["mode"]) is not str or item["mode"] not in {"add", "remove", "replace"}:
                raise InterpretationError("Invalid unresolved operation")
            if type(item["target"]) is not str or item["target"] not in {"traits", "intensity"}:
                raise InterpretationError("Invalid clarification target")
            candidates = _keys(item["candidates"], allowed, 3)
            if item["target"] == "intensity" and candidates:
                raise InterpretationError("Intensity clarification cannot propose traits")
            unresolved.append(Unresolved(item["text"].strip(), candidates, item["mode"], item["target"]))
        if kind not in {"request", "answer"} and (
                updates or unresolved or intensity is not None
                or data["request_generation"] or data["generic_requested"]):
            raise InterpretationError("Non-request turn cannot change settings")
        if data["generic_requested"] and any(u.traits for u in updates):
            raise InterpretationError("Generic roast conflicts with specific traits")
        return cls(kind, data["request_generation"], updates, intensity,
                   data["generic_requested"], unresolved)

    @classmethod
    def from_json(cls, text, allowed, intensity_aliases=None):
        if not isinstance(text, str) or len(text) > 12000:
            raise InterpretationError("Interpretation is too long")
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise InterpretationError("Duplicate JSON field")
                result[key] = value
            return result
        try:
            data = json.loads(text, object_pairs_hook=unique)
        except (ValueError, TypeError) as exc:
            raise InterpretationError("Expected one JSON object") from exc
        return cls.from_dict(data, allowed, intensity_aliases)


@dataclass
class PendingQuestion:
    proposed: TurnInterpretation
    expected: str = "traits"  # traits | choice
    resume_generation: bool = True


@dataclass
class PoemRecord:
    lines: list[str]
    system: str
    traits: list[str]
    intensity: str
    planned_end_words: list[str]
    actual_end_words: list[str]
    metadata: dict = field(default_factory=dict)


@dataclass
class DialogueState:
    traits: list[str] = field(default_factory=list)
    intensity: str = "mild"
    awaiting: PendingQuestion | None = None
    history: list[PoemRecord] = field(default_factory=list)
    last_plan: list[str] | None = None
    generic: bool = False

    def summary(self):
        # Current traits are deliberately omitted from what the interpreter sees:
        # the model only needs the settings a message might change, and the current
        # trait list was the source of it echoing traits into trait_updates.
        return {"intensity": self.intensity, "generic": self.generic,
                "pending": asdict(self.awaiting) if self.awaiting else None}


@dataclass
class Decision:
    kind: str
    text: str = ""
    traits: list[str] = field(default_factory=list)
    intensity: str = "mild"
