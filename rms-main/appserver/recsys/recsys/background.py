import gzip
import json

from django_rq import job
from celery import shared_task

from recsys.algorithms.aggregate import Aggregate
from recsys.algorithms.native import AlgorithmNativeUpdate, SubscribeRecall
from recsys.algorithms.constants import Constants
from recsys.algorithms.subscribe_stat import SubscribeStat
from recsys.algorithms.make_top import MakeTop
import logging


logger = logging.getLogger(__name__)


#@job
@shared_task(queue="default")
def pingback_click_handle(uid, ud, pub_id):
    do_pingback_click_handle(uid, ud, pub_id)

    alg = AlgorithmNativeUpdate()
    recommendations = alg.get_non_keyword_rec_cache(uid, ud)
    if recommendations:
        recommendations['rec'] = alg.resort_recommendations(recommendations['rec'], uid, ud)

    cache_key = alg.get_non_keyword_rec_cache_key(uid, ud)
    zip_data = gzip.compress(json.dumps(recommendations, ensure_ascii=True).encode("utf-8"))
    alg.redis_connection.setex(cache_key, Constants.RECOMMENDATION_CACHE_TIME, zip_data)


def do_pingback_click_handle(uid, ud, pub_id):
    if not ud and not uid:
        logger.warning("ud '{}' and uid {} are none".format(ud, uid))
        return False

    # update click history
    if pub_id:
        agg = Aggregate()
        person_click_history_cache_key = agg.get_person_click_history_key(uid, ud)
        agg.redis_connection.zadd(person_click_history_cache_key, {pub_id: 1}, incr=True)

        person_click_paper_cache_key = agg.get_person_click_paper_key(uid, ud, pub_id)
        agg.redis_connection.incr(person_click_paper_cache_key)

        agg.increase_pub_num_view(pub_id)

        # shrink excess word
        current_num_pub = agg.redis_connection.zcard(person_click_history_cache_key)
        if current_num_pub > agg.UD_MAX_NUM_SHOW:
            all_pub_ids = agg.redis_connection.zrange(person_click_history_cache_key, 0, current_num_pub, True, False)
            for pub_id in all_pub_ids:
                pub_cache_key = agg.get_person_click_paper_key(uid, ud, pub_id)
                if agg.redis_connection.exists(pub_cache_key) == 0:
                    agg.redis_connection.zrem(person_click_history_cache_key, pub_id)

    return True


#@job
@shared_task(queue="default")
def pingback_show_handle(uid, ud, pub_id, keyword=""):
    """ Save user show paper id to redis
    :param uid:
    :param ud:
    :param pub_id:
    :param keyword:
    :return:
    """
    do_pingback_show_handle(uid, ud, pub_id, keyword)


def do_pingback_show_handle(uid, ud, pub_id, keyword=""):
    """ Save user show paper id to redis
    :param uid:
    :param ud:
    :param pub_id:
    :param keyword:
    :return:
    """
    if not ud and not uid:
        logger.warning("ud and uid are all none, don't update redis cache")
        return False

    if not pub_id:
        logger.warning("pub_id is not found")
        return False

    # update show history
    agg = Aggregate()
    person_show_history_cache_key = agg.get_person_show_history_key(uid, ud)
    agg.redis_connection.zadd(person_show_history_cache_key, {pub_id: 1}, incr=True)

    person_show_paper_cache_key = agg.get_person_show_paper_key(uid, ud, pub_id)
    agg.redis_connection.incr(person_show_paper_cache_key)

    # update subscribe stat
    if uid and keyword:
        ss = SubscribeStat(uid)
        ss.omit_keyword(keyword)

    # shrink too old pub
    current_num_pub = agg.redis_connection.zcard(person_show_history_cache_key)
    if current_num_pub > agg.UD_MAX_NUM_SHOW:
        all_pub_ids = agg.redis_connection.zrange(person_show_history_cache_key, 0, current_num_pub, True, False)
        for pub_id in all_pub_ids:
            pub_cache_key = agg.get_person_show_paper_key(uid, ud, pub_id)
            if agg.redis_connection.exists(pub_cache_key) == 0:
                agg.redis_connection.zrem(person_show_history_cache_key, pub_id)

    return True


#@job("refresh")
@shared_task(queue="refresh")
def refresh_event_handle(uid, ud, keyword, **kwargs):
    if not uid:
        return 0

    alg = AlgorithmNativeUpdate()
    if keyword and len(keyword) > 0:
        count = alg.update_keyword_recommendation(uid, ud, keyword)
    else:
        count = alg.update_non_keyword_recommendation(uid, ud, recall_names=['SubscribeRecall', 'SubscribeOAGRecall', 'SubscribeKGRecall'])

    if 0 < count < 10:
        logger.warning("uid {}, ud {}, keyword {}, there are only {} recommendations".format(
            uid, ud, keyword, count))

    return count


#@job("subscribe")
@shared_task(queue="subscribe")
def subscribe_del_handle(uid: str, subscribe_word: str) -> int:
    if not uid:
        return 0
    alg = AlgorithmNativeUpdate()
    count = alg.update_non_keyword_recommendation(uid, None, recall_names=[SubscribeRecall.__name__])
    return count


#@job("subscribe")
@shared_task(queue="subscribe")
def subscribe_add_handle(uid: str, subscribe_word: str) -> int:
    if not uid:
        return 0
    alg = AlgorithmNativeUpdate()
    count = alg.update_non_keyword_recommendation(uid, None, recall_names=[SubscribeRecall.__name__])
    return count


#@job
@shared_task(queue="default")
def preload_lost_items(items):
    """
    :param items: list of (item id, score, item type, from)
    :return:
    """
    Aggregate().preload_items(items)
    return len(items)


#@job
@shared_task(queue="default")
def make_top_train():
    MakeTop().train()
