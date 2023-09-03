import datetime
import requests
import logging
import uuid
import json
import time
from typing import Iterator
import asyncio
from asgiref.sync import sync_to_async

from zhipu.api_request import getToken

from recsys.models import ChatRound
from recsys.ann import PaperVectorIndex, PaperIndex, PaperGPTVectorIndex
from recsys.algorithms.aggregate import Aggregate
from recsys.algorithms import get_cross_model
from recsys.utils import translate_to_chinese, translate_to_english, YoudaoTranslate
from recsys.text_segment import TextSegment

from django.utils import timezone


logger = logging.getLogger(__name__)


class ChatGLM130B:

    def __init__(self, temperature: float = 0.6, top_p: float = 0.6, timeout: int = 60, no_risk=False) -> None:
        self.temperature = temperature
        if self.temperature < 0 or self.temperature > 1.0:
            raise ValueError("temperature must between 0.0 and 1.0")
        self.top_p = top_p
        if self.top_p < 0 or self.top_p > 1.0:
            raise ValueError("top_p must between 0.0 and 1.0")
        self.no_risk = no_risk
        self.url = 'https://maas.aminer.cn/api/paas/model/v1/open/engines/chatGLM/chatGLM'
        #self.url_sse = "https://maas.aminer.cn/api/paas/model/v1/open/engines/sse/chatGLM/chatGLM"
        self.url_sse = "https://open.bigmodel.cn/api/paas/v3/model-api/chatglm_130b/sse-invoke"
        self.token_url = "https://maas.aminer.cn/api/paas/passApiToken/createApiToken"
        self.timeout = timeout
        self.apikey = "ed83262133184bfe9a443f918b0bdbb3"
        self.public_key= "MFwwDQYJKoZIhvcNAQEBBQADSwAwSAJBAIHYPqz3ZIo1hh2PONPfIX2h/70LrvMiAwfLVCnU/cdAUQWMI5h0s1aZ4ywe5vJ0LeW8O8D3C0d21OCFEfe3PVkCAwEAAQ=="
        self.token = ""
        self.max_token = 1024
        self.load_token()

    def load_token(self):
        resp_data = getToken(self.apikey, self.public_key)
        if resp_data['code'] != 200:
            raise ValueError(f"resp code {resp_data['code']} is not 200, error msg {resp_data['msg']}")
        self.token = resp_data['data']
        logging.info(f"token is {self.token}")
        return self.token

    def get_answer(self, prompt:str, history: list[str] = []) -> dict:
        """Get answer from GLM 130B. GLM API response:
            {
                "code": 200,  
                "msg": "成功", 
                "data": {
                        "prompt": "他之前担任什么职务？",  
                        "outputText": "王先生于 2022 年 2 月担任某某大学党委副书记、校长 (副部长级)。他此前曾在某某大学电子工程系担任党委副书记、副主任、主任，信息科学技术学院副院长，人事处处长、人才资源开发办公室主任，校长助理，校党委常委、副校长、常务副校长、秘书长、机关党委书记等职。他的研究方向为信号与信息处理，曾获得北京市科技进步二等奖、中国船舶工业总公司科技进步二等奖、国家教委科技进步三等奖等奖励。", 
                        "inputTokenNum": null,  
                        "outputTokenNum": null, 
                        "totalTokenNum": 93,  
                        "requestTaskNo": "1542097269879345154",
                        "taskOrderNo": "51507247240199147520", 
                        "taskStatus": "SUCCESS"
                        }, 
                "success": true
            }

        Args:
            history (list[str]): list of history message 
            prompt (str): user prompt

        Returns:
            dict: {
                "data": {
                    "message": str, #返回消息
                    "pubs": [
                        {"pub_id": str, "title": str}
                    ]
                },
                "is_ok": true|false,  # true：代表成功，false：代表失败
                "error_msg": str,     # 错误信息,
                "error_code": int,    # 错误码
            }

        """
        if len(history) % 2 != 0:
            raise ValueError("the length of history must be even")
        
        headers = {
            "Authorization": self.token,
        }
        prompt = self._shrink_prompt(prompt)
        body = {
            "temperature": self.temperature,
            "top_p": self.top_p,
            "prompt": prompt,
            "history": history,
            "requestTaskNo": str(uuid.uuid4()),
        }
        url = self.url
        
        try:
            r = requests.post(url, json=body, headers=headers, timeout=self.timeout)
        except Exception as e:
            logger.warning(f"except when post {body}: {e}")
            return {"data": {}, "is_ok": False, "error_code": 504, "error_msg": str(e)}
        
        if r.status_code != 200:
            return {"data": {}, "is_ok": False, "error_code": r.status_code, "error_msg": f"GLM {body['requestTaskNo']} status code {r.status_code} is not 200 ok"}

        resp_data = r.json()
        if resp_data['success'] is False:
            return {"data": {}, "is_ok": False, "error_code": resp_data['code'], "error_msg": resp_data['msg']}

        resp = {
            "is_ok": resp_data['success'],
            "error_code": resp_data['code'],
            "error_msg": resp_data['msg'],
            "data": {
                "message": resp_data['data']['outputText'].strip(),
            }
        }
        return resp
    
    def get_answer_stream(self, prompt:str, history: list[str] = []) -> Iterator:
        """Get answer from GLM 130B SSE API. 
        Args:
            history (list[str]): list of history message 
            prompt (str): user prompt

        Returns:
            dict: {
                "data": {
                    "message": str, #返回消息
                },
                "is_ok": true|false,  # true：代表成功，false：代表失败
                "error_msg": str,     # 错误信息,
                "error_code": int,    # 错误码
            }

        """
        if len(history) % 2 != 0:
            raise ValueError("the length of history must be even")
        
        headers = {
            "Authorization": self.token,
        }
        prompt = self._shrink_prompt(prompt)
        body = {
            "temperature": self.temperature,
            "top_p": self.top_p,
            "prompt": [
                {
                    'role': 'user',
                    'content': prompt,
                }
            ],
            "incremental": True,
            "sseFormat": "data",
        }
        url = self.url_sse
        start_time = time.time()
        try:
            r = requests.post(url, json=body, headers=headers, timeout=self.timeout, stream=True)
        except Exception as e:
            logger.warning(f"except when post {body}: {e}")
            yield {"data": {'event': 'finish'}, "is_ok": False, "error_code": 504, "error_msg": str(e)}
        
        if r.status_code != 200:
            yield {"data": {'event': 'finish'}, "is_ok": False, "error_code": r.status_code, "error_msg": f"GLM {body['requestTaskNo']} status code {r.status_code} is not 200 ok"}
        else:
            buf = []
            #prev_messsage = ''
            # response two \n first
            for _ in range(2):
                yield  {
                    "is_ok": True,
                    "error_code": 200,
                    "error_msg": '',
                    'data': {
                        'message': '\n',
                        'event': "add",
                    }
                }

            for line in r.iter_lines(decode_unicode=True):
                logger.info(f"recv line from sse \"{line}\"") 
                if line == "" and len(buf) > 0:
                    data = {
                        'message': ''
                    }
                    for buf_line in buf:
                        seperator_idx = buf_line.find(":")
                        name = buf_line[:seperator_idx]
                        value = buf_line[seperator_idx+1:]
                        if name == "data":
                            msg = json.loads(value)['data']
                            data['message'] += msg
                        elif name == "meta":
                            data[name] = json.loads(value)
                        else:
                            data[name] = value
                    # yield by characters
                    #if prev_messsage == "\n" and data['message'][0] != prev_messsage:
                    #    new_chars = data['message']
                    #else:
                    #    new_chars = data['message'][len(prev_messsage):]
                    new_chars = data['message']
                    if len(new_chars) > 0:
                        for i, c in enumerate(new_chars):
                            resp = {
                                'is_ok': True,
                                'data': {
                                    'message': c,
                                    'event': "add",
                                    'spend_seconds': time.time() - start_time
                                }
                            }
                            yield resp
                    else:
                        if 'event' in data and data['event'] == "finish":
                            resp = {
                                "is_ok": True,
                                "error_code": 200,
                                "error_msg": '',
                                'data': {
                                    'message': '',
                                    'event': "finish",
                                }
                            }
                            yield resp

                    logger.info(f"new chars \"{new_chars}\", data {data}")
                    buf = []
                    #prev_messsage = data['message']
                else:
                    buf.append(line)

    def _shrink_prompt(self, prompt:str) -> str:
        num_tokens = len(prompt)
        if num_tokens < self.max_token:
            return prompt
        
        sep_idx = int(self.max_token / 2)
        tokens = prompt.split(" ")
        return " ".join(tokens[:sep_idx])
    

