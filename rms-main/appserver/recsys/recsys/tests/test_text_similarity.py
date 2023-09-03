from django.test import TestCase
import numpy as np

from recsys.algorithms.text_similarity import TextSimilarity


class TestTextSimilarity(TestCase):

    def setUp(self) -> None:
        super(TestTextSimilarity, self).setUp()

    def test_get_similarity(self):
        test_sentences = [
            "Semantic-aware aircraft trajectory prediction using flight plans",
            "Universal Law In The Crude Oil Market Based On Visibility Graph Algorithm And Network Structure",
            "Graft: A graph based time series data mining framework"
        ]
        model = TextSimilarity()
        model.train(test_sentences)
        sim = model.get_similarity("Modeling Relational Data with Graph Convolutional Networks", "graph is ok")
        print(f"similarity {sim}")
        self.assertGreater(sim, 0)
