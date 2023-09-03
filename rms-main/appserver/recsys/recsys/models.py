from pymongo import MongoClient
from bson.objectid import ObjectId
from urllib.parse import quote_plus
from django.conf import settings
from django.db import models
from django.db.models.signals import post_save
from django.core.exceptions import ValidationError
import random
import logging
    
from recsys.algorithms.constants import Constants
from recsys.utils import is_mongo_id


logger = logging.getLogger(__name__)


def validate_paper_id(value):
    if is_mongo_id(value) is False:
        raise ValidationError(f"{value} is not valid mongo id")
    return value


def validate_ai2k_authors(value):
    if not value:
        return value
    lines = value.split("\n")
    for line in lines:
        tmp = line.split("||")
        if len(tmp) != 4:
            raise ValidationError("At least three separators ||")
        # author_zh_name = tmp[0].strip()
        # author_en_name = tmp[1].strip()
        # author_org = tmp[2].strip()
        author_id = tmp[3].strip()
        if not is_mongo_id(author_id):
            raise ValidationError(f"{author_id} is not valid id")

    return value


class MongoConnection:

    def __init__(self, config=None, socket_timeout=300*1000):
        """
        :param config:
          [{
            'host': "192.168.6.208",
            'port': 37017,
            'authSource': "aminer",
            'user': "aminer_platform_reader",
            'password': "Reader@123",
          }, ....]
        """
        if not config:
            raise ValueError("config is none")

        self.config = config
        self.master_client = None

        for i in range(len(config)):
            reader_idx = random.randint(0, len(config) - 1)
            user = config[reader_idx]['user']
            password = config[reader_idx]['password']
            auth_source = config[reader_idx]['authSource']
            host = config[reader_idx]['host']
            port = config[reader_idx]['port']
            self.uri = "mongodb://{}:{}@{}:{}/?authSource={}".format(quote_plus(user), quote_plus(password), host, port, auth_source)
            self.client = MongoClient(self.uri, unicode_decode_error_handler='ignore', socketTimeoutMS=socket_timeout)
            if self.is_active(self.client):
                logger.info(f"{self.uri} is active")
                break

    @classmethod
    def get_aminer_client(cls):
        return cls(config=settings.MONGO['aminer'])

    @classmethod
    def is_active(cls, client: MongoClient):
        try:
            client.admin.command('ping')
        except Exception as e:
            logger.warning("server {} not available: {}".format(client.address, e))
            return False

        return True

    def initial_master_client(self):
        if self.master_client:
            return self.master_client
        master_idx = 0
        config = self.config
        user = config[master_idx]['user']
        password = config[master_idx]['password']
        auth_source = config[master_idx]['authSource']
        host = config[master_idx]['host']
        port = config[master_idx]['port']
        uri = "mongodb://{}:{}@{}:{}/?authSource={}".format(quote_plus(user), quote_plus(password), host, port, auth_source)
        self.master_client = MongoClient(uri, unicode_decode_error_handler='ignore')
        if not self.is_active(self.master_client):
            logger.warning(f"master {uri} is not active")
            self.master_client = None

        return self.master_client

    def find(self, db_name, doc_name, *args, **kwargs):
        db = self.client[db_name]
        doc = db[doc_name]
        cursor = doc.find(*args, **kwargs)
        items = []
        for item in cursor:
            items.append(item)
        logger.info("{}.{}.{} =>count {}".format(db_name, doc_name, args, len(items)))
        return items

    def distinct(self, db_name, doc_name, field, query):
        """
        :param db_name:
        :param doc_name:
        :param field: which to return distinct values
        :param query: specifies the documents from which to retrieve the distinct values
        :return:
        """
        db = self.client[db_name]
        doc = db[doc_name]
        cursor = doc.distinct(field, query)
        items = []
        for item in cursor:
            items.append(item)
        logger.info("{}.{}.{} =>count {}".format(db_name, doc_name, field, len(items)))
        return items

    def find_by_id(self, db_name, doc_name, item_id, *args, **kwargs):
        if is_mongo_id(item_id) is False:
            logger.warning(f"item {item_id} is not valid mongo id")
            return []
        sql = {
            "_id": ObjectId(item_id)
        }
        items = self.find(db_name, doc_name, sql, *args, **kwargs)
        return items

    def find_by_ids(self, db_name, doc_name, item_ids, *args, **kwargs):
        item_ids = list(filter(lambda x: is_mongo_id(x), item_ids))
        sql = {
            "_id": {
                "$in": [ObjectId(item_id) for item_id in item_ids]
            }
        }
        items = self.find(db_name, doc_name, sql, *args, **kwargs)
        id_item_map = {}
        for item in items:
            id_item_map[str(item['_id'])] = item

        result = []
        for item_id in item_ids:
            if item_id not in id_item_map:
                continue
            result.append(id_item_map[item_id])

        return result

    def sort(self, db_name, doc_name, patterns, sort_condition1, sort_condition2, projection=None, limit=0):
        """
        :param db_name:
        :param doc_name:
        :param patterns:
        :param sort_condition1: [("field1", pymongo.ASCENDING or pymongo.DESCENDING)]
        :param sort_condition2: [("field1", pymongo.ASCENDING or pymongo.DESCENDING)]
        :param projection:
        :param limit:
        :return:
        """
        db = self.client[db_name]
        doc = db[doc_name]
        cursor = doc.find(patterns, projection).sort(sort_condition1, sort_condition2).limit(limit)

        items = []
        for item in cursor:
            items.append(item)

        logger.info("{}.{}.{} =>count {}".format(db_name, doc_name, patterns, len(items)))
        return items

    def close(self):
        self.client.close()

    def insert_one(self, db_name, doc_name, content, *args, **kwargs):
        if not self.initial_master_client():
            return None
        db = self.master_client[db_name]
        doc = db[doc_name]
        result = doc.insert_one(content, *args, **kwargs)
        return result.inserted_id


