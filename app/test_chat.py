import unittest
from unittest.mock import Mock

from dialogue.catalogue import TraitCatalogue
from dialogue.manager import DialogueManager
from .chat import create_app, instructions


class InstructionsTest(unittest.TestCase):
    def setUp(self):
        self.catalogue = TraitCatalogue.load()

    def test_lists_every_trait_and_the_controls(self):
        text = instructions(self.catalogue)
        for trait in self.catalogue.keys:
            self.assertIn(trait, text)
        for phrase in ("Another one", "harsher", "go easy", "Drop the musical part", "instead",
                       "generic roast", "cancel", "reset", "bye", "Poem generator"):
            self.assertIn(phrase, text)

    def test_app_builds_with_the_panel(self):
        pipeline = Mock(catalogue=self.catalogue, system="A", manager=DialogueManager(self.catalogue))
        demo = create_app(pipeline)
        labels = [getattr(block, "label", None) for block in demo.blocks.values()]
        self.assertIn("How to use", labels)
        self.assertIn("Roast conversation", labels)


if __name__ == "__main__":
    unittest.main()