class ChatGPT:

    def __init__(self, timeout=60) -> None:
        '''
        '''
        self.url = 'https://searchtest.aminer.cn/aminer-operation/web/chatGpt/getChatGptResponse'
        self.timeout = timeout
    
    def get_answer(self, prompt: str, history: list[str] = []) -> dict:
        """Get answer from ChatGPT. ChatGPT API response:
        
        curl --location --request POST 'https://searchtest.aminer.cn/aminer-operation/web/chatGpt/getChatGptResponse' \
            --header 'Content-Type: application/json' \
            --data-raw '{
                "model": "gpt-3.5-turbo",
                "messages": [
                    {
                    "role": "user",
                    "content": "国际法律事务:当私募基金在国际市场上涉及到国际税收协定时，您将如何协助基金管理人处理相关国际税收法律问题？"
                    }
                ]
            }'

        Args:
            history (list[str]): list of history message 
            prompt (str): user prompt

        Returns:
            dict: {
                "data": {
                "message": str, #返回消息
                "pubs": [
                    {"pub_id": str, "title": str}
                ]
                },
                "is_ok": true|false,  # true：代表成功，false：代表失败
                "error_msg": str,     # 错误信息,
                "error_code": int,    # 错误码
            }
        """
        headers = {
            "Content-Type": 'application/json',
        }
        body = {
            "model": "gpt-3.5-turbo",
            "messages": []
        }
        body['messages'].append({"role": "user", "content": prompt})

        for h in history:
            body['messages'].append({"role": "user", "content": h})
        
        try:
            r = requests.post(self.url, json=body, headers=headers, timeout=self.timeout)
        except Exception as e:
            logger.warning(f"except when post {body}: {e}")
            return {"data": {}, "is_ok": False, "error_code": 504, "error_msg": str(e)}
        
        if r.status_code != 200:
            return {"data": {}, "is_ok": False, "error_code": r.status_code, "error_msg": r.text}

        resp_data = r.json()
        logger.info(f"post {body}, resp {resp_data}")
        resp = {
            "is_ok": resp_data['success'],
            "error_code": resp_data['code'],
            "error_msg": resp_data['msg'],
            "data": {
                "message": resp_data['data']['choices'][0]['message']['content'].strip(),
            }
        }
        return resp


