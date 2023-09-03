import json
import logging
import asyncio

from django.utils.timezone import now
from django.utils import timezone
from django.http import HttpResponse, JsonResponse, HttpResponseForbidden, StreamingHttpResponse
from django.views.decorators.http import condition
from django.conf import settings

from recsys.algorithms.constants import Constants
from recsys.algorithms.aggregate import Aggregate
from recsys.algorithms.interest import Interest
from recsys.algorithms.native import AlgorithmNativeApi
from recsys.algorithms.recall_favorite import RecallFavorite
from recsys.models import ActionLog, ChatRound
from recsys.utils import get_request_ip, checksum_is_valid, is_mongo_id, do_paginator
from recsys.background import pingback_click_handle, pingback_show_handle, refresh_event_handle
from recsys.chat import ChatWithUser


logger = logging.getLogger(__name__)


def recommend_v3(request):
    """ Handle recommend from nodejs, response data same as previous
    :param request:
        [
            {
                "parameters": {
                    "num": 6,
                    "exclude_ids": [],
                    "keywords": [],
                    "uid": "",
                    "ud": "",
                    "first_reach": "",
                },
            }
        ]
    :return:
    """
    if request.method == "OPTIONS":
        return HttpResponse("", status=204)

    try:
        if request.method == "GET":
            body_json = json.loads(request.GET.get('body'))[0]
        elif request.method == 'POST':
            body_json = json.loads(request.body)[0]
        else:
            raise ValueError(f"unknow method {request.method}")
    except Exception as e:
        return HttpResponse(f"{e}", status=403)

    logger.info("receive request body: {}".format(body_json))

    parameters = body_json.get('parameters')
    ud = request.COOKIES.get("_Collect_UD")
    if not ud:
        ud = parameters.get('ud')
    # ab_flag = request.COOKIES.get("abflag")
    ab_flag = Aggregate.transfer2abflag(ud)

    # chat service 
    bussiness = parameters.get("bussiness") 
    stream = parameters.get('stream')
    if bussiness:
        if bussiness == "chat":
            if stream:
                return chat_service_stream(request)
            else:
                return chat_service(request)
        elif bussiness == "chat_history":
            return chat_history_service(request)

    # get business parameters
    try:
        num = int(parameters.get('num', '6'))
        exclude_ids = parameters.get('exclude_ids', [])
        keywords = parameters.get('keywords', [])
        keywords = list(filter(lambda x: x is not None and x.strip() != "", keywords))
        uid = parameters.get('uid')
        first_reach = parameters.get("first_reach")
        alg_flag = parameters.get("alg_flag")
        user_agent = request.META.get('HTTP_USER_AGENT') or ""
        recalls = parameters.get('recalls', [])
    except Exception as e:
        logger.warning("failed to extract parameters: {}".format(e))
        return HttpResponse("", status=403)

    agg = Aggregate()
    candidate_num = num * 20
    prediction = agg.re_ranking(uid, ud, candidate_num, ab_flag=ab_flag, keywords=keywords, exclude_ids=exclude_ids,
                                first_reach=first_reach, user_agent=user_agent, alg_flag=alg_flag)
    prediction_data = prediction.get('data', [])
    item_id_type_and_item_map = agg.get_cached_items(prediction_data)
    offset = 0
    epubs = []
    for r in prediction_data:
        item_id = r['item']
        item_type = r['type']
        recall_type = r['recall_type']

        if recall_type not in recalls and recalls:
            continue

        if (item_id, item_type) not in item_id_type_and_item_map:
            continue

        item = item_id_type_and_item_map[(item_id, item_type)]
        labels = []
        labels_zh = []
        if keywords:
            labels += keywords
            labels_zh += keywords

        if 'labels' in item:
            labels += item.get('labels', [])
        if 'labels_zh' in item:
            labels_zh += item.get("labels_zh", [])

        if 'id' not in item:
            item['id'] = item_id

        if item_type == agg.ITEM_PUB:
            e_person = {}
            if item.get("authors", []):
                e_person = item['authors'][0]
            epubs.append({"e_pub": [item], "e_person": e_person, "mrt": True, "id": item_id, 'labels': labels, 'labels_zh': labels_zh})
        else:
            epubs.append({"e_pub": [item], "id": item_id, 'labels': labels, 'labels_zh': labels_zh})

        if recall_type != Constants.RECALL_TOP:
            offset += 1

        if offset >= num:
            break

    data = {
        "data": [
            {
                "data": epubs,
                "succeed": True
            }
        ],
        "meta": {
            'ud': ud,
            'uid': uid,
            'version': settings.APP_VER,
        }
    }
    if 'meta' in prediction:
        data['meta'].update(prediction['meta'])

    return JsonResponse(data)


