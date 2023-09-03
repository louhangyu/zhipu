"""Algorithm of near neighbours
"""
import codecs
import os
import json
import datetime
import logging
import time
from tqdm import tqdm
import requests
import typesense
from concurrent.futures import ThreadPoolExecutor 

from recsys.algorithms.constants import Constants
from recsys.utils import standard_score, null_to_blank
from recsys.models import MongoConnection, HighQualityPaper
from recsys.algorithms.redis_connection import RedisConnection
from recsys.algorithms.subscribe_stat import SubscribeStat
from recsys.algorithms import get_sentence_model, get_contriever_model, get_token_model, \
    sentence_model_name, contriever_model_name, get_vector_cosine

from django.conf import settings
from django.utils import timezone
from django.db import close_old_connections


logger = logging.getLogger(__name__)
oagbert_collection = None


class PaperIndex:
    def __init__(self, path=settings.FAISS_PAPER_PATH, timeout=3, prev_days=365):
        self.path = path
        self.max_count = 10000*20
        self.indexed_paper_ids_set = set()
        self.search_client = typesense.Client(settings.TYPESENSE_SEARCH)
        self.timeout = timeout

        self.index_name = "paper"
        self.too_old_pub_ids = []
        self.last_ts = timezone.now() - datetime.timedelta(prev_days)
        self.schema = {
            'name': self.index_name,
            'fields': [
                {'name': 'tags', 'type': 'string[]'},
                {'name': 'subject_zh', 'type': 'string'},
                {'name': 'subject_en', 'type': 'string'},
                {'name': 'title', 'type': 'string'},
                {'name': 'abstract', 'type': 'string'},
                {'name': 'keywords', 'type': 'string[]'},
                {'name': 'venue', 'type': 'string'},
                {'name': 'authors', 'type': 'string[]'},
                {'name': 'affiliations', 'type': 'string[]'},
                {'name': '_id', 'type': 'string', "index": False, "optional": True},
                {'name': 'id', 'type': 'string'},
                {'name': 'id_of_mysql', 'type': 'int32', "index": False, "optional": True},
                {'name': 'year', 'type': 'int32'},
                {'name': 'ts', 'type': 'string', "index": False, "optional": True},
                {'name': 'category', 'type': 'string'},
                {'name': 'ts_timestamp', 'type': 'int32'},
            ],
            'default_sorting_field': 'ts_timestamp',
            "token_separators": [
                '-', 
                '.', 
                ':', 
                "=", 
                '#', 
                '&', 
                '_', 
                '(', 
                ')', 
                '<', 
                '>', 
                '{', 
                '}', 
                '\'', 
                '\"', 
                '*', 
                '/', 
                '%', 
                '@', 
                '|', 
                '!', 
                '[', 
                ']', 
                ';',
                '$',
                '?',
                '~',
                '^',
                '`',
            ]
        }

    def train(self) -> int:
        self.load_indexed_papers()

        new_papers = self.get_new_papers()
        if not new_papers:
            logger.warning("new papers are empty")
            return 0

        step = 1000
        for i in tqdm(range(0, len(new_papers) + 1, step), desc="Add new papers"):
            bulk = new_papers[i:i+step]
            for j in range(len(bulk)):
                bulk[j]['id'] = bulk[j]['_id']
            try:
                resp = self.search_client.collections[self.index_name].documents.import_(bulk, {'action': 'upsert', 'dirty_values': 'coerce_or_drop'})
                for j in range(len(resp)):
                    r = resp[j]
                    if r['success'] is False:
                        logger.warning("failed to insert {}: {}".format(bulk[j], r))
            except Exception as e:
                logger.warning("except when insert bulk: {}".format(e))

        if self.too_old_pub_ids:
            for pub_id in self.too_old_pub_ids:
                try:
                    self.search_client.collections[self.index_name].documents[pub_id].delete()
                except Exception as e:
                    logger.warning(f"except when del doc {pub_id}: {e}")

        return len(new_papers)

    def load_indexed_papers(self):
        docs = self.search_client.collections[self.index_name].documents.export().strip()
        if docs:
            for line in docs.split("\n"):
                doc = json.loads(line)
                self.indexed_paper_ids_set.add(doc['_id'])
                if doc['ts']:
                    ts = timezone.make_aware(datetime.datetime.strptime(doc['ts'], Constants.SQL_DATETIME_FORMAT))
                    if ts < self.last_ts:
                        self.too_old_pub_ids.append(doc['_id'])
                else:
                    self.too_old_pub_ids.append(doc['_id'])

        print("{}: has trained {}".format(datetime.datetime.now(), len(self.indexed_paper_ids_set)))

    def migrate(self):
        if self.exists():
            self.search_client.collections[self.index_name].update(self.schema)

    def drop(self):
        if self.exists():
            self.search_client.collections[self.index_name].delete()

    def create(self):
        if self.exists():
            return False
        self.search_client.collections.create(self.schema)
        return True

    def exists(self):
        all_indexes = self.search_client.collections.retrieve()
        all_indxes_name = [x['name'] for x in all_indexes]
        return self.index_name in all_indxes_name

    def rebuild(self):
        """Remove schema only, need to train again.
        """
        self.drop()

    def get_new_papers(self):
        new_papers = []
        new_paper_ids_set = set()

        if not os.path.exists(self.path):
            return []

        with tqdm(desc="read {}".format(self.path)) as bar:
            with codecs.open(self.path, encoding="utf-8") as f:
                for line in f:
                    try:
                        paper = json.loads(line)
                    except Exception as e:
                        logger.warning("[{}] can't parsed: {}".format(line, e))
                        continue
                    paper_id = paper['_id']
                    if paper_id in self.indexed_paper_ids_set:
                        continue
                    if paper_id in new_paper_ids_set:
                        continue
                    paper = self.tidy_paper(paper)

                    new_papers.append(paper)
                    new_paper_ids_set.add(paper_id)

                    bar.update()

        new_papers = sorted(new_papers, key=lambda x: x["ts"], reverse=True)
        new_papers = new_papers[:self.max_count]
        if new_papers:
            logger.info("new papers first {}, last {}".format(new_papers[0]['ts'], new_papers[-1]['ts']))
        return new_papers

    @classmethod
    def tidy_paper(cls, paper):
        paper['subject_en'] = null_to_blank(paper['subject_en'])
        paper['subject_zh'] = null_to_blank(paper['subject_zh'])
        paper['ts_timestamp'] = 0
        if 'ts' in paper and paper['ts']:
            paper['ts_timestamp'] = timezone.now().strptime(paper['ts'], Constants.SQL_DATETIME_FORMAT).timestamp()

        return paper

    def search_by_dict(self, paper:dict, k:int=100, debug:bool=False):
        """ Query from typesense and postgres
        :param paper: dict, format is
          {
              title: str,
              abstract: str,
              keywords: [str],
              venue: str,
              authors: [str],
              affiliations: [str]
          }
        :param k: the number of neighbours
        :param debug: if debug is true, return paper object in the tail
        :return:
           [(str, float, option[dict])]: returns list of (paper_id, distance, hit object)
        """
        # tidy data
        query = " ".join([str(x) for x in paper.values()])
        if isinstance(k, int) is False:
            k = int(k)

        try:
            resp = self.search_from_typesense(query, per_page=k)
        except Exception as e:
            logger.warning("exception when search {}, query {}: {}".format(paper, query, e))
            resp = None

        result = []
        if resp:
            for i, hit in enumerate(resp['hits']):
                if debug:
                    item = (hit['_id'], 1 - i / resp['nbHits'], hit)
                else:
                    item = (hit['_id'], 1 - i / resp['nbHits'])
                result.append(item)
        return result[:k]

    def search_from_typesense(self, q, query_by='title,abstract,venue,subject_zh,subject_en,tags,keywords,authors', query_by_weight="10,2,5,1,1,1,5,3", sort_by='_text_match:desc,year:desc,ts_timestamp:desc', per_page=100, **kwargs):
        """
        :param sort_by:
        :param q:
        :param query_by:
        :param options
               {
                  'q': '',
                  'query_by': 'title',
                  'sort_by': 'ts_timestamp:desc',
                  'filter_by': "ts_timestamp :> 1652510445",
                  'per_page': 100
               }
        :return: {nbHits: int, hits: [{}]}
        """
        try:
            options = {
                'q': q,
                'query_by': query_by,
                "query_by_weight": query_by_weight,
                'sort_by': sort_by,
                'filter_by': f"ts_timestamp :> {int(self.last_ts.timestamp())} && year :>= {self.last_ts.year - 1}",
                'per_page': per_page,
                "use_cache": True,
                "cache_ttl": 3600,
            }
            options.update(kwargs)
            logger.info("start search {}".format(options))
            resp = self.search_client.collections[self.index_name].documents.search(options)
            logger.info("search {}, response {}".format(options, resp['found']))
            result = {
                'nbHits': resp['found'],
                'hits': [x['document'] for x in resp['hits']],
            }
        except Exception as e:
            logger.warning("except when search {}: {}".format(options, e))
            return {}

        if not result['hits']:
            logger.warning("empty when search {}".format(options))

        return result


