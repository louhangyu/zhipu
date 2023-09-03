import pprint

from recsys.models import HotPaper
from recsys.algorithms.redis_connection import RedisConnection
from recsys.algorithms.constants import Constants
from recsys.algorithms.aggregate import Aggregate

from django.utils import timezone
from django.db import connection
import json
import math


class MakeTop:

    def __init__(self):
        self.redis_key = "top:paper:v1"
        self.redis_conn = RedisConnection.get_default()
        self.redis_cache_time = 3600*24

    def train(self):
        current_time = timezone.now()
        hot_papers = HotPaper.objects.filter(is_top=True, top_start_at__lte=current_time, top_end_at__gte=current_time)
        print("Current time {}, hot papers count {}, query {}".format(current_time, len(hot_papers), hot_papers.query))
        items = []
        agg = Aggregate()
        for h in hot_papers:
            item = self.hot_paper_to_dict(h)
            items.append(item)
            print(item)
            if item['category'] == HotPaper.CATEGORY_PUB:
                pub = agg.preload_pub(item['pub_id'], False)
                pprint.pprint(pub)

        self.redis_conn.setex(self.redis_key, self.redis_cache_time, json.dumps(items))
        return items

    @classmethod
    def hot_paper_to_dict(cls, h: HotPaper) -> dict:
        item = {
            'category': h.category,
            "pub_id": h.pub_id,
            "top_reason_zh": h.top_reason_zh,
            "top_reason_en": h.top_reason_en,
            "video_url": h.video_url,
            "pub_topic_id": h.pub_topic_id,
            'ai2k_id': h.ai2k_id,
            'ai2k_title': h.ai2k_title,
            'ai2k_description': h.ai2k_description,
            'ai2k_authors': h.get_ai2k_authors_list(),
            'ts': int(h.create_at.timestamp()),
        }
        return item

    def fetch(self):
        """ Fetch today top from redis server
        :return: [{item: str, type: str, score: float, recall_type: str, recall_reason: str}]
        """
        raw = self.redis_conn.get(self.redis_key)
        if not raw:
            return []
        data = json.loads(raw)
        items = []
        for r in data:
            item = self.pack_recommend_item(r)
            items.append(item)
        
        items = sorted(items, key=lambda x: x['score'], reverse=True)
        return items

    @classmethod
    def pack_recommend_item(cls, hot_paper: dict) -> dict:
        """ Pack item for recommendation
        :param hot_paper: {pub_id: str, top_reason_zh: str, top_reason_en: str}
        :return:
          {
              item: str,
              type: str,
              score: float,
              recall_type: str,
              reason_reason: {
                zh: str,
                en: str
              },
              video_url: str
          }
        """
        if hot_paper['category'] == HotPaper.CATEGORY_TOPIC:
            item_id = hot_paper['pub_topic_id']
            item_type = Constants.ITEM_PUB_TOPIC
        elif hot_paper['category'] == HotPaper.CATEGORY_AI2K:
            item_id = hot_paper['ai2k_id']
            item_type = Constants.ITEM_AI2K
        else:
            item_id = hot_paper['pub_id']
            item_type = Constants.ITEM_PUB

        interval = timezone.now().timestamp() - hot_paper.get('ts', 0)
        score = 1.0 - 1.0 / math.exp(math.log(interval + 2))

        item = {
            "item": item_id,
            "type": item_type,
            "score": score,
            "recall_type": Constants.RECALL_TOP,
            "recall_reason": {
                'zh': hot_paper['top_reason_zh'],
                'en': hot_paper['top_reason_en'],
            },
            "video_url": hot_paper.get('video_url'),
            'ai2k_id': hot_paper.get('ai2k_id'),
            'ai2k_title': hot_paper.get('ai2k_title'),
            'ai2k_description': hot_paper.get('ai2k_description'),
            'ai2k_authors': hot_paper.get('ai2k_authors'),
        }
        return item