class ActionLog(models.Model):
    ACTION_SHOW = 1
    ACTION_CLICK = 2
    ACTION_SUBSCRIBE_KEYWORD = 3
    ACTION_SUBSCRIBE_SUBJECT = 4
    ACTION_FAVORITE = 5
    ACTION_COPY_TITLE = 6
    ACTION_SEARCH = 7

    TYPE_PUB = 1
    TYPE_PUB_TOPIC = 2
    TYPE_REPORT = 3
    TYPE_PROFILE = 4
    TYPE_AI2K = 6

    USER_HUMAN = 1
    USER_GOOGLE_BOT = 2

    uid = models.CharField(max_length=64, null=True, blank=True)
    ud = models.CharField(max_length=64, null=True, blank=True)
    ls = models.IntegerField(null=True, blank=True)
    ip = models.CharField(max_length=32, null=True, blank=True)
    pub_ids = models.CharField(max_length=4096, null=True, blank=True)
    keywords = models.CharField(max_length=4096, null=True, blank=True)
    action = models.SmallIntegerField()
    author_id = models.CharField(max_length=64, null=True, blank=True)
    abflag = models.CharField(max_length=12, null=True, blank=True)
    create_at = models.DateTimeField(auto_now_add=True)
    type = models.SmallIntegerField(default=TYPE_PUB)
    device = models.CharField(max_length=128, null=True, blank=True)
    first_reach = models.DateTimeField(null=True, blank=True)
    recall_type = models.CharField(max_length=32, blank=True, null=True)
    query = models.CharField(max_length=255, blank=True, null=True)

    @classmethod
    def str2action(cls, action):
        if action == "show":
            return cls.ACTION_SHOW
        elif action == "click":
            return cls.ACTION_CLICK
        elif action == "subscribe_keyword":
            return cls.ACTION_SUBSCRIBE_KEYWOR
        elif action == "subscribe_subject":
            return cls.ACTION_SUBSCRIBE_SUBJECT
        elif action == "favorite":
            return cls.ACTION_FAVORITE
        elif action == "copy_title":
            return cls.ACTION_COPY_TITLE
        elif action == "search":
            return cls.ACTION_SEARCH
        else:
            return None

    @classmethod
    def str2type(cls, type_str):
        from recsys.algorithms.aggregate import Aggregate

        if type_str == Aggregate.ITEM_PUB:
            return cls.TYPE_PUB
        elif type_str == Aggregate.ITEM_PUB_TOPIC:
            return cls.TYPE_PUB_TOPIC
        elif type_str == Aggregate.ITEM_REPORT:
            return cls.TYPE_REPORT
        elif type_str == "profile":
            return cls.TYPE_PROFILE
        elif type_str == Aggregate.ITEM_AI2K:
            return cls.TYPE_AI2K
        else:
            return 0

    @classmethod
    def get_user_type(cls, user_agent):
        pass


