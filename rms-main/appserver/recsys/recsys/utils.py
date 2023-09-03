import datetime
import hashlib
import logging
import math
import re
import time
import requests
from urllib.parse import quote
from bson import ObjectId
import translators
import uuid
#translators.preaccelerate()

from django.utils.timezone import now
from django.utils import timezone
from django.core.mail import send_mail
from django.db import connection
from django.conf import settings
from django.core.paginator import Paginator, Page


logger = logging.getLogger(__name__)


def get_request_ip(request):
    if "HTTP_X_FORWARDED_FOR" in request.META:
        ips = request.META['HTTP_X_FORWARDED_FOR'].split(",")
        if len(ips) <= 0:
            return ""

        ip = ips[0]
    else:
        ip = request.META['REMOTE_ADDR']
    return ip


class Report:

    def __init__(self):
        self.end = timezone.make_naive(now())
        self.start = self.end - datetime.timedelta(7)
        self.start = self.start.replace(hour=0, minute=0, second=0)
        self.receivers = settings.REPORT_RECEIVERS
        logger.info("start {}, end {}".format(self.start, self.end))

    def collect(self):
        date_format = "%Y-%m-%d"
        sql = """
        select 
          "day",
          sum(click),
          sum("show"),
          count(ud),
          case 
            when sum("show") > 0 then TRUNC(sum(click)::decimal / sum("show"), 4)
            else 0 
            end as ctr
        from 
          recsys_actionlog_day_ud_stat
        where
          "show" > 6 and 
          "show" < 200 and
          "day" >= %s and
          "day" <= %s
        group by
          "day"
        order by "day"
        """
        message = ""
        headers = ["Day", "Clean-CTR", "Click", "Show", "UD"]
        message += "{:15s} {:10s} {:10s} {:16s} {:15s}".format(headers[0], headers[1], headers[2], headers[3],
                                                               headers[4])
        message += "\r\n"
        with connection.cursor() as cursor:
            cursor.execute(sql, (self.start.strftime(date_format), self.end.strftime(date_format)))
            for row in cursor.fetchall():
                day = row[0].strftime(date_format)
                ctr = float(row[4])
                show = int(row[2])
                click = int(row[1])
                ud = row[3]
                message += "{:10s} {:10.4f} {:>16d} {:>15d} {:>10d}".format(day, ctr, click, show, ud)
                message += "\r\n"

        message += "\r\n-------Thanks\r\n"

        return message

    def send(self):
        print("Ready to send")
        title = "Aminer CTR Report at {}".format(now().date())
        message = self.collect()
        print("{}".format(message))

        send_mail(title, message, from_email=None, recipient_list=self.receivers)
        print("send done")


def checksum_is_valid(request) -> bool:
    checksum = request.GET.get('checksum')
    device = request.GET.get("device")

    if device is None:
        return True

    if not checksum:
        return False

    params = []
    for name, value in request.GET.items():
        if name == "checksum":
            continue

        params.append((name, quote(value)))

    params = sorted(params, key=lambda x: x[0])
    secret = "&".join(["{}={}".format(x[0], x[1]) for x in params])
    encrpyed = hashlib.md5(secret.encode()).hexdigest()
    logger.info("secret {}, expected checksum {}, checksum {}".format(secret, encrpyed, checksum))
    if encrpyed == checksum:
        return True

    return False


def tidy_paper_for_ann(record:dict) -> dict:
    """
    :param record: dict from mongodb aminer.publication_dupl
        {
            'type': 'pub',
            'authors': authors,
            'data2videoUrl': pdf_info.get('data2videoUrl'),
            'doi': pub.get('doi'),
            'figureUrls': pdf_info.get('metadata', {}).get('figure_urls', None),
            'id': str(pub['_id']),
            'num_citation': pub.get('n_citation', 0),
            'num_viewed': None,
            'pages': {
                "start": pub.get('page_start'),
                "end": pub.get('page_end'),
            },
            'pdf': pub.get('pdf'),
            'title': pub.get('title'),
            'urls': pub.get('url'),
            'venue': {
                'info': {
                    'name': venue_info.get('Name'),
                    'short': venue_info.get('Short')
                }
            },
            'year': pub.get('year'),
            'summary': pdf_info.get('headline'),
            'abstract': pub.get('abstract'),
            'keywords': pdf_info.get('keywords'),
            'graph_keywords': []
        }
    :return:
       {
            "title": str, 
            "title_zh": str, 
            "abstract": str, 
            "abstract_zh": str, 
            "keywords": [str], 
            "venue": str, 
            "authors": [str], 
            "affiliations": [str] 
        }
    """
    if 'title' not in record and 'title_zh' not in record:
        return {}

    if record.get('title') is None or record.get('title_zh') is None:
        return {}

    result = {
        '_id': str(record['id']),
        'title': record['title'] or '',
        'title_zh': record['title_zh'] or '',
        'abstract': record.get('abstract') or "",
        'abstract_zh': record.get('abstract_zh') or "",
        'keywords': record.get('keywords') or [],
        'venue': record.get("venue", {}).get("info", {}).get("name") or "",
        'authors': [],
        'affiliations': [],
    }

    author_names = []
    for author in record.get('authors', []):
        if 'name' in author:
            author_names.append(author['name'])

    # authors
    result['authors'] = author_names

    # affiliations
    orgs = []
    for author in record.get('authors', []):
        if 'org' in author and author['org']:
            orgs.append(author['org'])
    result['affiliations'] = orgs
    return result


