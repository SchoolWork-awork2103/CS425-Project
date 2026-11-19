import json
import unittest
from .catalogue import TraitCatalogue
from .manager import DialogueManager
from .types import (DialogueState, InterpretationError, PendingQuestion, PoemRecord, TraitUpdate,
                    TurnInterpretation, Unresolved)


def turn(traits=(), mode="add", **kwargs):
    return TurnInterpretation(trait_updates=[TraitUpdate(mode, list(traits))] if traits else [], **kwargs)


class ManagerTest(unittest.TestCase):
    def setUp(self):
        self.manager = DialogueManager(TraitCatalogue.load(), history_limit=2)

    def test_missing_traits_then_answer_keeps_intensity(self):
        original = DialogueState()
        decision, state = self.manager.step(turn(request_generation=True, intensity="harsh"), original)
        self.assertEqual(decision.kind, "clarify")
        self.assertIsNone(original.awaiting)
        decision, state = self.manager.step(turn(["confident"], kind="answer"), state)
        self.assertEqual((decision.kind, state.traits, state.intensity), ("generate", ["confident"], "harsh"))
        self.assertIsNone(state.awaiting)

    def test_ordered_compound_edits_and_intensity(self):
        original = DialogueState(traits=["smart", "confident"])
        edit = TurnInterpretation(request_generation=True, intensity="mild", trait_updates=[
            TraitUpdate("remove", ["smart"]), TraitUpdate("add", ["musical", "confident"])])
        decision, state = self.manager.step(edit, original)
        self.assertEqual(state.traits, ["confident", "musical"])
        self.assertEqual(decision.kind, "generate")
        self.assertEqual(original.traits, ["smart", "confident"])

    def test_ambiguous_compound_edit_is_atomic_and_choice_resumes(self):
        original = DialogueState(traits=["smart"], intensity="harsh")
        proposal = TurnInterpretation(request_generation=True, intensity="mild",
                                     unresolved=[Unresolved("driven", ["ambitious", "hardworking"], "replace")])
        decision, state = self.manager.step(proposal, original)
        self.assertEqual((state.traits, state.intensity), (["smart"], "harsh"))
        self.assertEqual(decision.kind, "clarify")
        decision, state = self.manager.control("second", state)
        self.assertEqual((decision.kind, state.traits, state.intensity), ("generate", ["hardworking"], "mild"))

    def test_multiple_unknowns_resolve_sequentially(self):
        proposal = TurnInterpretation(request_generation=True, unresolved=[Unresolved("first"), Unresolved("second")])
        _, state = self.manager.step(proposal, DialogueState())
        _, state = self.manager.step(turn(["wise"], kind="answer"), state)
        self.assertEqual(state.traits, [])
        self.assertEqual(state.awaiting.proposed.unresolved[0].text, "second")
        decision, state = self.manager.step(turn(["loyal"], kind="answer"), state)
        self.assertEqual((decision.kind, state.traits), ("generate", ["wise", "loyal"]))

    def test_partial_replacement_retains_already_resolved_traits(self):
        proposal = TurnInterpretation(request_generation=True,
                                      trait_updates=[TraitUpdate("replace", ["smart"])],
                                      unresolved=[Unresolved("driven", ["ambitious", "hardworking"], "replace")])
        _, state = self.manager.step(proposal, DialogueState(traits=["musical"]))
        self.assertEqual(state.traits, ["musical"])
        decision, state = self.manager.control("first", state)
        self.assertEqual((decision.kind, state.traits), ("generate", ["smart", "ambitious"]))

    def test_yes_no_and_new_request(self):
        proposal = TurnInterpretation(request_generation=True, unresolved=[Unresolved("books", ["bookish"])])
        _, state = self.manager.step(proposal, DialogueState(traits=["smart"]))
        decision, accepted = self.manager.control("yes", state)
        self.assertEqual(accepted.traits, ["smart", "bookish"])
        decision, cancelled = self.manager.control("no", state)
        self.assertIsNone(cancelled.awaiting)
        self.assertEqual(cancelled.traits, ["smart"])
        decision, replaced = self.manager.step(turn(["musical"], mode="replace", request_generation=True), state)
        self.assertEqual(replaced.traits, ["musical"])
        self.assertIsNone(replaced.awaiting)

    def test_intensity_ambiguity_can_be_resolved(self):
        _, state = self.manager.step(TurnInterpretation(request_generation=True,
                                    unresolved=[Unresolved("meaner or softer intensity", target="intensity")]), DialogueState(traits=["wise"]))
        decision, state = self.manager.step(turn(kind="answer", intensity="mild"), state)
        self.assertEqual((decision.kind, state.intensity), ("generate", "mild"))

    def test_generic_is_explicit_and_persists_for_another(self):
        decision, state = self.manager.step(turn(request_generation=True, generic_requested=True), DialogueState(traits=["wise"]))
        self.assertEqual((decision.kind, state.traits, state.generic), ("generate", [], True))
        decision, state = self.manager.step(turn(request_generation=True), state)
        self.assertEqual(decision.kind, "generate")
        _, state = self.manager.step(turn(["smart"]), state)
        self.assertFalse(state.generic)

    def test_remove_final_trait_prompts_and_removal_is_idempotent(self):
        decision, state = self.manager.step(turn(["smart"], mode="remove", request_generation=True), DialogueState(traits=["smart"]))
        self.assertEqual((decision.kind, state.traits), ("clarify", []))
        _, state = self.manager.step(turn(["smart"], mode="remove"), state)
        self.assertEqual(state.traits, [])

    def test_history_bounded_reset_and_sessions_independent(self):
        state, other = DialogueState(traits=["wise"]), DialogueState()
        for i in range(3):
            state = self.manager.record_success(state, PoemRecord([str(i)] * 4, "D", ["wise"], "mild", [str(i)] * 4, []))
        self.assertEqual(len(state.history), 2)
        self.assertEqual(state.last_plan, ["2"] * 4)
        self.assertEqual(other.history, [])
        _, reset = self.manager.control("/reset", state)
        self.assertEqual(reset, DialogueState())

    def test_offtopic_edits_in_answer_are_staged(self):
        _, state = self.manager.step(TurnInterpretation(request_generation=True,
                                unresolved=[Unresolved("meaner or softer", target="intensity")]),
                                     DialogueState(traits=["wise"]))
        decision, state = self.manager.step(TurnInterpretation(kind="answer", intensity="mild",
                                trait_updates=[TraitUpdate("add", ["confident"])]), state)
        self.assertEqual((decision.kind, state.traits, state.intensity),
                         ("generate", ["wise", "confident"], "mild"))

    def test_partial_intensity_answer_survives_reclarification(self):
        _, state = self.manager.step(TurnInterpretation(request_generation=True,
                                unresolved=[Unresolved("driven", ["ambitious", "hardworking"])]),
                                     DialogueState(traits=["wise"], intensity="harsh"))
        decision, state = self.manager.step(TurnInterpretation(kind="answer", intensity="mild"), state)
        self.assertEqual(decision.kind, "clarify")
        self.assertEqual(state.awaiting.proposed.intensity, "mild")
        decision, state = self.manager.control("first", state)
        self.assertEqual((decision.kind, state.traits, state.intensity),
                         ("generate", ["wise", "ambitious"], "mild"))

    def test_noop_edit_keeps_generic_mode(self):
        decision, state = self.manager.step(turn(["smart"], mode="remove"), DialogueState(generic=True))
        self.assertEqual((decision.kind, state.traits, state.generic), ("say", [], True))
        decision, state = self.manager.step(turn(request_generation=True), state)
        self.assertEqual((decision.kind, state.traits), ("generate", []))

    def test_remove_question_answered_in_its_own_mode(self):
        _, state = self.manager.step(TurnInterpretation(request_generation=True,
                                unresolved=[Unresolved("driven", ["ambitious", "hardworking"], "remove")]),
                                     DialogueState(traits=["wise", "hardworking"]))
        decision, state = self.manager.step(TurnInterpretation(kind="answer",
                                trait_updates=[TraitUpdate("remove", ["hardworking"])]), state)
        self.assertEqual((decision.kind, state.traits), ("generate", ["wise"]))

    def test_unresolvable_answer_reasks_instead_of_dropping(self):
        _, state = self.manager.step(TurnInterpretation(request_generation=True,
                                unresolved=[Unresolved("driven", ["ambitious", "hardworking"])]),
                                     DialogueState(traits=["wise"]))
        decision, state = self.manager.step(TurnInterpretation(kind="answer",
                                trait_updates=[TraitUpdate("remove", ["wise"])]), state)
        self.assertEqual(decision.kind, "clarify")
        self.assertTrue(state.awaiting)  # the question is still staged, nothing lost

    def test_intensity_question_resolves_by_word_and_ordinal(self):
        _, state = self.manager.step(TurnInterpretation(request_generation=True,
                                unresolved=[Unresolved("meaner or softer", target="intensity")]),
                                     DialogueState(traits=["wise"], intensity="mild"))
        decision, milder = self.manager.control("mild", state)
        self.assertEqual((decision.kind, milder.intensity), ("generate", "mild"))
        decision, harsher = self.manager.control("Second", state)
        self.assertEqual((decision.kind, harsher.intensity), ("generate", "harsh"))
        decision, _ = self.manager.control("harsh?", state)
        self.assertEqual((decision.kind, decision.intensity), ("generate", "harsh"))
        self.assertEqual(self.manager.control("harsh", state)[1].traits, ["wise"])
        self.assertIsNone(self.manager.control("quite", state))  # unrecognised words still reach the interpreter

    def test_invalid_typed_operations_are_rejected(self):
        with self.assertRaises(InterpretationError):
            self.manager.step(turn(["telepathic"]), DialogueState())

    def test_pending_proposal_stays_bounded(self):
        # Answers that each add a new clarification must not grow the staged question forever:
        # session.summary() feeds every interpretation prompt and has a token budget.
        _, state = self.manager.step(TurnInterpretation(request_generation=True,
                                unresolved=[Unresolved("alpha")]), DialogueState(traits=["wise"]))
        for i in range(150):
            decision, state = self.manager.step(TurnInterpretation(
                kind="answer", unresolved=[Unresolved(("unknown %d " % (i % 10)) * 23)]), state)
            self.assertEqual(decision.kind, "clarify")
        self.assertLessEqual(len(state.awaiting.proposed.unresolved), 8)
        self.assertLess(len(json.dumps(state.summary())), 10000)
        # the queue is still functional: resolving the current question stages its answer
        # and re-asks the next queued description, exactly as before the cap kicked in
        decision, state = self.manager.step(turn(["loyal"], kind="answer"), state)
        self.assertEqual(decision.kind, "clarify")
        self.assertEqual(state.awaiting.proposed.trait_updates, [TraitUpdate("add", ["loyal"])])

    def test_staged_updates_coalesce_without_changing_effects(self):
        _, state = self.manager.step(TurnInterpretation(request_generation=True,
                                unresolved=[Unresolved("meaner or softer", target="intensity")]),
                                     DialogueState(traits=["wise"]))
        for traits in (["smart"], ["confident"], ["smart"]):  # adjacent same-mode merges, deduped
            _, state = self.manager.step(turn(traits, kind="answer"), state)
        self.assertEqual(state.awaiting.proposed.trait_updates, [TraitUpdate("add", ["smart", "confident"])])
        decision, state = self.manager.step(turn(kind="answer", intensity="mild"), state)
        self.assertEqual((decision.kind, state.traits), ("generate", ["wise", "smart", "confident"]))

    def test_controls_survive_lookalike_characters_and_punctuation(self):
        state = DialogueState(traits=["wise"], awaiting=PendingQuestion(
            TurnInterpretation(request_generation=True,
                               unresolved=[Unresolved("driven", ["ambitious", "hardworking"])]),
            "choice", True))
        _, fresh = self.manager.control("  ｒｅｓｅｔ\u200b... ", DialogueState(traits=["wise"]))
        self.assertEqual(fresh, DialogueState())
        _, fresh = self.manager.control("start\u00a0over.", state)
        self.assertEqual(fresh, DialogueState())
        # ligature and typographic punctuation still resolve the pending choice / cancel
        self.assertEqual(self.manager.control("ﬁrst!!", state)[1].traits, ["wise", "ambitious"])
        self.assertEqual(self.manager.control("no\u200b\u00a0", state)[1].awaiting, None)
        self.assertIsNone(self.manager.control("ﬁrst I said ambitious", state))  # sentences go to the model


if __name__ == "__main__":
    unittest.main()