class PaperVectorIndex:
    """The table HighQualityPaper is source."""
    index_name = "paper_vector"
    SPLIT_TOKENS = [
        '-', 
        '.', 
        ':', 
        "=", 
        '#', 
        '&', 
        '_', 
        '(', 
        ')', 
        '<', 
        '>', 
        '{', 
        '}', 
        '\'', 
        '\"', 
        '*', 
        '/', 
        '%', 
        '@', 
        '|', 
        '!', 
        '[', 
        ']', 
        ';',
        '$',
        '?',
        '~',
        '^',
        '`',
    ]

    def __init__(self, prev_days=365*5, vector_dim=768):
        self.schema = {
            'name': self.index_name,
            'fields': [
                {'name': 'id', 'type': 'str'},  # mongodb doc id
                {'name': 'mysql_id', 'type': 'int32', "index": False, "optional": True},
                {'name': 'ts_timestamp', 'type': 'int32'},
                {'name': 'vector', 'type': 'float[]', 'num_dim': vector_dim},
            ],
            "token_separators": [
                '-', 
                '.', 
                ':', 
                "=", 
                '#', 
                '&', 
                '_', 
                '(', 
                ')', 
                '<', 
                '>', 
                '{', 
                '}', 
                '\'', 
                '\"', 
                '*', 
                '/', 
                '%', 
                '@', 
                '|', 
                '!', 
                '[', 
                ']', 
                ';',
                '$',
                '?',
                '~',
                '^',
                '`',
            ]
        }
        self.vector_db = typesense.Client(settings.VECTOR_DB)
        self.indexed_doc_ids = set()
        self.prev_days = prev_days
        self.last_ts = int((timezone.now() - datetime.timedelta(prev_days)).timestamp())

    def train(self):
        if self.exists() is False:
            self.create()

        new_pubs = self._extract_new_pubs()
        if len(new_pubs) == 0:
            return 0, 0
        batch_size = 100
        n_success = 0
        n_fail = 0
        with tqdm(total=len(new_pubs), desc="train vectors") as bar:
            with ThreadPoolExecutor(max_workers=8) as pool:
                for i in range(0, len(new_pubs) + 1, batch_size):
                    batch = new_pubs[i:i+batch_size]
                    batch_pub_ids = [x['paper_id'] for x in batch]
                    docs = []
                    for j, paper_vector in enumerate(pool.map(self._get_paper_vector, batch_pub_ids)):
                        bar.update()

                        if not paper_vector:
                            continue
                        mysql_id = batch[j]['id']
                        pub_id = batch[j]['paper_id']
                        ts = batch[j]['ts']
                        if ts:
                            doc = {
                                'id': pub_id,
                                "mysql_id": mysql_id,
                                "vector": paper_vector,
                                'ts_timestamp': ts.timestamp()
                            }
                            docs.append(doc)

                    if docs:
                        resp = self.vector_db.collections[self.index_name].documents.import_(docs, {'action': 'upsert', 'dirty_values': 'coerce_or_drop'})
                        for j in range(len(resp)):
                            r = resp[j]
                            if r['success'] is False:
                                logger.warning("failed to insert {}: {}".format(batch[j], r))
                                n_fail +=1
                            else:
                                n_success += 1
        print(f"success {n_success}, fail {n_fail}")
        return n_success, n_fail

    def _get_paper_vector(self, paper_id)  :
        from recsys.algorithms.aggregate import Aggregate

        agg = Aggregate()
        pub = agg.preload_pub(paper_id)
        if not pub:
            return [] 
        title = pub.get('title')
        title_zh = pub.get('title_zh')
        abstract = pub.get('abstract') 
        abstract_zh = pub.get('abstract_zh')
        year = pub.get('year')
        venue = pub.get('venue', {}).get('info', {}).get('name')
        keywords = pub.get('keywords')
        authors = pub.get('authors')
        text = "\n".join([
            f"title: {title}",
            f"title zh: {title_zh}",
            f"abstract: {abstract}",
            f"abstract zh: {abstract_zh}",
            f"year: {year}",
            f"venue: {venue}",
            f"keywords: {keywords}",
            f"authors: {authors}",
        ])
        return self._get_text_vector(text)
    
    @classmethod
    def _get_text_vector(cls, text, model_name=contriever_model_name) :
        if not text:
            return [] 
        logger.info(f"ready to get \"{text}\" vector")
        #for token in cls.SPLIT_TOKENS:
        #    text = text.replace(token, " ")
        #text = text.lower()
        if model_name == sentence_model_name:
            model = get_sentence_model() 
            embs = model.encode(text, show_progress_bar=False, normalize_embeddings=True)
            if isinstance(text, str):
                embs = embs.astype(float)
            else:
                embs = [x.astype(float) for x in embs]
        else:
            model = get_contriever_model()
            tokenizer = get_token_model()
            if isinstance(text, str):
                new_text = [text]
                inputs = tokenizer(new_text, padding=True, truncation=True, return_tensors="pt")
                embs = model(**inputs)
                embs = [list(x.detach().cpu().numpy().astype(float)) for x in embs]
                embs = embs[0]
            else:
                batch_size = 32
                sentences = text
                embs = []
                for i in range(0, len(sentences) + 1, batch_size):
                    batch = sentences[i:i+batch_size]
                    #assert not include blank string
                    assert(all([len(x.strip()) > 0 for x in batch]))
                    try:
                        inputs = tokenizer(batch, padding=True, truncation=True, return_tensors="pt")
                    except Exception as e:
                        logger.warning(f"except when tokenizer {batch}: {e}")
                        return []
                        
                    batch_embs = model(**inputs)
                    batch_embs = [list(x.detach().cpu().numpy().astype(float)) for x in batch_embs]
                    embs += batch_embs
        logger.info(f"text {text}, vector {embs}")
        return embs

    def _extract_new_pubs(self)  :
        """Returns: [{id: int, paper_id: str, ts: datetime}]"""
        self._load_all_indexed_docs()

        end = timezone.now()
        start = end - datetime.timedelta(self.prev_days)
        new_pubs = []
        step = 1000
        qs = HighQualityPaper.objects.filter(ts__range=(start, end))
        total = qs.count()
        with tqdm(desc="load paper from db", total=total) as bar:
            for i in range(0, total + 1, step):
                pubs = qs.values('id', 'paper_id', "ts")[i:i+step]
                bar.update(n=len(pubs))
                new_pubs += list(filter(lambda x: x['paper_id'] not in self.indexed_doc_ids, pubs))
        return new_pubs

    def _load_all_indexed_docs(self):
        '''from vector db'''
        source = self.export()
        for line in tqdm(source.split("\n"), desc="load all indexed docs"):
            if not line:
                continue
            doc = json.loads(line)
            self.indexed_doc_ids.add(doc['id'])
        logger.info(f"indexed {len(self.indexed_doc_ids)} docs")

    def migrate(self):
        if self.exists():
            self.vector_db.collections[self.index_name].update(self.schema)
    
    def export(self):
        return self.vector_db.collections[self.index_name].documents.export()

    def drop(self):
        if self.exists():
            self.vector_db.collections[self.index_name].delete()

    def create(self):
        if self.exists():
            return False
        self.vector_db.collections.create(self.schema)
        return True

    def exists(self):
        all_indexes = self.vector_db.collections.retrieve()
        all_indxes_name = [x['name'] for x in all_indexes]
        return self.index_name in all_indxes_name

    def rebuild(self):
        """Remove schema only, need to train again.
        """
        self.drop()
        self.create()

    def search_by_dict(self, paper:dict, k:int=100, debug:bool=False):
        """ Query from vector db and postgres
        :param paper: dict, format is
          {
              title: str,
              abstract: str,
              keywords: [str],
              venue: str,
              authors: [str],
              affiliations: [str]
          }
        :param k: the number of neighbours
        :param debug: if debug is true, return paper object in the tail
        :return:
           [(str, float, option[dict])]: returns list of (paper_id, score, hit object)
        """
        start_time = time.time()
        paper_text = "\n".join([f"The {name} is {value}" for name, value in paper.items()])
        paper_vector = self._get_text_vector(paper_text)
        logger.info(f"get text vector {paper_text}, spends {time.time() - start_time}s")
        if not paper_vector:
            logger.warning(f"{paper} vector is null, {paper_vector}")
            return []

        start_time = time.time()
        if isinstance(k, int) is False:
            k = int(k)

        options = {
            'searches': [
                {
                    'collection': self.index_name,
                    'q': '*',
                    'vector_query': f'vector:({paper_vector}, k:{k})',
                    'filter_by': f'ts_timestamp:>{self.last_ts}',
                    "per_page": k,
                }
            ]
        }
        resp = self.vector_db.multi_search.perform(options, {})
        first_resp = resp['results'][0]
        result = []
        if 'hits' in first_resp:
            for i, hit in enumerate(first_resp['hits']):
                score = get_vector_cosine(paper_vector, hit['document']['vector'])
                if debug:
                    item = (hit['document']['id'], score, hit)
                else:
                    item = (hit['document']['id'], score)
                result.append(item)
        result = result[:k]
        logger.info(f"search done, spends {time.time() - start_time}s")
        return result


class PaperGPTVectorIndex(PaperVectorIndex):
    index_name = "paper_gpt_index"

    def __init__(self, prev_days=365 * 5, vector_dim=1536):
        super().__init__(prev_days, vector_dim)
    
    @classmethod
    def _get_text_vector(cls, text, timeout=300) :
        openai_key = settings.OPENAI_KEY
        proxy_host = "172.22.245.17"
        proxy_port = 3128
        proxy_servers = {
            "http": f"http://{proxy_host}:{proxy_port}",
            "https": f"http://{proxy_host}:{proxy_port}",
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {openai_key}"
        }
        body = {
            'model': "text-embedding-ada-002",
            'input': text.strip()
        }
        url = "https://api.openai.com/v1/embeddings"
        try:
            r = requests.post(url, headers=headers, json=body, proxies=proxy_servers, timeout=timeout)
        except Exception as e:
            logger.warning(f"get embedding for {text} from {url} except: {e}")
            return []

        if r.status_code != 200:
            logger.warning(f"status code {r.status_code} when request {body}")
            return [] 
        data = r.json()
        logger.info(f"url {url}, request {body}, resp {data}")
        
        return data['data'][0]['embedding']