class AccessLogSnapshot(models.Model):
    happen_time = models.DateTimeField()
    business = models.CharField(max_length=16)
    total = models.IntegerField(default=0)
    status_200_number = models.IntegerField(default=0)
    status_5xx_number = models.IntegerField(default=0)
    resp_body_bytes_sum = models.PositiveBigIntegerField(default=0)
    resp_seconds_sum = models.FloatField(default=0.0)
    create_at = models.DateTimeField(auto_created=True, auto_now_add=True)

    def avg_resp_byte(self):
        return self.resp_body_bytes_sum / self.total

    def avg_resp_second(self):
        return self.resp_seconds_sum / self.total


class HotPaper(models.Model):
    DEVICES = (
        ("PC", "pc"),
        ("mini_program", "mini_program")
    )
    CATEGORY_PUB = "pub"
    CATEGORY_TOPIC = "topic"
    CATEGORY_AI2K = "ai2k"
    CATEGORIES = (
        (CATEGORY_PUB, "Pub"),
        (CATEGORY_TOPIC, "Topic"),
        (CATEGORY_AI2K, "AI2000"),
    )
    category = models.CharField(choices=CATEGORIES, max_length=32)
    pub_id = models.CharField(max_length=32, validators=[validate_paper_id], blank=True, null=True)
    interpret = models.TextField(null=True, blank=True)
    interpret_author = models.CharField(max_length=128, null=True, blank=True)
    video_url = models.TextField(null=True, blank=True, help_text="视频链接")
    report_id = models.CharField(max_length=24, null=True, blank=True)
    report_title = models.CharField(max_length=255, null=True, blank=True)
    report_from = models.CharField(max_length=64, null=True, blank=True)
    report_date = models.DateField(blank=True, null=True)
    is_top = models.BooleanField(default=False)
    display_device = models.CharField(blank=True, null=True, help_text="展示终端", choices=DEVICES, max_length=32)
    top_start_at = models.DateTimeField(blank=True, null=True, help_text="置顶开始时间")
    top_end_at = models.DateTimeField(blank=True, null=True, help_text="置顶结束时间")
    top_reason_zh = models.CharField(blank=True, null=True, help_text="中文置顶理由", max_length=250)
    top_reason_en = models.CharField(blank=True, null=True, help_text="英文置顶理由", max_length=250)
    pub_topic_id = models.CharField(max_length=32, null=True, blank=True, help_text="必读论文ID")
    ai2k_id = models.CharField(max_length=32, blank=True, null=True)
    ai2k_title = models.CharField(max_length=255, blank=True, null=True)
    ai2k_description = models.TextField(blank=True, null=True)
    ai2k_keywords = models.CharField(max_length=255, blank=True, null=True)
    ai2k_authors = models.TextField(blank=True, null=True, validators=[validate_ai2k_authors], help_text="一行一个作者，每行用'|｜'分开。示例：学者中文名||学者英文名||机构||学者ID")
    create_at = models.DateTimeField(auto_now_add=True)
    modify_at = models.DateTimeField(auto_now=True)

    def get_ai2k_authors_list(self):
        if not self.ai2k_authors:
            return []

        authors = []
        lines = self.ai2k_authors.split("\n")
        for line in lines:
            tmp = line.split("||")
            author_zh_name = tmp[0].strip()
            author_en_name = tmp[1].strip()
            author_org = tmp[2].strip()
            author_id = tmp[3].strip()
            authors.append({
                "id": author_id,
                'org': author_org,
                'name': author_en_name,
                'name_zh': author_zh_name
            })

        return authors