class AutoAPI:

    def __init__(self, timeout=60) -> None:
        '''
        '''
        #self.url = 'https://searchtest.aminer.cn/aminer-operation/web/chatGpt/getChatGptResponse'
        #self.url = "http://reader.wyc-personal.cn:9002/api/AMiner"
        self.url = "http://10.10.0.29:9002/api/AMiner/answer"
        self.timeout = timeout
    
    def get_answer(self, query: str) -> dict:
        """Get answer from AutoAPI. Response:
            {
                'message': bool,
                'result': str
            }

        Args:
            query (str): user prompt

        Returns:
            dict: {
                "data": {
                    "message": str, #返回消息
                },
                "is_ok": true|false,  # true：代表成功，false：代表失败
                "error_msg": str,     # 错误信息,
                "error_code": int,    # 错误码
            }
        """
        headers = {
            "Content-Type": 'application/json',
        }
        params = {'query': query}
        try:
            r = requests.get(self.url, params=params, headers=headers, timeout=self.timeout)
        except Exception as e:
            logger.warning(f"except when get {params}: {e}")
            return {"data": {}, "is_ok": False, "error_code": 504, "error_msg": str(e)}
        
        if r.status_code != 200:
            return {"data": {}, "is_ok": False, "error_code": r.status_code, "error_msg": f"AutoAPI status code {r.status_code} is not 200 ok"}

        resp_data = r.json()
        logger.info(f"get {params}, resp {resp_data}")
        
        if resp_data['message'] == "success":
            is_ok = True
        else:
            is_ok = False

        resp = {
            "is_ok": is_ok,
            "error_code": 0,
            "error_msg": "",
            "data": {
                "message": resp_data['result'],
            }
        }
        return resp
    

