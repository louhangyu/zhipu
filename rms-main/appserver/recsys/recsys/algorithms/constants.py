

class Constants:
    RECALL_FOLLOW = "follow"   # 关注学者动态
    RECALL_SUBSCRIBE = "subscribe"  # 订阅关键词精准检索
    RECALL_SUBSCRIBE_OAG = "subscribe_oag"    # 订阅关键词oagbert语义召回
    RECALL_SUBSCRIBE_KG = "subscribe_kg"    # 订阅关键词基于知识图谱召回
    RECALL_BEHAVIOR = "behavior"  # 基于行为的推荐
    RECALL_BEHAVIOR_PERSON = "behavior_person"  # 基于行为的推荐
    RECALL_SUBJECT = "subject"    # 订阅学科的推荐
    RECALL_EDITOR_HOT = "editor_hot"   # 运营热点文章
    RECALL_HOT = "hot"   # 根据全部用户行为计算的热点文章
    RECALL_TOPIC_HOT = "topic_hot"     # 热门主题
    RECALL_SEARCH = "search"
    RECALL_RANDOM_PERSON = "random_person"  # 从7天有动态的学者池中选择部分学者推荐
    RECALL_AI2K = "ai2k"
    RECALL_COLD = "cold"
    RECALL_COLD_AI2K = "cold_ai2k"   # 冷启动AI2000学者
    RECALL_COLD_SUBSCRIBE = "cold_subscribe"  # 冷启动订阅关键词精准检索
    RECALL_COLD_SUBSCRIBE_OAG = "cold_subscribe_oag"    # 冷启动订阅关键词oagbert语义召回
    RECALL_COLD_TOP = "cold_top"  # 只有冷启动的B路会展示
    RECALL_TOP = "top"

    RECALL_SHENZHEN_NEWLY = "shenzhen_newly"  # only for shenzhen

    RECALL_PUSH_HOT = "push_hot"  # from daily json
    RECALL_PUSH_NEW = "push_new"  # from subscribe stat
    RECALL_PUSH_WEEK = "push_week"  # hot paper for week
    RECALL_PUSH_FOLLOW = "push_follow"  # follow paper for week

    RECALL_TYPES = (
        RECALL_FOLLOW,
        RECALL_SUBSCRIBE,
        RECALL_SUBSCRIBE_OAG,
        RECALL_SUBSCRIBE_KG,
        RECALL_BEHAVIOR,
        RECALL_BEHAVIOR_PERSON,
        RECALL_AI2K,
        RECALL_SUBJECT,
        RECALL_EDITOR_HOT,
        RECALL_HOT,
        RECALL_TOPIC_HOT,
        RECALL_SEARCH,
        RECALL_RANDOM_PERSON,
        RECALL_PUSH_NEW,
        RECALL_PUSH_WEEK,
        RECALL_SHENZHEN_NEWLY,
        RECALL_COLD,
        RECALL_COLD_SUBSCRIBE_OAG,
        RECALL_COLD_SUBSCRIBE,
        RECALL_COLD_AI2K,
        RECALL_COLD_TOP,
        RECALL_TOP,
    )

    RECALL_FAVORITE_CACHE_TIME = 3600*24*7

    SCI_SOURCE = "CJCR"
    SCI_QUARTILE = "1区"

    CCF_SOURCE = "CCF"
    CCF_QUARTILE = "A"

    PUB_CACHE_TIME = 3600 * 24 * 7
    RECOMMENDATION_CACHE_TIME = 3600 * 24 * 7
    PERSON_CACHE_TIME = 3600 * 24 * 7

    USER_UID = "uid"
    USER_UD = "ud"

    COLD_USER_ID = "cold"
    COLD_USER_TYPE = "cold"

    SQL_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
    SQL_DATE_FORMAT = "%Y-%m-%d"

    UD_MAX_NUM_SHOW = 2000

    ITEM_PUB = "pub"
    ITEM_PUB_TOPIC = "pub_topic"
    ITEM_PERSON = "person"
    ITEM_AI2K = "ai2k"
    ITEM_REPORT = "report"
    VALID_ITEM_TYPE = [ITEM_PUB, ITEM_PUB_TOPIC, ITEM_PERSON, ITEM_AI2K]

    ALG_PUSH = "push"
    ALG_SHENZHEN = "shenzhen"

    PUSH_NEW_DAYS = 1

    QUERY_MAX_LEN = 60
    QUERY_MAX_TOKEN = 3

    KEYWORD_REC_CACHE_TIME = 3600*24*7