def hot_paper_saved_handler(sender, instance, created, raw, *args, **kwargs):
    from recsys.background import make_top_train
    make_top_train.delay()


post_save.connect(hot_paper_saved_handler, sender=HotPaper)


class ColdKeyword(models.Model):
    word = models.CharField(max_length=32)
    create_at = models.DateTimeField(auto_now_add=True)
    modify_at = models.DateTimeField(auto_now=True)


class Ad(models.Model):

    AD_TYPE_CHOICES = (
        (Constants.ITEM_AI2K, Constants.ITEM_AI2K),
    )
    ad_type = models.CharField(max_length=255, blank=True, null=True, choices=AD_TYPE_CHOICES)
    ad_id = models.CharField(max_length=255, blank=True, null=True)
    title = models.TextField()
    title_zh = models.TextField()
    keywords = models.TextField()
    url = models.URLField(max_length=4096)
    author_ids = models.TextField()
    total = models.IntegerField()
    desc = models.TextField()
    desc_zh = models.TextField()
    create_at = models.DateTimeField(auto_now_add=True)
    modify_at = models.DateTimeField(auto_now=True)


class Subject(models.Model):
    title = models.CharField(max_length=255)
    title_zh = models.CharField(max_length=255)
    keywords = models.TextField()
    keywords_zh = models.TextField()
    create_at = models.DateTimeField(auto_now_add=True)
    modify_at = models.DateTimeField(auto_now=True)


class HighQualityPaper(models.Model):
    paper_id = models.CharField(max_length=24, unique=True, validators=[validate_paper_id])
    title = models.CharField(max_length=255)
    tags = models.CharField(max_length=255, blank=True, null=True)
    abstract = models.TextField(blank=True, null=True)
    authors = models.CharField(max_length=255, blank=True, null=True)
    venue = models.CharField(max_length=255)
    affiliations = models.TextField(blank=True, null=True)
    subject_zh = models.CharField(max_length=128, blank=True, null=True)
    subject_en = models.CharField(max_length=128, blank=True, null=True)
    category = models.TextField(null=True, blank=True)
    year = models.IntegerField(null=True, blank=True)
    ts = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)


class UserEventLog(models.Model):
    """
              _id: str,
              ip: str,
              user: str,
              tc: datetime,
              type: str,
              query: str,
              uid: str,
              ud: str,
              item: str
            }
    """
    ip = models.GenericIPAddressField(null=True, blank=True)
    user = models.CharField(max_length=64, null=True, blank=True)
    tc = models.DateTimeField()
    tc_day = models.DateField()
    type = models.CharField(max_length=32, null=True, blank=True)
    query = models.CharField(max_length=255, null=True, blank=True)
    uid = models.CharField(max_length=64, null=True, blank=True)
    ud = models.CharField(max_length=64, null=True, blank=True)
    item = models.CharField(max_length=32, null=True, blank=True)
    create_at = models.DateTimeField(auto_now_add=True)


class ChineseEnglish(models.Model):
    ch = models.CharField(max_length=255, null=True, blank=True)
    eng = models.CharField(max_length=255, null=True, blank=True)
    translator = models.CharField(max_length=64)
    create_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['ch', 'eng']


class UserVector(models.Model):
    uid = models.CharField(max_length=128, unique=True)
    subscribes = models.JSONField(blank=True, null=True)
    gender = models.IntegerField(null=True, blank=True)
    title = models.CharField(max_length=255, null=True, blank=True)
    vector = models.JSONField(blank=True, null=True)
    cluster = models.IntegerField(blank=True, null=True)
    update_at = models.DateTimeField(auto_now=True)
    create_at = models.DateTimeField(auto_now_add=True)


class ChatRound(models.Model):
    uid = models.CharField(max_length=128, db_index=True)
    user_message = models.TextField()
    user_pubs = models.JSONField()
    assistant_message = models.TextField()
    assistant_extend_message = models.TextField(blank=True, null=True)
    spend_seconds = models.FloatField(default=0.0)
    extend_spend_seconds = models.FloatField(default=0.0)
    create_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["create_at"]

    @property
    def pub_titles(self):
        return [{'title': x['title'], 'recall_from': x.get('recall_from')} for x in self.user_pubs]