class TaskClassify:
    TASK_NONE = -1
    TASK_PERSON = 0
    TASK_SUMMARY = 1
    TASK_DETAIL = 2
    TASK_DERIVATIVE = 3

    def __init__(self, timeout=5) -> None:
        self.timeout = timeout
        self.url = "http://10.10.0.22:4998/sileishiti"

    def classify(self, message:str) -> int:
        headers = {
            "Content-Type": 'application/json',
        }
        message_zh = YoudaoTranslate().translate_to_chinese(message)
        body = {
            "text": message_zh 
        }
        try:
            r = requests.post(self.url, json=body, headers=headers, timeout=self.timeout)
        except Exception as e:
            logger.warning(f"except when post {body}: {e}")
            return self.TASK_NONE 
        
        if r.status_code != 200:
            logger.warning(f"{self.url} response status code {r.status_code} is not 200 ok")
            return self.TASK_NONE 

        resp_data = r.json()
        logger.info(f"post {body}, resp {resp_data}")
        resp_result = resp_data['result']
        if resp_result == self.TASK_SUMMARY:
            return self.TASK_SUMMARY
        elif resp_result == self.TASK_DETAIL:
            return self.TASK_DETAIL
        elif resp_result == self.TASK_DERIVATIVE:
            return self.TASK_DERIVATIVE
        elif resp_result == self.TASK_PERSON:
            return self.TASK_PERSON
        else:
            return self.TASK_NONE 


