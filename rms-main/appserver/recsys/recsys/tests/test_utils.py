from django.test import TestCase

from recsys import utils


class TestViews(TestCase):

    def setUp(self) -> None:
        super(TestViews, self).setUp()

    def test_is_chinese(self):
        source = "你好"
        self.assertEqual(utils.is_chinese(source), True)

    def test_not_is_chinese(self):
        source = "hello"
        self.assertEqual(utils.is_chinese(source), False)


class TestYoudao(TestCase):

    def setUp(self) -> None:
        return super().setUp()
    
    def tearDown(self) -> None:
        return super().tearDown()
    
    def test_translate_to_chinese(self):
        q = 'what is BFS?'
        q_ch = utils.YoudaoTranslate().translate_to_chinese(q)
        self.assertNotEqual(q, q_ch)
        
