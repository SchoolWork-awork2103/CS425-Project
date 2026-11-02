from copy import deepcopy
import unittest
from unittest.mock import Mock
from .pipeline import Pipeline
from dialogue.types import DialogueState, InterpretationError, TurnInterpretation, TraitUpdate
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
        toxicity = lambda poems: [{k: 0.0 for k in self.cfg["toxicity"]} for p in poems]
        self.reranker = Reranker(self.cfg, toxicity=toxicity)
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
        _, state = self.pipeline.respond("roast me")
        original = deepcopy(state)
        reply, state = self.pipeline.respond("another", state)
        self.assertIn("couldn't find", reply)
        self.assertEqual(state.history, original.history)
        self.assertEqual(state.last_plan, original.last_plan)
        self.assertEqual(self.pipeline.last_trace["generation_batches"], 2)
        self.assertEqual(state.traits, ["confident"])

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
        _, state = self.pipeline.respond("roast me", system="A")
        self.assertEqual(state.history[0].system, "A")
        self.service.generate.assert_not_called()
        self.assertEqual(self.pipeline.manager.initial_state(), DialogueState())
        _, reset = self.pipeline.respond("reset", state)
        self.assertEqual(reset, DialogueState())

    def test_missing_assets_are_recoverable(self):
        self.planner.plan.side_effect = FileNotFoundError("missing GloVe")
        with self.assertLogs("app.pipeline", level="ERROR"):
            reply, state = self.pipeline.respond("roast me")
        self.assertIn("settings are saved", reply)
        self.assertEqual(state.traits, ["confident"])
        self.assertEqual(state.history, [])

    def test_planner_exclusion_fallback_keeps_candidate_metadata(self):
        self.planner.plan.side_effect = [[], [{"end_words": ["proud", "loud", "wise", "eyes"]}]]
        _, state = self.pipeline.respond("roast me", DialogueState(last_plan=["bright", "night", "day", "say"]))
        self.assertEqual(self.planner.plan.call_args_list[0].kwargs["exclude"], ["bright", "night", "day", "say"])
        self.assertEqual(state.last_plan, ["proud", "loud", "wise", "eyes"])

    def test_none_message_is_treated_as_empty(self):
        reply, state = self.pipeline.respond(None, DialogueState(traits=["wise"]))
        self.assertIn("Tell me a trait", reply)
        self.assertEqual(state.traits, ["wise"])


if __name__ == "__main__":
    unittest.main()