def pingback(request):
    if request.method == "OPTIONS":
        return HttpResponse("")

    uid = request.GET.get('uid')
    if uid and is_mongo_id(uid) is False:
        return HttpResponseForbidden("uid is invalid")
    ud = request.GET.get("ud")
    ls = request.GET.get("ls")
    if ls and ls.isnumeric():
        ls = int(ls)
    else:
        ls = None
    pub_ids = request.GET.get('pub_ids')
    if pub_ids and is_mongo_id(pub_ids) is False:
        return HttpResponseForbidden("pub_ids is invalid")
    keywords = request.GET.get('keywords')
    action = ActionLog.str2action(request.GET.get('action'))
    pb_type = ActionLog.str2type(request.GET.get('type', "pub"))
    author_id = request.GET.get("author_id")
    if author_id and is_mongo_id(author_id) is False:
        return HttpResponseForbidden("author id is invalid")
    ip = get_request_ip(request)
    device = request.GET.get("device")
    recall_type = request.GET.get("recall_type")
    if recall_type and recall_type not in Constants.RECALL_TYPES:
        return HttpResponseForbidden(content="recall type is invalid")
    first_reach = request.GET.get("first_reach")
    first_reach_format = "%Y-%m-%d %H:%M:%S"
    if first_reach:
        try:
            first_reach = now().strptime(first_reach, first_reach_format)
            first_reach = timezone.make_aware(first_reach)
        except Exception as e:
            logger.warning("first reach '{}' format is invalid: {}".format(first_reach, e))
            return HttpResponseForbidden("first reach is invalid")

    if not action:
        return HttpResponseForbidden(content="action is null")

    if checksum_is_valid(request) is False:
        logger.warning("request {} checksum is invalid".format(request.GET))
        return HttpResponseForbidden(content="checksum invalid")

    if action == ActionLog.ACTION_SEARCH:
        query = request.GET.get('query')
        if not query:
            return HttpResponseForbidden(content="query is blank")
    else:
        query = None

    ab_flag = Aggregate.transfer2abflag(ud)
    obj = ActionLog.objects.create(
        uid=uid,
        ud=ud,
        ls=ls,
        pub_ids=pub_ids,
        keywords=keywords,
        action=action,
        type=pb_type,
        ip=ip,
        author_id=author_id,
        abflag=ab_flag,
        device=device,
        first_reach=first_reach,
        recall_type=recall_type,
        query=query
    )

    # call background task
    if action == ActionLog.ACTION_CLICK:
        pingback_click_handle.delay(uid, ud, pub_ids)
    elif action == ActionLog.ACTION_SHOW:
        pingback_show_handle.delay(uid, ud, pub_ids, keywords)
    elif action == ActionLog.ACTION_SEARCH:
        refresh_event_handle.delay(uid, ud, None)

    return JsonResponse({"id": obj.id, "abflag": ab_flag})


def get_meta_data(request):
    uid = request.GET.get("uid")
    ud = request.GET.get("ud")

    agg = Aggregate()
    browse_pubs = agg.get_person_show_papers(uid, ud)
    click_pubs = agg.get_person_click_papers(uid, ud)

    native_mr = AlgorithmNativeApi()
    non_keyword_rec = native_mr.fetch_non_keyword_recommendations(uid, ud, num=1000)

    recall_favorite = RecallFavorite().predict(uid, ud)
    data = {
        "recall": recall_favorite,
        "browse": {
            "count": len(browse_pubs),
            "pubs": browse_pubs
        },
        "click": {
            "count": len(click_pubs),
            "pubs": click_pubs
        },
        "native_mr": {
            'count': len(non_keyword_rec),
            'non_keyword_cache_key': native_mr.get_non_keyword_rec_cache_key(uid, ud),
            'non_keyword': non_keyword_rec
        }
    }
    return JsonResponse(data)


def chat_service(request):
    try:
        body_json = json.loads(request.body)[0]
    except Exception as e:
        logger.warning("request body is no valid {}: {}".format(request.body, e))
        return HttpResponse("", status=403)

    parameters = body_json.get('parameters')
    uid = parameters.get("uid")
    message = parameters.get("message")
    round_id = parameters.get('round_id')
    if not uid:
        return JsonResponse({"is_ok": False, "error_msg": "uid is null", "error_code": 403})
    chat_with_user = ChatWithUser(uid=uid)
    resp = chat_with_user.receive_message(message, round_id)
    return JsonResponse(resp)


def chat_service_stream(request):
    try:
        body_json = json.loads(request.GET.get('body'))[0]
    except Exception as e:
        logger.warning(f"request is no valid {request.GET}: {e}")
        return HttpResponse(f"{e}", status=403)

    parameters = body_json.get('parameters')
    uid = parameters.get("uid")
    message = parameters.get("message")
    round_id = parameters.get('round_id')
    if not uid:
        return JsonResponse({"is_ok": False, "error_msg": "uid is null", "error_code": 403})

    def event_stream():
        chat_with_user = ChatWithUser(uid=uid)
        for r in chat_with_user.receive_message_stream(message, round_id):
            yield "event:{}\n".format(r['data']['event'])
            yield "data:{}\n".format(json.dumps(r))
            yield "\n"
    
    return StreamingHttpResponse(streaming_content=event_stream(), 
                                 content_type="text/event-stream; charset=UTF-8", 
                                 headers={'X-Accel-Buffering': "no"})


def chat_history_service(request):
    try:
        body_json = json.loads(request.body)[0]
    except Exception as e:
        logger.warning("request body is no valid {}: {}".format(request.body, e))
        return HttpResponse("", status=403)

    parameters = body_json.get('parameters')
    uid = parameters.get("uid")
    page = parameters.get("page", 1)
    page_size = parameters.get("page_size", 10)

    chat_rounds = ChatRound.objects.filter(uid=uid)
    chat_rounds_pager = do_paginator(chat_rounds, page, page_size)
    resp = {
        "data": [
            {
                "round_id": x.id, 
                "user_message": x.user_message, 
                "assistant_message": x.assistant_message, 
                "assistant_extend_message": x.assistant_extend_message, 
                "user_pubs": x.user_pubs, 
                "create_at": f"{x.create_at}"
            }
            for x in chat_rounds_pager
        ],
        "num_pages": chat_rounds_pager.paginator.num_pages,
        "total": chat_rounds_pager.paginator.count,
        "is_ok": True,
        "error_msg": "",
        "error_code": 0,
    }

    return JsonResponse(resp)


def test_except_mail(request):
    message = request.GET['message']

    return HttpResponse("Good")
