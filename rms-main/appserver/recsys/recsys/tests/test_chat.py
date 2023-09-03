import time
from django.test import TestCase
from django.test.client import Client
from django.urls import reverse
import json

from recsys.chat import ChatGLM130B, ChatGPT, ChatWithUser


class TestChatGLM130B(TestCase):

    def setUp(self) -> None:
        super(TestChatGLM130B, self).setUp()
        self.chat_glm = ChatGLM130B()

    def test_get_answer(self):
        prompt = "what is bfs?"
        resp = self.chat_glm.get_answer(prompt)
        print(resp)
        self.assertTrue(resp['is_ok'])

    def test_get_answer_sse(self):
        #prompt = "what is bfs?"
        #prompt = "计算机视觉方向的论文在图像分类、目标检测、图像分割等任务上取得了哪些重要的成果？"
        prompt = "Transformer 来源于哪篇论文，哪年提出来的?"
        message = ""
        r = self.chat_glm.get_answer_stream(prompt)
        for resp in r:
            print(resp)
            self.assertTrue(resp['is_ok'])
            message += resp['data']['message']
            if resp['data']['event'] == 'finish':
                break
        
        print("message: ", message)
        



class TestChatGPT(TestCase):

    def setUp(self) -> None:
        super(TestChatGPT, self).setUp()
        self.chat_gpt = ChatGPT()

    def test_get_answer(self):
        prompt = "what is bfs?"
        resp = self.chat_gpt.get_answer(prompt)
        print(resp)
        self.assertTrue(resp['is_ok'])


class TestChatWithUser(TestCase):

    def setUp(self) -> None:
        super(TestChatWithUser, self).setUp()
        self.uid = "625697f2a0acf24a902eb356"
        self.chat_with_user = ChatWithUser(self.uid)

    def test_receive_message(self):
        prompt = "what is bfs?"
        resp = self.chat_with_user.receive_message(prompt)
        print(resp)
        self.assertTrue(resp['is_ok'])
    
    def test_receive_message_stream(self):
        #prompt = "Transformer 来源于哪篇论文，哪年提出来的?"
        prompt = "计算机视觉方向的论文在图像分类、目标检测、图像分割等任务上取得了哪些重要的成果？"
        for resp in self.chat_with_user.receive_message_stream(prompt):
            ts = round(time.time(), 3)
            print(f"{ts} -> {resp}")
            self.assertTrue(resp['is_ok'])
            self.assertGreater(resp['data']['round_id'], 0)
    
    def test_receive_message_stream_with_round_id(self):
        #prompt = "计算机视觉方向的论文在图像分类、目标检测、图像分割等任务上取得了哪些重要的成果？"
        prompt = "What are the ways to combine knowledge graph and big models?"
        round_id = 0
        for resp in self.chat_with_user.receive_message_stream(prompt):
            round_id = resp['data']['round_id']

        for resp in self.chat_with_user.receive_message_stream(prompt, round_id):
            print(f"{time.time()} -> {resp}")
            self.assertTrue(resp['is_ok'])
            self.assertGreater(resp['data']['round_id'], 0)
