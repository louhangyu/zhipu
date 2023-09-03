import datetime
import gzip
import json
import os

import logging
import socket

import pymongo
import requests

from bson import ObjectId
from django.conf import settings
from django.utils.timezone import now
from django.utils import timezone
from recsys.models import MongoConnection, HighQualityPaper
from recsys.algorithms.base import BaseAlgorithm, RedisConnection
from recsys.algorithms.constants import Constants
from recsys.utils import remove_duplicate_blanks

import pyssdb

from recsys.utils import is_mongo_id

logger = logging.getLogger(__name__)


#进行连接 SSDB数据库
try:
    if settings.SSDB['host'] and settings.SSDB['port']:
        ssdb_client = pyssdb.Client(host=settings.SSDB['host'], port=settings.SSDB['port'], socket_timeout=600)
    else:
        ssdb_client = None
except Exception as e:
    logger.error("failed to connect ssdb: {}".format(e))
    ssdb_client = None


class Aggregate(BaseAlgorithm):
    PUB_CACHE_TIME = Constants.PUB_CACHE_TIME

    def __init__(self) -> None:
        super(Aggregate, self).__init__(RedisConnection.get_default(), "agg")
        self.mongo = MongoConnection.get_aminer_client()
        self.ssdb_client = ssdb_client
        self.data_token = None   # aminer data center api token
        self.data_token_time = None
        self.graph_keywords = set()  # from mongodb aminer.data_category_tag
        self.gateway_host = settings.DATA_API_HOST

    def re_ranking(self, uid: str, ud: str, num: int = 6, ab_flag: str = None, **kwargs):
        """Re-sort predictions after recall related items.

        Args:
            uid (str): logined user id
            ud (str): JS generated uuid for anonymous user
            num (int, optional): item count need. Defaults to 50.
            ab_flag (str, optional): AB user group. Defaults to None.
            alg_flag (str, optional): Algorithm flag
            keywords (list[str]): list of keyword
            exclude_ids (list[str]): list of publication id which are excluded
            first_reach (str): ud or uid reach aminer first time.

        Returns:
            {
                data: [
                    {item:str, score:float, type:str, recall_reason: str, recall_type: str},
                    ...
                ],
                meta: {
                }
            }
        """
        from recsys.algorithms.native import AlgorithmNativeApi
        from recsys.algorithms.shenzhen import AlgorithmShenzhenApi
        from recsys.algorithms.push import AlgorithmPushApi

        alg_flag = kwargs.get("alg_flag")
        if alg_flag:
            if alg_flag == Constants.ALG_SHENZHEN:
                alg = AlgorithmShenzhenApi()
            elif alg_flag == Constants.ALG_PUSH:
                alg = AlgorithmPushApi()
            else:
                alg = AlgorithmNativeApi()
        else:
            alg = AlgorithmNativeApi()

        data = alg.ranking(uid, ud, num, ab_flag=ab_flag, **kwargs)
        if not data:
            logger.warning("failed to get recommend from algorithm {}, ab flag {}, uid {}, ud {}".format(
                alg, ab_flag, uid, ud, kwargs))

        return data

    def get_pub_cache_key(self, pub_id: str):
        return "{}_pub_{}".format(self.name, pub_id)

    def get_cached_pub(self, pub_id):
        pub_cache_key = self.get_pub_cache_key(pub_id)
        pub_cache_data_raw = self.redis_connection.get(pub_cache_key)
        if pub_cache_data_raw:
            return json.loads(gzip.decompress(pub_cache_data_raw))

        return None

    def get_cached_person(self, person_id):
        cache_key = self.get_person_cache_key(person_id)
        raw = self.redis_connection.get(cache_key)
        if raw:
            return json.loads(gzip.decompress(raw))

        return None

    def preload_person(self, person_id, use_cache=True):
        cache_key = self.get_person_cache_key(person_id)
        raw = self.redis_connection.get(cache_key)
        if raw and use_cache:
            return json.loads(gzip.decompress(raw))

        projection = {
            '_id': 1,
            'avatar': 1,
            'name': 1,
            'contact': 1,
            'h_index': 1,
            'n_pubs': 1,
            'n_citation': 1,
            'interests': 1,
            'na_ts': 1,
        }
        persons = self.mongo.find_by_id("aminer", "person", person_id, projection)
        if not persons:
            logger.warning("person {} not found in the mongo".format(person_id))
            return {}

        person = persons[0]
        contact = person.get('contact', {})
        interests = []
        if 'interests' in person and person['interests']:
            for interest in person['interests']:
                interests.append({
                    't': interest.get('t') or ''
                })
        result = {
            'type': self.ITEM_PERSON,
            'id': str(person['_id']),
            'ts': person.get('na_ts').strftime(Constants.SQL_DATETIME_FORMAT) if 'na_ts' in person and person['na_ts'] else '',
            'avatar': person.get('avatar'),
            'name': person.get('name'),
            'indices': {
                "pubs": person.get('n_pubs'),
                'hindex': person.get("h_index"),
                'citations': person.get('n_citation'),
            },
            'interests': interests,
            'contact': {
                'address': contact.get('address'),
                'affiliation': contact.get('affiliation'),
                'affiliation_zh': contact.get('affiliation_zh'),
                'position': contact.get('position'),
                'position_zh': contact.get('position_zh'),
            },
            'num_viewed': self.fetch_person_num_viewed(person_id)
        }

        self.redis_connection.setex(cache_key, Constants.PERSON_CACHE_TIME, gzip.compress(json.dumps(result).encode("utf-8")))
        return result

    def get_cached_items(self, items):
        """Fetch data from redis once and update items
        :param items: list of {item:str, score:float, type:str, from:str, recall_type: str, recall_reason:{}}
        :return: {
            (item_id, item_type): {
                item: str, score:float, type: str, from: str, recall_type: str, recall_reason: {}, title: str, ...
            }
        }
        """
        result = {}
        cache_keys = []
        cache_key_item_map = {}
        for item in items:
            item_id = item.get('item')
            item_type = item.get("type")

            if item_type == self.ITEM_PUB:
                cache_key = self.get_pub_cache_key(item_id)
            elif item_type == self.ITEM_PUB_TOPIC:
                cache_key = self.get_pub_topic_cache_key(item_id)
            elif item_type == self.ITEM_PERSON:
                cache_key = self.get_person_cache_key(item_id)
            elif item_type == self.ITEM_AI2K:
                cache_key = self.get_ai2k_cache_key(item_id)
            else:
                logger.warning("unknown item type {}".format(item_type))
                continue

            new_item = item.copy()

            if cache_key:
                cache_keys.append(cache_key)
                cache_key_item_map[cache_key] = new_item

            result[(item_id, item_type)] = new_item

        lost_items = []  # list of (item_id, score, item_type, from)
        raw_list = self.redis_connection.mget(cache_keys)
        for i, raw in enumerate(raw_list):
            if not raw:
                cache_key = cache_keys[i]
                item = cache_key_item_map[cache_key]
                lost_items.append(
                    (item.get("item"), 0, item.get('type'), '')
                )
                logger.warning("cache key {} is not found, item {}, response {}".format(cache_keys[i], item, raw))
                continue

            unzip_data = gzip.decompress(raw)
            original = json.loads(unzip_data)
            item_id = original.get("id")
            if not item_id:
                continue
            item_type = original.get('type')
            if not item_type:
                continue

            if (item_id, item_type) not in result:
                continue

            result[(item_id, item_type)].update(original)

        # remove some invalid item
        invalid_items = []  # list of (item_id, item_type)
        for key, value in result.items():
            if key[1] == self.ITEM_PUB:
                if 'title' not in value or not value['title']:
                    logger.warning("not found title or title is null of {}: {}".format(key, value))
                    invalid_items.append(key)
                    continue

            if 'id' not in value and 'item' not in value:
                logger.warning("not found id or item of {}: {}".format(key, value))
                invalid_items.append(key)

        if lost_items:
            from recsys.background import preload_lost_items
            logger.warning("lost items count {}, {}".format(len(lost_items), lost_items))
            preload_lost_items.delay(lost_items)

        if invalid_items:
            logger.warning("invalid items count {}, {}".format(len(invalid_items), invalid_items))
            for key in invalid_items:
                del result[key]

        if not result:
            logger.warning("items {} don't have cached items".format(items))
        else:
            logger.info("items {} => cached items {}".format(items, result))

        return result

    def preload_pub(self, pub_id: str, use_cache: bool = True) -> dict:
        """ Pack publication content
        :param pub_id:
        :param use_cache:
        :return: publication data dict, for example 5eafe7e091e01198d39865d6
        """
        if use_cache:
            cached_pub = self.get_cached_pub(pub_id)
            if cached_pub:
                return cached_pub

        pub_cache_key = self.get_pub_cache_key(pub_id)
        projection = {
            'authors': 1,
            'doi': 1,
            '_id': 1,
            'n_citation': 1,
            'page_start': 1,
            'page_end': 1,
            'pdf': 1,
            'title': 1,
            'title_zh': 1,
            'urls': 1,
            'venue': 1,
            'year': 1,
            'abstract': 1,
            'abstract_zh': 1,
            "keywords": 1,
            "keywords_zh": 1,
            'versions': 1,
            'ts': 1,
            'venue_hhb_id': 1,
        }
        if is_mongo_id(pub_id) is False:
            logger.warning("pub id {} is not valid ID".format(pub_id))
            return {}
        pubs = self.mongo.find_by_id("aminer", "publication_dupl", pub_id, projection)
        if len(pubs) == 0:
            return {}
        pub = pubs[0]
        pdf_info = self.fetch_pdf_info(pub_id)
        # fetch all authors
        if 'authors' in pub and pub['authors']:
            authors = pub['authors']
            author_ids = []
            for i, x in enumerate(authors):
                if authors[i] and 'orgid' in authors[i]:
                    authors[i]['orgid'] = str(authors[i]['orgid'])
                if not x or "_id" not in x:
                    continue
                author_ids.append(str(x['_id']))
                authors[i]['_id'] = str(authors[i]['_id'])
            author_avatars = self.fetch_authors(author_ids)
            author_id_avatar_map = {}
            for item in author_avatars:
                author_id_avatar_map[item['id']] = item

            for i, author in enumerate(authors):
                if not author:
                    continue
                author_id = author.get("_id")
                if not author_id:
                    continue
                author_id = str(author_id)

                authors[i].update(
                    author_id_avatar_map.get(author_id, {})
                )
        else:
            authors = []
            author_ids = []

        # fetch ai 2000 rank etc.
        author_id_rank_map = self.fetch_ai2k_rank(author_ids)
        for i in range(len(authors)):
            author = authors[i]
            if 'id' not in author:
                continue
            author_id = author['id']
            authors[i]['ai2000'] = author_id_rank_map.get(author_id)
            authors[i]['jconf'] = self.fetch_jconf_rank(author_id)

        venue_info = self.get_venue_info(pub)

        versions = pub.get('versions', [])
        for i in range(len(versions)):
            if 'i' in versions[i]:
                del versions[i]['i']

        clean_pub = {
            'id': str(pub['_id']),
            'type': self.ITEM_PUB,
            'authors': authors,
            'data2videoUrl': pdf_info.get('data2videoUrl'),
            'doi': pub.get('doi'),
            'figureUrls': pdf_info.get('metadata', {}).get('figure_urls', None),
            'num_citation': pub.get('n_citation', 0),
            'num_viewed': None,
            'pages': {
                "start": pub.get('page_start'),
                "end": pub.get('page_end'),
            },
            'pdf': pub.get('pdf'),
            'title': remove_duplicate_blanks(pub.get('title')),
            'urls': pub.get('url'),
            'venue': {
                'info': {
                    'name': venue_info.get('Name'),
                    'short': venue_info.get('Short')
                },
                'venue_hhb_id': str(pub.get('venue_hhb_id')) if 'venue_hhb_id' in pub else None
            },
            'year': pub.get('year'),
            'summary': pdf_info.get('headline'),
            'abstract': pub.get('abstract'),
            'keywords': pdf_info.get('keywords'),
            'graph_keywords': [],
            "sciq": self.fetch_sci_q(pub_id),
            'versions': versions,
            'ts': "",
            'subject_en': '',
            'subject_zh': '',
            'category': self.get_pub_category(pub_id),
            'preload_ts': timezone.now().strftime(Constants.SQL_DATETIME_FORMAT),
            'preload_host': socket.gethostname(),
            'preload_proc': os.getpid(),
        }
        num_viewed = self.fetch_pub_num_viewed(pub_id, use_cache)
        if num_viewed is not None:
            clean_pub['num_viewed'] = num_viewed

        labels, labels_zh = self.generate_labels(clean_pub, [])
        clean_pub['labels'] = labels
        clean_pub['labels_zh'] = labels_zh
        clean_pub['graph_keywords'] = self.fetch_graph_keywords(pdf_info.get('keywords', []))

        # get subject
        try:
            high_quality_paper = HighQualityPaper.objects.get(paper_id=pub_id)
            clean_pub['subject_zh'] = high_quality_paper.subject_zh
            clean_pub['subject_en'] = high_quality_paper.subject_en
        except Exception as e:
            logger.warning(f"except when get {pub_id} subject: {e}")

        if 'ts' in pub and pub['ts'] is not None:
            clean_pub['ts'] = timezone.make_aware(pub['ts'] + datetime.timedelta(hours=8)).strftime(Constants.SQL_DATETIME_FORMAT)

        # save cache
        self.redis_connection.setex(pub_cache_key, self.PUB_CACHE_TIME, gzip.compress(json.dumps(clean_pub).encode()))
        return clean_pub

    def get_venue_info(self, pub: str):
        info = {"Name": None, "Short": None}
        venue_hhb_id = str(pub.get("venue_hhb_id")) if "venue_hhb_id" in pub else None
        if venue_hhb_id:
            venue_hhb_infos = self.mongo.find_by_id("aminer", "venue_hhb", venue_hhb_id)
            if len(venue_hhb_infos) > 0:
                venue_hhb_info = venue_hhb_infos[0]
            else:
                venue_hhb_info = {}
        else:
            venue_hhb_info = {}
        venue_raw = pub.get('venue', {}).get('raw')
        if venue_raw:
            # venue_unify = self.fetch_pub_venue(venue_raw, venue_hhb_id)
            venue_unify = venue_hhb_info.get("short_name", "")
            if venue_unify:
                info = {'Name': venue_raw, 'Short': venue_unify}
            else:
                info['Name'] = venue_raw
        elif 'versions' in pub and pub['versions'] and len(pub['versions']) > 0:
            if pub['versions'][0]['l'] == "arxiv":
                info['Short'] = "Arxiv"
                info['Name'] = "Arxiv"
            else:
                vname = ""
                for version in pub['versions']:
                    if 'vname' in version and version['vname']:
                        vname = version['vname']
                        break
                if vname:
                    #venue_unify = self.fetch_pub_venue(vname, venue_hhb_id)
                    venue_unify = venue_hhb_info.get("short_name", "")
                    if venue_unify:
                        info = {'Name': vname, 'Short': venue_unify}
        else:
            info['Short'] = None
            info['Name'] = venue_raw

        return info

    def get_pub_category(self, pub_id):
        pubs = self.mongo.find_by_id("aminer", "publication", pub_id)
        if not pubs:
            return None
        categories = pubs[0].get('category')
        if not categories:
            return None
        for i in range(len(categories)):
            cate = categories[i]
            fields = cate.split("-")
            if len(fields) == 1:
                categories[i] = cate
            elif len(fields) == 2:
                categories[i] = fields[1].strip()
            else:
                categories[i] = cate
        return categories

    def get_ai2k_cache_key(self, ai2k_id: str):
        return "{}_ai2k_{}".format(self.name, ai2k_id)

    def get_cached_ai2k(self, ai2k_id):
        cache_key = self.get_ai2k_cache_key(ai2k_id)
        raw = self.redis_connection.get(cache_key)
        if raw:
            return json.loads(gzip.decompress(raw))

        return None

    def preload_ai2k(self, ai2k_id, use_cache=True):
        """ Preload data from mongo aminer_rank.recommend_record
        :param ai2k_id:
        :param use_cache:
        :return: {
            type: str,
            id: str,
            persons: [
                {
                    person_id: str,
                    avatar: str,
                    name: str,
                    name_zh: str,
                },
                ...
            ],
            activities: [
                {
                    pub_id: str,
                    title: str,
                    event_datetime: str,
                    person_id: str,
                    person_name: str
                },
                ...
            ]
        }
        """
        if use_cache:
            data = self.get_cached_ai2k(ai2k_id)
            if data:
                return data

        data = {
            'id': ai2k_id,
            'type': self.ITEM_AI2K,
            'persons': [],
            'activities': []
        }
        docs = self.mongo.find_by_id("aminer_rank", "recommend_record", ai2k_id)
        if not docs:
            logger.warning("ai2k {} not found in mongo".format(ai2k_id))
            return {}
        doc = docs[0]
        person_ids = doc['person_ids'][:10]
        person_docs = self.mongo.find_by_ids("aminer", "person", person_ids)
        for p in person_docs:
            data['persons'].append({
                'person_id': str(p['_id']),
                'avatar': p.get('avatar'),
                'name': p.get('name'),
                'name_zh': p.get('name_zh'),
            })

        last_happen = timezone.now() - datetime.timedelta(7)
        activity_docs = self.mongo.sort(
            'web',
            'scholar_paper_pool',
            {'person_id': {"$in": doc['person_ids']}, 'event_date': {"$gt": last_happen}},
            [("event_date", pymongo.DESCENDING)],
            None,
            limit=5
        )
        for a in activity_docs:
            tmp = self.mongo.find_by_id("aminer", "publication_dupl", a['event_pub_id'])
            if not tmp:
                continue
            pub = tmp[0]
            pub_venue_info = self.get_venue_info(pub)

            tmp = self.mongo.find_by_id('aminer', 'person', a['person_id'])
            if not tmp:
                continue
            person = tmp[0]
            data['activities'].append({
                'pub_id': a['event_pub_id'],
                'venue': {
                    'info': {
                        'name': pub_venue_info.get('Name'),
                        'short': pub_venue_info.get('Short')
                    }
                },
                'year': pub.get('year'),
                'title': pub['title'],
                'event_time': a['event_time'].strftime(Constants.SQL_DATETIME_FORMAT),
                'person_id': a['person_id'],
                'person_name': person['name'],
                'person_name_zh': person['name_zh'],
            })

        # save to redis
        cache_key = self.get_ai2k_cache_key(ai2k_id)
        self.redis_connection.setex(cache_key, self.PUB_CACHE_TIME, gzip.compress(json.dumps(data).encode()))

        return data

    def increase_pub_num_view(self, pub_id):
        cached_pub = self.get_cached_pub(pub_id)
        if not cached_pub:
            return 0

        num_viewed = self.fetch_pub_num_viewed(pub_id, False)
        if num_viewed is None:
            return 0

        if num_viewed > cached_pub['num_viewed']:
            cached_pub['num_viewed'] = num_viewed
        else:
            cached_pub['num_viewed'] += 1

        pub_cache_key = self.get_pub_cache_key(pub_id)
        self.redis_connection.setex(pub_cache_key, self.PUB_CACHE_TIME, gzip.compress(json.dumps(cached_pub).encode()))
        return cached_pub['num_viewed']

    def fetch_authors(self, author_ids):
        """
        :param author_ids:  list of author_id
        :return: list of
            {
                avatar: str,
                name: str,
                org: str,
                id: str
            }
        """
        if not author_ids:
            return []
        result = []
        sql = {
            'avatar': {'$exists': True},
            '_id': {
                "$in": [ObjectId(x) for x in author_ids]
            }
        }
        projection = {
            '_id': 1,
            'avatar': 1,
            'name': 1,
            'contact': 1,
            'h_index': 1,
        }
        persons = self.mongo.find("aminer", "person", sql, projection)
        for p in persons:
            result.append({
                'avatar': p.get('avatar'),
                'id': str(p['_id']),
                'name': p.get('name'),
                'org': p.get('contact', {}).get('affiliation', None),
                'h_index': p.get('h_index'),
            })
        logger.info("result avatars => {}".format(result))
        return result

    def fetch_pdf_info(self, pub_id: str):
        sql = {
            "pid": pub_id,
        }
        projection = {
            'data2videoUrl': 1,
            'metadata': 1,
            'headline': 1,
            "keywords": 1
        }
        pdf_infos = self.mongo.find("aminer", "publication_pdf_info", sql, projection)
        if len(pdf_infos) == 0:
            # logger.warning("not found pdf info for '{}'".format(pub_id))
            return {}
        return pdf_infos[0]

    def fetch_pub_num_viewed(self, pub_id, use_cache=True):
        key = "PAGE_VIEWED::PUB"
        redis_key = "{}:{}".format(key, pub_id)

        if use_cache:
            redis_value = self.redis_connection.get(redis_key)
            if redis_value:
                return int(redis_value)

        if not self.ssdb_client:
            return None
        value = self.ssdb_client.zget(key, pub_id)
        if value is None:
            logger.info("can't get num viewed for {}, {}".format(key, pub_id))
            return 0

        logger.info("pub {} num viewed is {}".format(key, value))
        if value and value > 3:
            self.redis_connection.setex(redis_key, 3600*24*7, str(value))

        return value

    def fetch_person_num_viewed(self, person_id, use_cache=True):
        key = "PAGE_VIEWED::PERSON"
        redis_key = "{}:{}".format(key, person_id)

        if use_cache:
            redis_value = self.redis_connection.get(redis_key)
            if redis_value:
                return int(redis_value)

        if not self.ssdb_client:
            return None
        value = self.ssdb_client.zget(key, person_id)
        if value is None:
            logger.warning("can't get num viewed for person {}, {}".format(key, person_id))
            return 0

        logger.info("person {} num viewed is {}".format(key, value))
        if value and value > 3:
            self.redis_connection.setex(redis_key, 3600*24*7, str(value))

        return value

    def generate_labels(self, paper: dict, keywords: list) -> tuple:
        """
        针对每篇论文返回如下类型的标签，标签规则如下：
        （1） 关键词标签（# #）：前端调用接口给过来的查询关键词，是什么关键词就返回什么
        （2） 新论文标签（New）：发表时间在当年的论文。
        查询字段：表：Publication_dupl  字段：year

        （3） Arxiv论文（Arxiv）：论文Venue是Arxiv的论文
        查询字段：venue： raw  。如果 raw是arxiv ，返回此字段。

        （4） 高引论文标签（High Citation）：论文引用量超过200的论文。
        查询字段：表：Publication_dupl  字段：n_citation

        （5） 顶刊顶会标签（Top Conference）：符合h-index>50的Venue
        表：Publication_dupl  字段：venue：_id   ， raw 。 _id是期刊ID，根据此ID去期刊表（Venue_dupl）里获取h-index指标（h_index）； raw是期刊名字

        （6） Top学者论文（Top Author）：所有论文作者中，如果有h-index超过50的学者，返回此标签；
        查询字段：表：Publication_dupl  字段：authors：_id。  根据这个id去person库里取该学者的h-index，有多个学者的情况下，逐个判断是否符合条件，只要有1个符合就返回此标签；

        （7） 热门论文（Hot Paper）：累积浏览量超过300的论文，返回此标签
        查询方式：通过pub.GetPageData API 获取num_viewed 这个字段

        New  新论文
        Arxiv  Arxiv
        High Citation   高引论文
        Top Conference  顶刊
        Top Author  大牛作者

        :return:
        """
        labels = []
        labels_zh = []
        if keywords:
            labels += keywords
            labels_zh += keywords

        if self.is_newly(paper):
            labels.append("New")
            labels.append("新论文")

        if self.is_arxiv(paper):
            labels.append("Arxiv")
            labels_zh.append("Arxiv")

        n_citation = paper.get('n_citation', 0)
        if n_citation > 200:
            labels.append("High Citation")
            labels_zh.append("高引论文")

        venue_id = paper.get('venue', {}).get('_id')
        if venue_id:
            venues = self.mongo.find_by_id('aminer', 'venue_dupl', venue_id, {'h_index': 1})
            if len(venues) > 0:
                if venues[0].get('h_index', 0) > 50:
                    labels.append('Top Conference')
                    labels_zh.append("顶刊")

        authors = paper.get('authors', [])
        for author in authors:
            if 'h_index' in author and author.get('h_index') and author.get('h_index') > 50:
                labels.append("Top Author")
                labels_zh.append("大牛作者")
                break

        if "num_viewed" in paper and paper['num_viewed'] and paper['num_viewed'] >= 300:
            labels.append("Hot Paper")
            labels_zh.append("热门论文")

        return labels, labels_zh

    @classmethod
    def is_arxiv(cls, pub):
        if 'versions' not in pub:
            return False

        for version in pub['versions']:
            if 'l' in version and version['l'].lower() == "arxiv":
                return True

        return False

    @classmethod
    def is_sci_q1(cls, pub):
        if pub['sciq'] and Constants.SCI_SOURCE in pub['sciq'] and Constants.SCI_QUARTILE in pub['sciq'][Constants.SCI_SOURCE]:
            return True

        return False

    @classmethod
    def is_ccf_a(cls, pub):
        if pub['sciq'] and Constants.CCF_SOURCE in pub['sciq'] and Constants.CCF_QUARTILE in pub['sciq'][Constants.CCF_SOURCE]:
            return True

        return False

    @classmethod
    def is_newly(cls, pub):
        if 'year' in pub and pub['year']:
            if int(pub['year']) < timezone.now().year:
                return False

        ts = pub.get("ts")
        if ts:
            ts_dt = datetime.datetime.strptime(ts, Constants.SQL_DATETIME_FORMAT)
            ts_dt = timezone.make_aware(ts_dt)
            if cls.is_arxiv(pub) and ts_dt > now() - datetime.timedelta(90):
                return True
            elif (cls.is_ccf_a(pub) or cls.is_sci_q1(pub)) and ts_dt > now() - datetime.timedelta(365):
                return True

        return False

    def fetch_pub_venue(self, venue: str, venue_hhb_id: str = None):
        """
        :param venue:
        :param venue_hhb_id:
        :return:
            {
                Name: str,
                Short: str
            }
        """
        #url = "http://gateway.private.aminer.cn/private/api/v2/venue/short"
        url = f"{self.gateway_host}/api/v2/venue/short"
        params = {"alias": venue, "venue_hhb_id": venue_hhb_id}
        header = {
            "Authorization": "Bearer {}".format(self.get_data_token())
        }
        try:
            r = requests.get(url, params, headers=header, timeout=30)
        except Exception as e:
            logger.warning("fetch_pub_venue failed: {}, {}".format(url, e))
            return {}

        if r.status_code != 200:
            logger.warning("failed to fetch pub venue by url {}, params {}, response {}".format(url, params, r.text))
            return {}

        return r.json()["data"]

    def fetch_sci_q(self, paper_id):
        #url = "http://gateway.private.aminer.cn/private/api/v2/venue/quartile/by/paper_id"
        url = f"{self.gateway_host}/api/v2/venue/quartile/by/paper_id"
        params = {"id": paper_id}
        header = {
            "Authorization": "Bearer {}".format(self.get_data_token()),
            "Accept": "application/json",
        }
        try:
            r = requests.get(url, params, headers=header, timeout=5)
        except Exception as e:
            logger.warning("failed to get {}: {}".format(url, e))
            return {}
        if r.status_code != 200:
            logger.warning("failed to fetch SCIQ by url {}, params {}, response {}".format(url, params, r.text))
            return {}
        data = r.json()
        if 'data' not in data:
            logger.warning("failed to fetch SCIQ by url {}, params {}, response {}, data is null".format(url, params, r.text))
            return {}
        if data['success'] is False:
            logger.warning("failed to fetch SCIQ by url {}, params {}, response {}".format(url, params, r.text))
            return {}

        return data['data']

    def fetch_subject_category(self, source, level=0):
        """
        :param source:
        :param level:
        :return:
            returns list of {id: str, name: str}
        """
        #url = "http://gateway.private.aminer.cn/private/api/v2/venue/category/by/source/level"
        url = f"{self.gateway_host}/api/v2/venue/category/by/source/level"
        headers = {"Authorization": "Bearer {}".format(self.get_data_token())}
        params = {
            "source": source,
            "level": level,
            'limit': 1000,
        }
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        if resp.status_code != 200:
            logger.warning("failed to fetch subject category {}, params {}, headers {}, resp {}".format(url, params, headers, resp.text))
            return []

        return resp.json()['data']

    def fetch_venue_ids(self, subject_id, quartile, limit=1000):
        #url = "http://gateway.private.aminer.cn/private/api/v2/venue/venue_ids/by/category_id"
        url = f"{self.gateway_host}/api/v2/venue/venue_ids/by/category_id"
        headers = {"Authorization": "Bearer {}".format(self.get_data_token())}
        params = {
            "id": subject_id,
            'limit': limit,
            'quartile': quartile,
        }
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        if resp.status_code != 200 or resp.json()['data'] is None:
            logger.warning("failed to fetch venue {}, params {}, headers {}, resp {}".format(url, params, headers, resp.text))
            return []

        return resp.json()['data']

    def fetch_venue_paper_ids(self, venue_id, start_year, end_year):
        #url = "http://gateway.private.aminer.cn/private/api/v2/venue/paperIDs/by/year"
        url = f"{self.gateway_host}/api/v2/venue/paperIDs/by/year"
        headers = {"Authorization": "Bearer {}".format(self.get_data_token())}
        paper_ids = []
        offset = 0
        limit = 100

        while True:
            params = {
                "id": venue_id,
                'start_year': start_year,
                'end_year': end_year,
                'limit': limit,
                'offset': offset,
                # "class": "sci",
            }
            try:
                resp = requests.get(url, headers=headers, params=params, timeout=30)
            except Exception as e:
                logger.warning("failed to fetch paper {}, params {}, headers {}: {}".format(url, params, headers, e))
                continue

            if resp.status_code != 200 or resp.json()['data'] is None:
                logger.warning("failed to fetch paper {}, params {}, headers {}, resp {}".format(url, params, headers, resp.text))
                break

            data = resp.json()['data']
            paper_ids += data
            offset += len(data)
            if len(data) < limit:
                break

        return paper_ids

    def fetch_person_pub_na(self, na_num, num):
        #url = "http://gateway.private.aminer.cn/private/api/v2/person/pubNa"
        url = f"{self.gateway_host}/api/v2/person/pubNa"
        headers = {"Authorization": "Bearer {}".format(self.get_data_token())}
        limit = 200
        offset = 0
        person_ids = []

        while True:
            params = {
                "num": na_num,
                'limit': limit,
                'offset': offset,
            }
            try:
                resp = requests.get(url, headers=headers, params=params, timeout=5)
            except Exception as e:
                logger.warning("failed to fetch person pub na {}, params {}, headers {}: {}".format(url, params, headers, e))
                continue

            if resp.status_code != 200 or resp.json()['data'] is None:
                logger.warning("failed to fetch paper {}, params {}, headers {}, resp {}".format(url, params, headers, resp.text))
                break

            data = resp.json()['data']
            person_ids += data
            offset += len(data)
            if len(data) < limit:
                break
            if offset > num:
                break

        return person_ids

    def fetch_ai2k_rank(self, person_ids):
        """
        :param person_ids: list of person_id
        :return:
            dict: returns person_id's award map. Format is
            {
                person_id : {}
            }
        """
        params = []
        for person_id in person_ids:
            param = {
                "action": "ranking.Search",
                "parameters": {
                    "brand": "ai_2000_scholar",
                    "entity_id": person_id,
                    "year_left": 2012,
                    "year_right": 2021,
                }
            }
            params.append(param)
        for host in settings.API_V2_HOSTS:
            if host.find("http") == 0:
                url = "{}/magic?".format(host)
            else:
                url = "http://{}/magic?".format(host)
            try:
                r = requests.post(url, data=json.dumps(params), timeout=5)
                break
            except Exception as e:
                logger.warning("failed to post {}, {}: {}".format(url, params, e))
                r = None

        if not r:
            logger.warning("failed to fetch ai2k by url {}, params {}".format(url, params))
            return {}

        if r.status_code != 200:
            logger.warning("failed to fetch ai2000 by url {}, params {}, response {}".format(url, params, r.text))
            return {}
        logger.info("url {}, params {}, response {}".format(url, params, r.text))

        if 'data' not in r.json()['data'][0]:
            return {}
        items = r.json()['data']
        result = {}
        for item_data in items:
            item = item_data['data']
            person_id = item['person_id']
            if 'domain_awards' not in item:
                continue

            domain_awards = item['domain_awards']
            min_award = None
            min_rank = None
            for award in domain_awards:
                metrics = award['metrics']
                metrics = sorted(metrics, key=lambda x: x['rank'], reverse=False)
                award['min_rank'] = metrics[0]['rank']
                award['metrics'] = metrics[:1]
                if not min_rank:
                    min_rank = award['min_rank']
                    min_award = award
                elif award['min_rank'] < min_rank:
                    min_rank = award['min_rank']
                    min_award = award

            result[person_id] = min_award
        return result

    def fetch_jconf_rank(self, person_id):
        params = [
            {
                "action": "newconferencerank.QueryJconfRank",
                "parameters": {"id": person_id}
            },
        ]

        for host in settings.API_V2_HOSTS:
            if host.find("http") == 0:
                url = "{}/magic?a=__newconferencerank.QueryJconfRank___".format(host)
            else:
                url = "http://{}/magic?a=__newconferencerank.QueryJconfRank___".format(host)
            try:
                r = requests.post(url, data=json.dumps(params), timeout=5)
                break
            except Exception as e:
                logger.warning("failed to post {}, {}: {}".format(url, params, e))
                r = None

        if not r:
            logger.warning("failed to fetch jconf by url {}, params {}".format(url, params))
            return {}

        if r.status_code != 200:
            logger.warning("failed to fetch jconf by url {}, params {}, response {}".format(url, params, r.text))
            return {}

        logger.info("url {}, params {}, response {}".format(url, params, r.text))
        if 'data' not in r.json()['data'][0]:
            return {}

        return r.json()['data'][0]['data']

    @classmethod
    def fetch_pub_summary(cls, pub_id):
        """
        :param pub_id:
        :return:
                {
                    "create_time": "2022-07-13T01:48:28.561Z",
                    "id": "62ce246cef52690a4b51e65f",
                    "publication_id": "62b135585aee126c0fa06e15",
                    "summary_en": str
                    "summary_zh": str
                    "update_time": "2022-09-15T02:05:13.575Z"
                }
        """
        params = [{
            "action": "PublicationQinghuaSummary.GetPublicationQinghuaSummaryListByPublicationId",
            "parameters": {
                "publication_id": pub_id
            }
        }]
        url = "https://apiv2.aminer.cn/n?a=GetPublicationQinghuaSummaryListByPublicationId__PublicationQinghuaSummary.GetPublicationQinghuaSummaryListByPublicationId___"
        try:
            r = requests.post(url, data=json.dumps(params), timeout=30)
        except Exception as e:
            logger.warning(f"failed to post {url}: {e}")
            return {}

        return r.json()['data'][0]['data']['publicationQinghuaSummaryList'][0]

    def fetch_graph_keywords(self, keywords):
        """
        :param keywords:  list of keyword str
        :return:
          [(str, bool)]: returns list of (keyword, has_graph)
        """
        if not self.graph_keywords:
            self.load_graph_keywords()

        result = []
        for keyword in keywords:
            if keyword in self.graph_keywords:
                flag = True
            else:
                flag = False

            result.append((keyword, flag))

        return result

    def load_graph_keywords(self):
        if self.graph_keywords:
            return

        if len(self.graph_keywords) == 0:
            return

        items = self.mongo.find("aminer", "data_category_tag")
        for item in items:
            self.graph_keywords.add(item['name'])
            self.graph_keywords.add(item['name_zh'])

    def fetch_data_token(self) -> str:
        # get token first
        url = "https://oauth.aminer.cn/api/v2/oauth/token"
        """
        params = {
            "grant_type": "client_credentials",
            "client_id": "8bf0f26a-f87c-4c2f-8086-997f337b6d29",
            "client_secret": "638e154b-b9fd-4c86-9744-9f7193cc5de8",
        }
        """
        params = {
            "grant_type": "client_credentials",
            "client_id": "a227299c-0fa4-4cbe-95a8-a8af7ce4837c",
            "client_secret": "db74429f-8a68-4e33-8dc9-a2349bfac401",
            "username": "aminer",
            "password": "a2f24a50-8c49-4572-90c1-017339b51a9c",
        }
        r = requests.post(url, data=params, timeout=30)
        if r.status_code != 200:
            logger.warning("fetch {}, params {}, response status code {} is not 200".format(url, params, r.status_code))
            return settings.DATA_API_FOREVER_TOKEN

        if 'access_token' not in r.json():
            return settings.DATA_API_FOREVER_TOKEN

        self.data_token = r.json()["access_token"]
        self.data_token_time = now()
        return self.data_token

    def get_data_token(self):
        if self.data_token_time is None:
            return self.fetch_data_token()

        if self.data_token is None:
            return self.fetch_data_token()

        if self.data_token_time < now() - datetime.timedelta(hours=1):
            return self.fetch_data_token()

        return self.data_token

    def get_pub_topic_cache_key(self, pub_topic_id: str):
        return "{}_pub_topic_{}".format(self.name, pub_topic_id)

    def get_cached_pub_topic(self, pub_topic_id):
        cache_key = self.get_pub_topic_cache_key(pub_topic_id)
        cache_data_raw = self.redis_connection.get(cache_key)
        if cache_data_raw:
            return json.loads(gzip.decompress(cache_data_raw))

        return None

    def preload_pub_topic(self, pub_topic_id: str, use_cache: bool = True) -> dict:
        """ Depend on preload_pub
        :param pub_topic_id:
        :param use_cache:
        :return:
        """
        if use_cache:
            cached_pub_topic = self.get_cached_pub_topic(pub_topic_id)
            if cached_pub_topic:
                return cached_pub_topic

        projection = {
            "name_zh": 1,
            'name': 1,
            'def_zh': 1,
            'def': 1,
            'must_reading_count': 1,
            'must_reading': 1,
            'num_view': 1,
            'num_like': 1,
            'created_time': 1,
        }
        topics = self.mongo.find_by_id("aminer", "pub_topic", pub_topic_id, projection)
        if len(topics) <= 0:
            logger.warning("not found pub_topic by id {}".format(pub_topic_id))
            return {}

        topic = topics[0]
        # generate labels
        channel_ids = topic.get('channel', [])
        if channel_ids:
            channels = self.mongo.find_by_ids("aminer", "must_reading_channel", channel_ids, {'name_zh': 1, 'name': 1})
            labels = [x.get('name') for x in channels]
            labels_zh = [x.get('name_zh') for x in channels]
        else:
            labels = []
            labels_zh = []

        must_reading_paper = {}
        must_reading_papers = []
        authors_frequency = {}   # {author_id: {count: int, ....}}
        if 'must_reading' in topic and isinstance(topic.get("must_reading"), list):
            for idx, p in enumerate(topic.get("must_reading")):
                if 'pid' in p:
                    paper = self.preload_pub(p['pid'])
                    if not must_reading_paper:
                        must_reading_paper = paper

                    if idx <= 3:
                        must_reading_papers.append(paper)

                    for author in paper.get("authors", []):
                        author_id = author.get("id")
                        if author_id in authors_frequency:
                            authors_frequency[author_id]['count'] += 1
                        else:
                            authors_frequency[author_id] = author
                            authors_frequency[author_id].update({
                                'count': 1
                            })

        authors = sorted(list(authors_frequency.values()), key=lambda x: x['count'], reverse=True)[:6]

        clean_topic = {
            'id': str(topic.get('_id')),
            'type': 'pub_topic',
            'title': topic.get('name'),
            'title_zh': topic.get('name_zh'),
            'content': topic.get("def"),
            'content_zh': topic.get("def_zh"),
            'abstract': '',
            'label': '',
            'url': '',
            'venue': '',
            'nodeNum': topic.get('must_reading_count', 0),
            'authors': authors,
            'must_reading_paper': must_reading_paper,
            'must_reading_papers': must_reading_papers,
            'labels': labels,
            'labels_zh': labels_zh,
            'ts': topic.get('created_time').strftime(Constants.SQL_DATETIME_FORMAT) if topic.get('created_time') else "",
        }

        cache_key = self.get_pub_topic_cache_key(pub_topic_id)
        self.redis_connection.setex(cache_key, 30*3600*24, gzip.compress(json.dumps(clean_topic).encode()))
        return clean_topic

    def get_report_cache_key(self, report_id: str):
        return "{}_report_{}".format(self.name, report_id)

    def get_cached_report(self, report_id: str) -> dict:
        cache_key = self.get_report_cache_key(report_id)
        cache_data_raw = self.redis_connection.get(cache_key)
        if cache_data_raw:
            return json.loads(gzip.decompress(cache_data_raw))

        return {}

    def preload_report(self, report_id: str, use_cache: bool = True) -> dict:
        """
        :param report_id:
        :param use_cache:
        :return:
        """
        if use_cache:
            cached_data = self.get_cached_report(report_id)
            if cached_data:
                return cached_data

        projection = {
            "title": 1,
            'content': 1,
            'abstract': 1,
            'like': 1,
            'author': 1,
            'image': 1,
            'created_time': 1,
        }
        reports = self.mongo.find_by_id("tracking", "articles", report_id, projection)
        if len(reports) <= 0:
            logger.warning("not found report by id {}".format(report_id))
            return {}

        report = reports[0]
        clean_report = {
            'id': str(report.get('_id')),
            'type': 'report',
            'title': report.get('title'),
            'content': "",
            'abstract': report.get("abstract"),
            'label': '',
            'url': '',
            'venue': report.get('author'),
            'nodeNum': report.get('like'),
            'authors': [],
            'figureUrls': [report.get('image')],
            'created_time': report.get('created_time').strftime("%Y-%m-%d") if 'created_time' in report else "",
        }

        cache_key = self.get_report_cache_key(report_id)
        self.redis_connection.setex(cache_key, 30*3600*24, gzip.compress(json.dumps(clean_report).encode()))
        return clean_report

    def preload_items(self, items, use_cache=False):
        """ Load items from mongodb or web api, then save them to redis.

        :param use_cache:
        :param items: list of (item id, score, item type, from)
        :param pbar: process bar
        :return:
        """
        for item in items:
            if not item or not item[0]:
                continue
            item_id = str(item[0].strip())
            if not is_mongo_id(item_id):
                continue
            item_type = item[2] if len(item) > 2 else ''

            if item_type == self.ITEM_PUB:
                self.preload_pub(item_id, use_cache)
            elif item_type == self.ITEM_PUB_TOPIC:
                self.preload_pub_topic(item_id, use_cache)
            elif item_type == self.ITEM_PERSON:
                self.preload_person(item_id, use_cache)
            elif item_type == self.ITEM_AI2K:
                self.preload_ai2k(item_id, use_cache)
            else:
                logger.warning("unknown item type {}".format(item_type))

