""" Hybird rank
"""
import numpy as np
import math
import logging

from django.utils import timezone
from recsys.algorithms.constants import Constants
from recsys.algorithms.paper_quality import PaperQuality
from recsys.algorithms.interest import Interest
from recsys.utils import standard_score


logger = logging.getLogger(__name__)


def hybird_rank(uid:str, ud:str, features:list[dict]) -> list[dict]:
    """Re-Rank by item feature.
    :param uid:
    :param ud:
    :param features: [{}], list of
      {
        item: str,
        type: str,
        ts: datetime,
        citation: int,
        num_viewed: int,
        district:{},
        title: str,
        abstract: str
      }
    :return: [{..., score: float}], list of feature with new score
    """
    if uid:
        interest = Interest(Constants.USER_UID, uid)
    elif ud:
        interest = Interest(Constants.USER_UD, ud)
    else:
        features = rank_by_property(features)
        standard_score(features)
        return features

    features_with_property_score = rank_by_property(features)
    features_with_ctr_score = []

    interest_ratio = 0.7
    titles = [x['title'] + "\n" + x['abstract'] for x in features]
    sims = interest.get_similarity(titles)
    for i in range(len(features)):
        if isinstance(sims, float):
            similarity = sims
        else:
            similarity = sims[i]
        property_score = features_with_property_score[i].get('score', 0)
        ctr_score = -1.0
        if uid and features_with_ctr_score:
            ctr_score = features_with_ctr_score[i].get('score', -1.0)

        if ctr_score > 0:
            features[i]['score'] = ctr_score
        elif ctr_score == 0:
            features[i]['score'] = None
        else:
            features[i]['score'] = similarity * interest_ratio + (1 - interest_ratio) * property_score

    # remove records if score is None
    features = list(filter(lambda x: x['score'] is not None, features))
    if not features:
        logger.warning("features are empty after rank")
        return []
    standard_score(features)
    return sorted(features, key=lambda x: x['score'], reverse=True)


def rank_by_property(features):
    """Rank by item properties
    :param features: [{}], list of
      {
        item:str,
        type: str,
        ts: datetime,
        citation: int,
        num_viewed: int,
        district:{},
        title: str
      }
    :return: [{..., score: float}], list of feature with new score
    """
    w_citation, w_view, w_district, w_quality = 0.2, 0.1, 0.4, 0.3
    citation_list = []
    view_list = []
    district_list = []
    quality_list = []
    paper_quality = PaperQuality()

    for pub in features:
        citation_list.append(math.log(pub['citation'] + 0.0000000001))
        view_list.append(math.log(pub['num_viewed'] + 0.0000000001))
        if 'district' in pub and pub['district'] is not None:
            if Constants.SCI_SOURCE in pub['district'] and \
                    pub['district'][Constants.SCI_SOURCE] and \
                    Constants.SCI_QUARTILE in pub['district'][Constants.SCI_SOURCE]:
                district_list.append(1)
            elif Constants.CCF_SOURCE in pub['district'] and \
                    pub['district'][Constants.CCF_SOURCE] and \
                    Constants.CCF_QUARTILE in pub['district'][Constants.CCF_SOURCE]:
                district_list.append(10)
            else:
                district_list.append(0)
        else:
            district_list.append(0)

        item_type = pub.get('type')
        item_id = pub.get('item')
        quality = paper_quality.get_item_quality(item_type, item_id) or 0.0
        quality_list.append(quality)

    citation_list = normalization(citation_list)
    view_list = normalization(view_list)
    district_list = normalization(district_list)
    quality_list = normalization(quality_list)

    result = []
    for i in range(len(features)):
        if features[i]['ts']:
            interval = (timezone.now() - features[i]['ts']).total_seconds()
            interval /= 3600
        else:
            interval = 0
        time_discount = math.exp(-interval)
        item = features[i]
        item['score'] = time_discount * (w_citation*citation_list[i] + w_view*view_list[i] + \
                                                w_district*district_list[i] + w_quality*quality_list[i])
        result.append(item)
    return result


def normalization(data):
    '''
    :param data: list of number
    :return:
        normalization_data
    '''
    span = np.max(data) - np.min(data)
    if span == 0:
        span += 0.0000000001
    return (data - np.min(data))/span