class ChatWithUser:

    def __init__(self, uid: str) -> None:
        self.uid = uid
        self.rounds: list[ChatRound] = [] # sort by create time ascend
        self.last_time = timezone.now() - datetime.timedelta(1)
        self.paper_index = PaperIndex(timeout=10)
        self.paper_vector_contrieve_index = PaperVectorIndex(prev_days=365*5)
        self.paper_vector_gpt_index = PaperGPTVectorIndex(prev_days=365*5)
        self.chat_service = ChatGLM130B(no_risk=False, timeout=60)
        self.auto_api = AutoAPI(timeout=60)
        self.classify_service = TaskClassify(timeout=5)

    def _load_history_rounds(self):
        self.rounds = ChatRound.objects.filter(uid=self.uid).filter(create_at__gt=self.last_time).order_by("create_at")
        logger.info(f"load {len(self.rounds)} rounds of uid {self.uid}")

    def _fetch_related_pubs(self, message: str, k:int=3, append_keyword_recall:bool=True, assistant_message:str="") -> list[dict]:
        """Returns: list of pubs {id: str, title: str, abstract: str}
        """
        start_time = time.time()
        if append_keyword_recall:
            keyword_candidates = self._fetch_pubs_from_keyword(message, k)
        else:
            keyword_candidates = []
        logger.info(f"spends {time.time() - start_time}s to fetch pubs from keyword, message {message}")

        start_time = time.time()
        sematic_candidates = self._fetch_pubs_from_gpt(message, k)
        logger.info(f"spends {time.time() - start_time}s to fetch pubs from gpt, message {message}")
        if not sematic_candidates:
            start_time = time.time()
            sematic_candidates = self._fetch_pubs_from_contrieve(message, k)
            logger.info(f"spends {time.time() - start_time}s to fetch pubs from contrieve, message {message}")

        result = keyword_candidates + sematic_candidates
        return result
    
    def _fetch_pubs_from_keyword(self, message: str, k:int=6) -> list[dict]:
        agg = Aggregate()
        
        #remove stop words
        start_time = time.time()
        logger.info(f"{message} ready to remove stop words")
        text_segment = TextSegment(pos=True)
        message_tokens = text_segment.segment(message, remove_stopword=True)
        clean_message = " ".join([x[0] for x in message_tokens])
        logger.info(f"{message} remove stop words done, spend {time.time() - start_time}")

        start_time = time.time()
        en_message = YoudaoTranslate().translate_to_english(clean_message)
        if not en_message:
            en_message = message
        logger.info(f"{message} translate done, spend {time.time() - start_time}")
        start_time = time.time()
        
        neighbours = self.paper_index.search_by_dict({'title': en_message}, k=10*k)
        logger.info(f"{message} search done, spend {time.time() - start_time}")
        if not neighbours:
            return []

        result = []
        for item in neighbours:
            pub_id = item[0]
            score = item[1]
            pub = agg.preload_pub(pub_id)
            if not pub:
                logger.warning(f"pub {pub_id} is not found")
                continue
            result.append({
                "pub_id": pub["id"],
                "title": pub['title'] or pub.get('title_zh') or '',
                'abstract': pub['abstract'] or pub.get('abstract_zh') or '',
                'year': pub['year'],
                'pdf': pub.get('pdf'),
                'venue': pub['venue'],
                'authors': pub['authors'],
                'score': score,
                'recall_from': "keyword",
            })

        result = result[:k]
        logger.info(f"message {message}, clean message {clean_message} related pubs {result}")
        return result
    
    def _fetch_pubs_from_contrieve(self, message: str, k:int=6) -> list[dict]:
        agg = Aggregate()
        neighbours = self.paper_vector_contrieve_index.search_by_dict({"title": message, "abstract": ""}, k=3*k)
        if not neighbours:
            return []

        #resort neighbours
        cross_model = get_cross_model()
        candidates = []
        for neighbour in neighbours:
            pub_id = neighbour[0]
            pub = agg.preload_pub(pub_id)
            if not pub:
                candidates.append((message, ""))
            else:
                content = "\n".join([
                    pub['title'] or pub.get('title_zh') or "",
                    pub['abstract'] or pub.get('abstract_zh') or "",
                    f"Published at {pub['year']}",
                    "Authors are {}".format(", ".join([x.get('name') or x.get('name_zh') or '' for x in pub['authors']])),
                    "Organizations are {}".format(", ".join([x.get('org') or x.get('org_zh') or '' for x in pub['authors']]))
                ])
                candidates.append((message, content))
        scores = cross_model.predict(candidates)

        sorted_neighbours = []
        for i in range(len(candidates)):
            pub_id = neighbours[i][0]
            score = scores[i].astype(float)
            sorted_neighbours.append((pub_id, score))
        sorted_neighbours = sorted(sorted_neighbours, key=lambda x: x[1], reverse=True)[:k]

        result = []
        for item in sorted_neighbours:
            pub_id = item[0]
            score = item[1]
            pub = agg.preload_pub(pub_id)
            if not pub:
                logger.warning(f"pub {pub_id} is not found")
                continue
            result.append({
                "pub_id": pub["id"],
                "title": pub['title'] or pub.get('title_zh') or '',
                'abstract': pub['abstract'] or pub.get('abstract_zh') or '',
                'year': pub['year'],
                'pdf': pub.get('pdf'),
                'venue': pub['venue'],
                'authors': pub['authors'],
                'score': score,
                'recall_from': "sematic",
            })

        result = result[:k]
        logger.info(f"\"{message}\" contrieve related pubs {result}")
        return result
    
    def _fetch_pubs_from_gpt(self, message: str, k:int=6) -> list[dict]:
        agg = Aggregate()
        start_time = time.time()
        neighbours = self.paper_vector_gpt_index.search_by_dict({"title": message, "abstract": ""}, k=k)
        logger.info(f"message {message}, spends {time.time() - start_time}s")
        if not neighbours:
            logger.warning(f"\"{message}\" neighbours are empty")
            return []
        
        start_time = time.time()
        result = []
        for item in neighbours:
            pub_id = item[0]
            score = item[1]
            pub = agg.preload_pub(pub_id)
            if not pub:
                logger.warning(f"pub {pub_id} is not found")
                continue
            result.append({
                "pub_id": pub["id"],
                "title": pub['title'] or pub.get('title_zh') or '',
                'abstract': pub['abstract'] or pub.get('abstract_zh') or '',
                'pdf': pub.get('pdf'),
                'year': pub['year'],
                'venue': pub['venue'],
                'authors': pub['authors'],
                'score': score,
                'recall_from': "semantic_gpt",
            })

        result = result[:k]
        logger.info(f"\"{message}\" gpt related pubs {result}, spends {time.time() - start_time}s")
        return result

    def receive_message(self, message: str, round_id:int=None) -> dict:
        """
        Returns:
            dict: {
                "data": {
                    "id": int, 
                    "message": str, #返回消息
                    "pubs": [
                        {"pub_id": str, "title": str}
                    ]
                },
                "is_ok": true|false,  # true：代表成功，false：代表失败
                "error_msg": str,     # 错误信息,
                "error_code": int,    # 错误码
            }
        """
        start_time = time.time()
        if not message:
            return {"is_ok": False, "error_msg": "message is empty", "error_code": 403}
        
        classification = -1
        pubs = []
        if round_id:
            classification = self.classify_service.classify(message)
            if classification in [TaskClassify.TASK_DERIVATIVE, TaskClassify.TASK_PERSON]:
                prompt = message
                resp = self.auto_api.get_answer(prompt)
            else:
                pubs = self._fetch_related_pubs(message, assistant_message="")
                prompt = f"\"{message}\", 请根据以下内容用中文简明扼要回答:\n"
                for pub in pubs:
                    prompt += "\n".join([
                        pub['title'] or '', 
                        pub['abstract'] or '', 
                        'Authors: {}'.format([x.get('name') or x.get("name_zh") or '' for x in pub['authors']]),
                        "Journal (or Conference): {}".format(pub['venue']['info']['name']),
                        f'Published year: {pub["year"]}',
                    ]) 
                resp = self.chat_service.get_answer(prompt)
        else:
            prompt = message
            resp = self.chat_service.get_answer(prompt)

        if resp['is_ok'] is False:
            return resp
        
        end_time = time.time()
        
        assistant_messsage = resp['data']['message']
        # save
        spend_seconds = end_time - start_time
        if round_id:
            chat_round = ChatRound.objects.get(id=round_id)
            chat_round.assistant_extend_message = assistant_messsage
            chat_round.user_pubs = pubs
            chat_round.extend_spend_seconds = spend_seconds
            chat_round.save()
        else:
            chat_round = ChatRound.objects.create(
                uid=self.uid, 
                user_message=message, 
                assistant_message=assistant_messsage, 
                user_pubs=pubs,
                spend_seconds=spend_seconds
            )
        self.rounds.append(chat_round)
        resp['data']['pubs'] = pubs
        resp['data']['prompt'] = prompt
        resp['data']['classification'] = classification
        resp['data']['round_id'] = chat_round.id
        resp['spend_seconds'] = spend_seconds
        return resp

    def receive_message_stream(self, message: str, round_id:int=None):
        """ Generator.
        Returns: 
            {
                "data": {
                    "id": int, 
                    "message": str, #返回消息
                    "pubs": [
                        {"pub_id": str, "title": str}
                    ]
                },
                "is_ok": true|false,  # true：代表成功，false：代表失败
                "error_msg": str,     # 错误信息,
                "error_code": int,    # 错误码
            }
        """
        if not message:
            yield {"is_ok": False, "error_msg": "message is empty", "error_code": 403, 'data': {'event': 'finish'}}
        else:
            classification = -1
            pubs = []
            assistant_messsage = ''
            if round_id:
                start_time = time.time()
                classification = self.classify_service.classify(message)
                classification_spends = time.time() - start_time
                if classification in [TaskClassify.TASK_DERIVATIVE, TaskClassify.TASK_PERSON]:
                    prompt = message
                    resp = self.auto_api.get_answer(prompt)
                    if resp['is_ok']:
                        assistant_messsage = resp['data']['message']
                    resp['data']['event'] = 'finish' 
                    resp['data']['pubs'] = pubs
                    resp['data']['prompt'] = prompt
                    resp['data']['classification'] = classification
                    resp['data']['round_id'] = round_id
                    yield resp
                else:
                    start_time = time.time()
                    pubs = self._fetch_related_pubs(message, assistant_message="")
                    fetch_related_pubs_spends = time.time() - start_time
                    prompt = f"\"{message}\", 请根据以下内容用中文简明扼要回答:\n"
                    for pub in pubs:
                        prompt += "\n".join([
                            pub['title'] or '', 
                            pub['abstract'] or '', 
                            'Authors: {}'.format([x.get('name') or x.get("name_zh") or '' for x in pub['authors']]),
                            "Journal (or Conference): {}".format(pub['venue']['info']['name']),
                            f'Published year: {pub["year"]}',
                        ]) 
                    
                    for resp in self.chat_service.get_answer_stream(prompt):
                        if resp['is_ok']:
                            assistant_messsage += resp['data']['message']
                        resp['data']['round_id'] = round_id
                        resp['data']['classify_spends'] = classification_spends
                        resp['data']['fetch_related_pubs_spends'] = fetch_related_pubs_spends 
                        if 'event' in resp['data'] and resp['data'].get('event') == "finish":
                            resp['data']['pubs'] = pubs
                            resp['data']['prompt'] = prompt
                            resp['data']['classification'] = classification
                        yield resp
                    
                chat_round = ChatRound.objects.get(id=round_id)
                chat_round.assistant_extend_message = assistant_messsage
                chat_round.user_pubs = pubs
                chat_round.extend_spend_seconds = time.time() - start_time
                chat_round.save()
                self.rounds.append(chat_round)
            else:
                start_time = time.time()
                chat_round = ChatRound.objects.create(
                    uid=self.uid, 
                    user_message=message, 
                    assistant_message=assistant_messsage, 
                    user_pubs=pubs,
                    spend_seconds=time.time() - start_time
                )
                chat_round_create_spend = time.time() - start_time
                prompt = message
                for resp in self.chat_service.get_answer_stream(prompt):
                    if resp['is_ok']:
                        assistant_messsage += resp['data']['message']
                    resp['data']['round_id'] = chat_round.id 
                    resp['data']['chat_round_create_spend'] = chat_round_create_spend
                    if 'event' in resp['data'] and resp['data'].get('event') == "finish":
                        resp['data']['pubs'] = pubs
                        resp['data']['prompt'] = prompt
                        resp['data']['classification'] = classification
                    yield resp

                chat_round.spend_seconds = time.time() - start_time
                chat_round.assistant_message = assistant_messsage
                chat_round.save()
                self.rounds.append(chat_round)