def standard_score(items, score_name="score"):
    """ Use standard algorithm (X - mu) / delta to compute new score
    :param items: list of {}
    :param score_name: str, score name
    :return: Returns items with standard score between 0 and 1
    """
    if not items:
        return items
    if len(items) < 2:
        return items
    mu = sum([x[score_name] for x in items]) / len(items)
    dev = sum([(x[score_name] - mu)**2 for x in items]) / (len(items))
    if dev == 0:
        return items
    stddev = math.sqrt(dev)

    for i in range(len(items)):
        z = (items[i][score_name] - mu) / stddev
        new_score = (1.0 + math.erf(z / math.sqrt(2.0))) / 2.0
        items[i][score_name] = new_score

    return items


def is_mongo_id(id_str):
    if ObjectId.is_valid(id_str):
        return True
    else:
        return False


def nan_to_blank(raw):
    if isinstance(raw, float) and math.isnan(raw):
        return ""
    else:
        return raw


def null_to_blank(raw):
    if raw is None:
        return ""
    return raw

chinese_pattern = re.compile('[\u4e00-\u9fff]')
def is_chinese(source) -> bool:
    if chinese_pattern.search(source) != None:
        return True
    return False


def translate_to_english(text, timeout=30):
    if is_chinese(text) is False:
        return text, ""
    
    return translate_text(text, timeout=timeout)


def translate_to_chinese(text, timeout=30):
    if is_chinese(text) is True:
        return text, ""
    
    return translate_text(text, timeout=timeout, to_language="zh")


def translate_text(ch, timeout=30, from_language="auto", to_language="en"):
    """Returns: target_text, translator"""

    supplies = [
        "deepl",
        "bing",
        "baidu",
        "alibaba"
    ]

    for supply in supplies:
        try:
            eng = translators.translate_text(ch, translator=supply, if_use_preacceleration=False, timeout=timeout)
            if eng:
                break
        except Exception as e:
            logger.warning("except when translate {}: {}".format(ch, e))
            continue

    if not eng:
        return None, None

    return eng.strip(), supply


def remove_duplicate_blanks(text:str) -> str:
    '''Remove all duplicate blanks'''
    if not text:
        return text
    result = re.sub(r'\n+', ' ', text)  # Replace multiple line breaks with a single space
    result = re.sub(r'\s{2,}', ' ', result)  # Replace multiple whitespaces with a single space
    result = result.strip()  # Remove leading and trailing whitespaces
    return result 


def do_paginator(qs, page:int, page_size: int=10) -> Page:
    paginator = Paginator(qs, page_size)
    pager = paginator.page(page)
    return pager


class YoudaoTranslate:

    def __init__(self, timeout=3) -> None:
        self.url = "https://openapi.youdao.com/api"
        self.appid = "7aae9fd69b5e628d"
        self.appkey = "EtbEIw1ukO7x41wybM9DVIKyA7PoPAyB"
        self.timeout = timeout

    def translate_to_chinese(self, text):
        if is_chinese(text):
            return text
        
        return self._translate(text, "auto", "zh-CHS")
    
    def translate_to_english(self, text):
        if is_chinese(text) is False:
            return text
        
        return self._translate(text, "auto", "en")
    
    def _translate(self, text:str, from_language:str, to_language:str) -> str:
        params = {
            'q': text,
            'from': from_language,
            'to': to_language,
            'appKey': self.appid,
            'salt': str(uuid.uuid1()),
            'curtime': int(time.time()),
            'signType': 'v3',
        }
        params['sign'] = self._generate_sign(params)
        try:
            r = requests.get(self.url, params=params, timeout=self.timeout)
        except Exception as e:
            logger.warning(f"except when get {self.url}, params {params}: {e}")
            return text
        
        resp_data = r.json()
        if 'translation' not in resp_data:
            logger.warning(f"failed when get {self.url}, params {params}: {resp_data}")
            return text
        
        result = "\n".join(resp_data['translation'])
        logger.info(f"{from_language} {text} -> {to_language} {result}")
        return result
        
    def _generate_sign(self, params: dict) -> str:
        raw = f"{self.appid}{self._get_input(params['q'])}{params['salt']}{params['curtime']}{self.appkey}"
        raw_binary = raw.encode()
        return hashlib.sha256(raw_binary).hexdigest()

    def _get_input(self, q:str) -> str:
        if len(q) <= 20:
            return q
        return f"{q[:10]}{len(q)}{q[-11:]}"

