# RMS

Recommendation of Aminer

[[_TOC_]]

# API

## Request recommendations

Request:

- method: post
- url: https:://backend.aminer.cn/recommend_v3/
- body (json format):
  - num: int, 请求内容数量
  - exclude_ids: [], 需要排除的内容ID列表
  - keywords: [], 订阅关键词
  - uid: 登陆用户的ID
  - ud: 未登陆用户的ID
  - first_reach: 首次访问网站时间, 格式：YYYY-mm-dd HH:MM:SS
  - alg_flag: 算法标记. 来自深圳分站请求，填`shenzhen`; 推送请求，填`push`;
  - subscribes: [str], 登陆用户的全体订阅词
  - recalls: [str]，非必填, 控制召回路。
    - editor_hot: 运营推荐的hot paper
    - top: 运营推荐的置顶paper
    - follow,behavior,behavior_person,subscribe: 个性化推荐feed
- Request example
  ```json
    [
      {
        "parameters": {
          "num": 10,  # 请求内容数量
          "exclude_ids": [],  # 需要排除的内容ID
          "keywords": [],     # 订阅关键词
          "uid": "",          # 登陆用户的ID
          "first_reach": "",  #首次访问网站时间
        }
      }
    ]
  ```
- Response format
  ```json
  {
    "data": [
      {
        "data": [
          {
            "e_pub": [{
              "type": "",
              "recall_type": "",
              "recall_reason": {
                "zh": "",
                "en": ""
              }
            }],
            "id": "",
            "labels": [],
            "labels_zh": []
          }, ...
        ],
        "succeed": true
      }
    ],
    "meta": {
      
    }
  }
  ```
  - type: 
    - pub, 
    - pub_topic, 
    - person, 
    - ai2k
  - recall_type:
    - "follow"   # 关注学者动态
    - "subscribe"  # 订阅关键词精准检索
    - "subscribe_oag"    # 订阅关键词oagbert语义召回
    - "subscribe_kg"    # 订阅关键词基于知识图谱召回
    - "behavior"  # 基于行为的推荐
    - "behavior_person"  # 基于行为的推荐
    - "subject"    # 订阅学科的推荐
    - "editor_hot"   # 运营热点文章
    - "hot"   # 根据全部用户行为计算的热点文章
    - "topic_hot"     # 热门主题
    - "search"
    - "random_person"  # 从7天有动态的学者池中选择部分学者推荐
    - "ai2k"
    - "cold"
    - "cold_ai2k"   # 冷启动AI2000学者
    - "cold_subscribe"  # 冷启动订阅关键词精准检索
    - "cold_subscribe_oag"    # 冷启动订阅关键词oagbert语义召回
    - "cold_top"  # 只有冷启动的B路会展示
    - "top" # 置顶的内容

## Get Meta of UD or UID

You can use it for debug.

Request:

- method: get
- url: http://10.10.0.30:4091/meta/
- params:
  - uid:
  - ud:
  

Response:

```json
{
    "browse": {
        "count": 0,
        "pubs": []
    },
    "click": {
        "count": 0,
        "pubs": []
    },
    "non_keyword": []
}
```

## Chat 

- method: post
- url: https:://backend.aminer.cn/chat/
- body (json format):
  - message: str, 对话消息
  - uid: str, 登陆用户的ID
  - round_id: int, 非必填，当需要扩展回答的时候才填。 扩展回答对话ID
  - bussiness: chat, 业务类型
- Request example
  ```json
    [
      {
        "parameters": {
          "message": "what is bfs",  # 对话消息
          "uid": "xxx",          # 登陆用户的ID
          "bussiness": "chat",  #业务类型
          "extend_msg_id": 222  #扩展消息ID,
          "stream": false,  #是否请求流式数据
        }
      }
    ]
  ```
- Response format
  ```json
  {
    "data": {
      "round_id": int, # 对话ID
      "message": str, #返回消息
      "pubs": [
        {"pub_id": str, "title": str}
      ]
    },
    "is_ok": true|false,  # true：代表成功，false：代表失败
    "error_msg": str,     # 错误信息,
    "error_code": int,    # 错误码
  }
  ```

## Chat History

- method: post
- url: https:://backend.aminer.cn/recommend_v3/
- body (json format):
  - uid: str, 登陆用户的ID
  - page: int, 第几页
  - page_size: int, 每页内容数量
  - bussiness: chat_history, 业务类型
- Request example
  ```json
    [
      {
        "parameters": {
          "uid": "xxx",          # 登陆用户的ID
          "bussiness": "chat_history",  #业务类型
          "page": 1,
          "page_size": 10,
        }
      }
    ]
  ```
- Response format
  ```json
  {
    "data": [{
      "round_id": int,  #对话ID
      "user_message": str, #用户消息
      "assistant_message": str, #助手返回消息
      "assistant_extend_message": str,  #助手扩展回答消息
      "assistant_pubs": [ #助手返回论文信息
        {"pub_id": str, "title": str}
      ]
    }],
    "num_pages": int,   # 页数
    "total": int,       #总消息数
    "is_ok": true|false,  # true：代表成功，false：代表失败
    "error_msg": str,     # 错误信息,
    "error_code": int,    # 错误码
  }
  ```

