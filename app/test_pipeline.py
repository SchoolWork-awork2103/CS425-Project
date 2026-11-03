from copy import deepcopy
import unittest
from unittest.mock import Mock
from .pipeline import Pipeline
from dialogue.types import (DialogueState, InterpretationError, PendingQuestion, TraitUpdate,
                            TurnInterpretation, Unresolved)
from reranker.rerank import Reranker
from utils import load_config

GOOD = ["you call yourself confident and proud,", "but all we hear is you being loud.",
        "you think your every word is wise,", "yet nobody listens, we just roll our eyes."]


class PipelineTest(unittest.TestCase):
    def setUp(self):
        self.cfg = load_config()
        self.interpreter = Mock()
        self.interpreter.interpret.return_value = TurnInterpretation(
            request_generation=True, trait_updates=[TraitUpdate("replace", ["confident"])])
        self.service = Mock()
        self.service.generate.return_value = [{"lines": GOOD, "norm_logprob": -1.0}]
        self.planner = Mock()
        self.planner.plan.return_value = [{"end_words": ["proud", "loud", "wise", "eyes"]}]
        self.reranker = Reranker(self.cfg, trait_fit=False)
        self.reranker.toxicity = lambda poems: [{k: 0.0 for k in self.cfg["toxicity"]} for p in poems]
        self.pipeline = Pipeline(self.cfg, interpreter=self.interpreter, service=self.service,
                                 planner=self.planner, reranker=self.reranker)

    def test_success_commits_selected_plan_and_history(self):
        original = DialogueState()
        reply, state = self.pipeline.respond("roast my confidence", original)
        self.assertEqual(reply, "\n".join(GOOD))
        self.assertEqual(len(state.history), 1)
        self.assertEqual(state.last_plan, ["proud", "loud", "wise", "eyes"])
        self.assertEqual(state.history[0].actual_end_words, state.last_plan)
        self.assertEqual(original, DialogueState())

    def test_repeat_retry_exhaustion_preserves_history_and_settings(self):
        _, state = self.pipeline.respond("roast my confidence")
        original = deepcopy(state)
        reply, state = self.pipeline.respond("another", state)
        self.assertIn("couldn't find", reply)
        self.assertEqual(state.history, original.history)
        self.assertEqual(state.last_plan, original.last_plan)
        self.assertEqual(self.pipeline.last_trace["generation_batches"], 2)
        self.assertEqual(state.traits, ["confident"])

    def test_full_aabb_preferred_then_best_of_any_rhyme(self):
        loose = [GOOD[0], "but all we hear is you being cheap.", *GOOD[2:]]     # first couplet doesn't rhyme
        self.service.generate.return_value = [{"lines": loose, "norm_logprob": -0.1}, {"lines": GOOD, "norm_logprob": -5.0}]
        reply, _ = self.pipeline.respond("roast my confidence")
        self.assertEqual(reply, "\n".join(GOOD))
        self.service.generate.return_value = [{"lines": loose, "norm_logprob": -0.1}]
        reply, state = self.pipeline.respond("roast my confidence")
        self.assertEqual(reply, "\n".join(loose))
        self.assertTrue(self.pipeline.last_trace["aabb_fallback"])
        self.assertEqual(self.pipeline.last_trace["generation_batches"], 2)   # retried before falling back

    def test_guessed_trait_is_noted_in_the_reply_once(self):
        self.interpreter.interpret.return_value = TurnInterpretation(
            request_generation=True, trait_updates=[TraitUpdate("add", ["bookish"])])
        self.interpreter.last_notes = ["(Reading 'read minds' as bookish.)"]
        reply, state = self.pipeline.respond("I can read minds")
        self.assertEqual(reply, "\n".join(["(Reading 'read minds' as bookish.)", *GOOD]))
        self.assertEqual(state.history[0].lines, GOOD)
        # a turn answered without the interpreter (the control path) does not repeat the note
        self.service.generate.return_value = [{"lines": [*GOOD[:3], "yet nobody listens, we all roll our eyes."],
                                               "norm_logprob": -1.0}]
        state.awaiting = PendingQuestion(TurnInterpretation(request_generation=True,
                                                            unresolved=[Unresolved("jokes", ["funny"])]), "choice")
        reply, state = self.pipeline.respond("1", state)
        self.assertNotIn("Reading", reply)
        self.assertEqual(state.traits, ["bookish", "funny"])

    def test_clarification_and_bad_interpretation_do_not_generate(self):
        self.interpreter.interpret.return_value = TurnInterpretation(request_generation=True)
        _, state = self.pipeline.respond("roast me")
        self.assertIsNotNone(state.awaiting)
        self.service.generate.assert_not_called()
        self.interpreter.interpret.side_effect = InterpretationError("invalid")
        _, same = self.pipeline.respond("unclear", state)
        self.assertEqual(same, state)
        self.service.generate.assert_not_called()

    def test_switch_generator_and_reset_independent_sessions(self):
        self.pipeline.generator_a = Mock(return_value=[{"lines": GOOD, "norm_logprob": -1.0}])
        _, state = self.pipeline.respond("roast my confidence", system="A")
        self.assertEqual(state.history[0].system, "A")
        self.service.generate.assert_not_called()
        self.assertEqual(self.pipeline.manager.initial_state(), DialogueState())
        _, reset = self.pipeline.respond("reset", state)
        self.assertEqual(reset, DialogueState())

    def test_generator_e(self):
        self.pipeline.generator_e = Mock(return_value=[{"lines": GOOD, "norm_logprob": -1.0}])
        _, state = self.pipeline.respond("roast my confidence", system="E")
        self.assertEqual(state.history[0].system, "E")
        self.service.generate.assert_not_called()
        with self.assertRaises(ValueError):
            Pipeline(self.cfg, system="B", interpreter=self.interpreter, service=self.service)

    def test_missing_assets_are_recoverable(self):
        self.planner.plan.side_effect = FileNotFoundError("missing GloVe")
        with self.assertLogs("app.pipeline", level="ERROR"):
            reply, state = self.pipeline.respond("roast my confidence")
        self.assertIn("settings are saved", reply)
        self.assertEqual(state.traits, ["confident"])
        self.assertEqual(state.history, [])

    def test_planner_exclusion_fallback_keeps_candidate_metadata(self):
        self.planner.plan.side_effect = [[], [{"end_words": ["proud", "loud", "wise", "eyes"]}]]
        _, state = self.pipeline.respond("roast my confidence", DialogueState(last_plan=["bright", "night", "day", "say"]))
        self.assertEqual(self.planner.plan.call_args_list[0].kwargs["exclude"], ["bright", "night", "day", "say"])
        self.assertEqual(state.last_plan, ["proud", "loud", "wise", "eyes"])

    def test_none_message_is_treated_as_empty(self):
        reply, state = self.pipeline.respond(None, DialogueState(traits=["wise"]))
        self.assertIn("Tell me a trait", reply)
        self.assertEqual(state.traits, ["wise"])

    def test_explicit_roast_request_restored_when_interpreter_drops_it(self):
        self.interpreter.interpret.return_value = TurnInterpretation(
            request_generation=False, trait_updates=[TraitUpdate("add", ["confident"])])
        reply, state = self.pipeline.respond("roast me, I am confident")
        self.assertEqual(reply, "\n".join(GOOD))
        self.assertEqual(state.traits, ["confident"])
        self.assertEqual(self.pipeline.last_trace.get("roast_request_restored"), True)

    def test_refused_roast_is_not_forced(self):
        self.interpreter.interpret.return_value = TurnInterpretation(
            request_generation=False, trait_updates=[TraitUpdate("add", ["confident"])])
        reply, state = self.pipeline.respond("no roast for now, just note that I am confident")
        self.assertIn("Settings updated", reply)
        self.assertEqual(state.traits, ["confident"])
        self.service.generate.assert_not_called()
        self.assertNotIn("roast_request_restored", self.pipeline.last_trace)

    def test_common_refusal_phrasings_are_not_forced(self):
        # Each message needs a fresh interpretation object; the policy mutates it.
        self.interpreter.interpret.side_effect = lambda message, state: TurnInterpretation(
            request_generation=False, trait_updates=[TraitUpdate("add", ["confident"])])
        for message in ["you cannot roast me", "I don't want a roast", "won\u2019t roast me",
                        "I refuse to be roasted", "no more roasts please, thanks"]:
            with self.subTest(message=message):
                reply, _ = self.pipeline.respond(message, DialogueState(traits=["wise"]))
                self.assertIn("Settings updated", reply)
                self.assertNotIn("roast_request_restored", self.pipeline.last_trace)
        self.service.generate.assert_not_called()

    def test_roast_requests_are_still_restored(self):
        # The widened refusal pattern must not silence the safety net on plain requests.
        self.interpreter.interpret.side_effect = lambda message, state: TurnInterpretation(
            request_generation=False)
        for message in ["roast me", "Roast!", "give me a roast please", "one more roast"]:
            with self.subTest(message=message):
                reply, _ = self.pipeline.respond(message, DialogueState(traits=["wise"]))
                self.assertEqual(reply, "\n".join(GOOD))

    def test_unanchored_remove_echoing_session_is_dropped(self):
        # "change intensity to harsh" never mentions confident; the model's remove is an echo.
        self.interpreter.interpret.return_value = TurnInterpretation(
            request_generation=False, intensity="harsh",
            trait_updates=[TraitUpdate("remove", ["confident"])])
        reply, state = self.pipeline.respond("change intensity to harsh",
                                             DialogueState(traits=["confident", "athletic"]))
        self.assertIn("Settings updated: confident, athletic; harsh", reply)
        self.assertEqual(state.traits, ["confident", "athletic"])
        self.assertEqual(state.intensity, "harsh")
        self.assertEqual(self.pipeline.last_trace.get("ungrounded_updates_dropped"),
                         [{"mode": "remove", "traits": ["confident"]}])
        self.service.generate.assert_not_called()

    def test_anchored_remove_is_kept(self):
        self.interpreter.interpret.return_value = TurnInterpretation(
            request_generation=True, trait_updates=[TraitUpdate("remove", ["bookish"])])
        reply, state = self.pipeline.respond("leave out the reading part",
                                             DialogueState(traits=["bookish", "confident"]))
        self.assertEqual(reply, "\n".join(GOOD))
        self.assertEqual(state.traits, ["confident"])
        self.assertNotIn("ungrounded_updates_dropped", self.pipeline.last_trace)

    def test_hallucinated_add_is_left_to_the_model(self):
        # Adds show in the settings reply, so only destructive edits are bounded here.
        self.interpreter.interpret.return_value = TurnInterpretation(
            request_generation=True, trait_updates=[TraitUpdate("add", ["adventurous"])])
        _, state = self.pipeline.respond("roast me")
        self.assertEqual(state.traits, ["adventurous"])
        self.assertNotIn("ungrounded_updates_dropped", self.pipeline.last_trace)

    def test_bare_continuation_cannot_change_settings(self):
        # Observed live: for "another" the model invented add outgoing, silently mutating
        # settings ahead of an un-echoed generate reply. A bare continuation keeps them.
        self.interpreter.interpret.side_effect = lambda message, state: TurnInterpretation(
            request_generation=True, trait_updates=[TraitUpdate("add", ["outgoing"])])
        reply, state = self.pipeline.respond("another", DialogueState(traits=["confident", "athletic"]))
        self.assertEqual(reply, "\n".join(GOOD))
        self.assertEqual(state.traits, ["confident", "athletic"])
        self.assertEqual(self.pipeline.last_trace["bare_continuation_updates_dropped"],
                         [{"mode": "add", "traits": ["outgoing"]}])
        # generic_requested on "another" would clear the trait list; it is stripped as well
        self.interpreter.interpret.side_effect = lambda message, state: TurnInterpretation(
            request_generation=True, generic_requested=True)
        _, state = self.pipeline.respond("One more roast!", DialogueState(traits=["confident"]))
        self.assertEqual((state.traits, state.generic), (["confident"], False))
        # only exact bare requests: anything with more content keeps the model's edits
        for message in ["another, but add outgoing", "outgoing", "another one, harsher"]:
            with self.subTest(message=message):
                self.interpreter.interpret.side_effect = lambda m, s: TurnInterpretation(
                    request_generation=True, trait_updates=[TraitUpdate("add", ["outgoing"])])
                _, state = self.pipeline.respond(message, DialogueState(traits=["confident"]))
                self.assertEqual(state.traits, ["confident", "outgoing"])

    def test_pending_answer_remove_is_exempt_from_grounding(self):
        state = DialogueState(traits=["patient", "confident"],
                              awaiting=PendingQuestion(
                                  TurnInterpretation(request_generation=True,
                                                      unresolved=[Unresolved("drop which trait",
                                                                             ["patient", "confident"],
                                                                             "remove", "traits")])))
        self.interpreter.interpret.return_value = TurnInterpretation(
            kind="answer", request_generation=True, trait_updates=[TraitUpdate("remove", ["patient"])])
        reply, new = self.pipeline.respond("no, the second quality", state)
        self.assertEqual(reply, "\n".join(GOOD))
        self.assertEqual(new.traits, ["confident"])
        self.assertIsNone(new.awaiting)


if __name__ == "__main__":
    unittest.main()