# Redis method for browse

- key
  - UID: uid_show1_{uid};
  - UD: ud_show1_{ud}, {ud} should be cleaned. "-" should be replaced by "_";
- name: pub_id
- get data mode
  - zrange
  - zscore
- redis server 
  - {"host": "10.10.0.28", "port": "6379", "ssl": False, "password": "UEWA21CzY3Gwclf5pTXPdpsEUehFFiNQF+tl6NwADl4="},


Get a paper show number of a uid or a ud
 
- key
  - UID: uid_show_paper_{uid}_{pub_id};
  - UD: ud_show_paper_{ud}, {ud} should be cleaned. "-" should be replaced by "_";
- get data mode
  - mget 
  - get 
- redis server
  - {"host": "10.10.0.28", "port": "6379", "ssl": False, "password": "UEWA21CzY3Gwclf5pTXPdpsEUehFFiNQF+tl6NwADl4="},


# Redis method for click 

- key
  - UID: uid_click_{uid};
  - UD: ud_click_{ud}, {ud} should be cleaned. "-" should be replaced by "_";
- name: pub_id
- get data mode
  - zrange
  - zscore
- redis server
  - {"host": "10.10.0.28", "port": "6379", "ssl": False, "password": "UEWA21CzY3Gwclf5pTXPdpsEUehFFiNQF+tl6NwADl4="},

Get a paper click number of a uid or a ud

- key
  - UID: uid_click_paper_{uid}_{pub_id};
  - UD: ud_click_paper_{ud}, {ud} should be cleaned. "-" should be replaced by "_";
- get data mode
  - mget
  - get
- redis server
  - {"host": "10.10.0.28", "port": "6379", "ssl": False, "password": "UEWA21CzY3Gwclf5pTXPdpsEUehFFiNQF+tl6NwADl4="},

# How to fetch user action log?

Data are stored in postgresql server. Database is `rms` and table is `recsys_actionlog`.

- Host: 10.10.0.39:5432
- User: reporter
- Password: `report_1232*()`

fields:

- action: 1, show; 2, click
- type:  
    - TYPE_PUB = 1
    - TYPE_PUB_TOPIC = 2
    - TYPE_REPORT = 3
    - TYPE_PROFILE = 4

# How to fetch user event log?

User event log contains all action logs of users, they store in the postgres `rms.usereventlog`.

- Host: 10.10.0.39:5432
- User: reporter
- Password: `report_1232*()`


# Postgres

- host: 10.10.0.39
- port: 5432

## DB: feature

User:

- user: feature_dev
- password: howtodoit12345_*&%

tables:

- week_hot_paper
- high_cite_paper

# Typesense vector server

version: typesense-server-0.24.1-1.x86_64.rpm

- api-address = 10.10.0.22
- api-port = 8108
- api-key = kXlOjmjgW4pSPvQmVvK0e88GtU34JklynXHG1jSSSjxlcR31


# MongoDB 

## db: aminer

We have used these documents below:

- publication_dupl: store papers
- pub_topic: store paper topic

## db: tracking  

- articles: store report

## db: web

- scholar_paper_pool: person dynamic information

# SSDB

PAGE_VIEWED::PERSON
PAGE_VIEWED::PUB
"Host": "10.10.0.23",
"Port": 12000

# Servers

- 10.10.0.38, offline command
- 10.10.0.39, recsys slave api
- 10.10.0.30, pub ip: 159.27.5.67, recsys gateway api
- 10.10.0.22, vector server, typesense
- 120.131.0.100, GPU train

# Data

- Follow recall. Format: http://10.10.0.38/aminer/meta/follow_recall/followed_scholar_recall-{2022_03_23}.json
- Subscribe recall. Format: http://10.10.0.38/aminer/meta/subscribe_recall/subscribe_recall-2022_03_23.json
- User action log. Format: http:://120.131.0.100:10808/aminer/input_log/2022-03-16-log.json
- High quality papers. Format: http://10.10.0.38/aminer/pub.json
- Get paper click etc. Url: http://10.10.0.38/aminer/paper_quality.csv

# ChatGLM API

https://docs.qq.com/doc/DU1B0VW9SWGJuaVdk

API  Key: ed83262133184bfe9a443f918b0bdbb3

MFwwDQYJKoZIhvcNAQEBBQADSwAwSAJBAIHYPqz3ZIo1hh2PONPfIX2h/70LrvMiAwfLVCnU/cdAUQWMI5h0s1aZ4ywe5vJ0LeW8O8D3C0d21OCFEfe3PVkCAwEAAQ==

# Operation

## How to add hot paper?

These hot papers will show in home page.

- url: http://10.10.0.38/admin/recsys/hotpaper/

# Product Requirements

- https://docs.qq.com/doc/DUWF1b01seWdCbnNM

# Reference

- Algorithm package: <https://dev.aminer.cn/zhuyifan/get-paper-embedding>

# Future Reading

- (shenzhen)[shenzhen.md]
- (pingback)[pingback.md]
- (release)[release.md]
