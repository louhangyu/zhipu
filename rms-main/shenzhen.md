
[[_TOC_]]

# Servers

From 192.168.0.49 to 57

# Topology

- 49: postgresql
- 50: milvus-2.0.5
  - Attu: http://192.168.0.50:8000/#/
- 51: 
  - Redis 
      - IP: 192.168.0.51:6379 
      - Pass: UEWA21CzY3Gwclf5pTXPdpsEUehFFiNQF+tl6NwADl4=
- 52:
  - Meili:  http://192.168.0.52:7700
- 53: offline command
- 54: pingback gateway
- 55-57: webapp server

# API

- Host: backend.aminersz.cn
- Examples:
  - proto: https
  - url: https://backend.aminersz.cn/recommend_v3/
  - body
    - ```json
      [
            {
                "parameters": {
                    "num": 50,
                    "exclude_ids": [],
                    "keywords": [],
                    "uid": "63dcb63594097702ee0f8cf2",
                    "alg_flag": ""
                }
            }
      ]
    ```

## Recommend Frontend Service

Request:
- method: post
- url: https://backend.aminersz.cn/recommend_v3/
- body (json format):
  - num: int, 请求内容数量，选填
  - exclude_ids: [str], 需要排除的内容ID列表, 选填
  - keywords: [str], 订阅关键词。选填，只有请求订阅推荐的时候，才填
  - uid: str, 登陆用户的aminer ID。必填，没有登陆可以为空
  - ud: str, 未登陆用户的ID, 需要前端自己来生成，保证是唯一的。必填
  - first_reach: str, 首次访问网站时间, 格式：YYYY-mm-dd HH:MM:SS。第一次生成_Collect_UD时，同时生成first_reach并持久化在本地。选填
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
- Type是pub的响应格式: 关键信息都在data[0]['data']里面，各种推荐的内容(比如pub, person)都会放在一个字典里面, 只是会有一些字段不同，大格式是一样的。
  ```json
  {
    "data": [
      {
        "data": [
          {
            "e_pub": [{
              "type": "pub",  # 类型
              "recall_type": "",  # 召回类型
              "recall_reason": {
                "zh": "",  # 推荐理由中文
                "en": ""   # 推荐理由英文
              },
              "item": "6406ac7090e50fcafd054a3a",  #Pub ID
              "score": 0.5,   #用于推荐的分值
              "authors": [  #type是pub时候的结构
                  {
                      "name": "",  #作者名称
                      "_id": "",   #作者ID
                      "avatar": "",  #作者头像url
                      "org": "",  #所属机构
                      "h_index": ""  #H-Index,
                      "ai2000": {}, # ai2000的排名，只有进入榜的用户才有这个值
                      "jconf": {}
                  },
                  ....
              ],
              "num_citation": "", #引用数
              "num_viewed": "",   #浏览数
              "title": "",   #标题
              "abstract": "",  #摘要
              "category": [],  #所属目录
              "subject_zh": "",   #学科中文名
              "subject_en": "",   #学科英文名
              "keywords": "",     #关键词
              "graph_keywords": [],   #图谱关键词
              "venue": {
                  "info": {
                      "name": "",  #venue全称
                      "short": "",  #venue简称
                  }
              }
            }],
            "id": "", # 项目ID
            "labels": [],  # 英文标签
            "labels_zh": []  # 中文标签
          }, ...
        ],
        "succeed": true
      }
    ],
    "meta": {
      
    }
  }
  ```
  - type: 主要有四种类型pub, pub_topic, person, ai2k, 现在主要用到的是pub, person其他两个暂时不用
  
- Person的响应格式
    ```json
    {
    "data": [
        {
        "data": [
            {
            "e_pub": [{
                "type": "person",  # 类型
                "recall_type": "",  # 召回类型
                "recall_reason": {
                "zh": "",  # 推荐理由中文
                "en": ""   # 推荐理由英文
                },
                "item": "6406ac7090e50fcafd054a3a",  #Person ID
                "score": 0.5,   #用于推荐的分值
                "avatar": "",  #头像url
                "name": "",   #名称
                "indices": {
                    "pubs": "",  #文献数
                    "hindex": "",  #H-Index
                    "citations": "",  #引用数
                },
                "interests": [
                    {"t": "" # 兴趣},
                    ... 
                ],
                "contact": {
                  "address": "",  #联系地址
                  "affiliation": "",
                  "affiliation_zh": "",
                  "position": "",  #职位
                  "position_zh": "",  #中文职位
                },
                "num_viewed": "", #浏览数
            }],
            "id": "", # Person ID
            "labels": [],  # 英文标签
            "labels_zh": []  # 中文标签
            }, ...
        ],
        "succeed": true
        }
    ],
    "meta": {
        
    }
    }
    ```

# 离线任务列表

使用crontab挂在aminer用户下。

```
# RMS

5 1 * * * cd /data/webapp/rms/appserver/confs/shenzhen; ./command.sh update_pub_ids
30 1,13 * * * cd /data/webapp/rms/appserver/confs/shenzhen; ./command.sh update_pub
55 12,23 * * * cd /data/webapp/rms/appserver/confs/shenzhen; ./command.sh export_user_event_log

30 1 * * * cd /data/webapp/rms/appserver/confs/shenzhen; ./command.sh paper_quality_update
40 1,15 * * * cd /data/webapp/rms/appserver/confs/shenzhen; ./command.sh subscribe_stat_update

45  14,2   * * * cd /data/webapp/rms/appserver/confs/shenzhen; ./command.sh ann_update --mode train --type pub
45  15,4   * * * cd /data/webapp/rms/appserver/confs/shenzhen; ./command.sh ann_update --mode train --type pub_vector
15  3   * * * cd /data/webapp/rms/appserver/confs/shenzhen; ./command.sh ann_update --mode train --type topic

5  *   * * * cd /data/webapp/rms/appserver/confs/shenzhen; ./command.sh recall_favorite_update --mode train

30  2  *  *  *  cd /data/webapp/rms/appserver/confs/shenzhen; ./command.sh ads_update


15  *  *  *  *  cd /data/webapp/rms/appserver/confs/shenzhen; ./command.sh schedule


# RMS Recall

45   1   *   *   * cd /data/webapp/rms_recall; ./safeRun-pro.sh cold
20   */2   *   *   * cd /data/webapp/rms_recall; ./safeRun-pro.sh latest_paper
20   1   *   *   * cd /data/webapp/rms_recall; ./safeRun-pro.sh scholar_pool
15   1   *   *   * cd /data/webapp/rms_recall; ./safeRun-pro.sh email_follow_new

5   3   *   *   * cd /data/webapp/rms_recall; ./safeRun-pro.sh follow_recall
5   6   *   *   * cd /data/webapp/rms_recall; ./safeRun-pro.sh miniprogram_recall
5   4   *   *   * cd /data/webapp/rms_recall; ./safeRun-pro.sh subscribe_children_kg

20   1   *   *   * cd /data/webapp/rms_recall; ./safeRun-pro.sh embedding
20   3   *   *   * cd /data/webapp/rms_recall; ./safeRun-pro.sh subscribe_oag


# RMS algorithm
30  12  *  *  *  cd /data/webapp/rms/appserver/confs/shenzhen; ./command.sh algorithm_update --algorithm native --mode train
```

# Pingback 规范

- 上报方法：GET
- 参数：x-www-form
- 协议: https
- 域名: backend.aminersz.cn
- 路径: /pingback/

## 请求上报的公共字段 (必填)

- uid: aminer用户id; 只有登陆用户才有
- ud: 未注册id, 小程序可以使用微信生成唯一设备码
- pub_ids: 必填
  - type=pub, 文章ID;
  - type=profile, 学者ID;
- action: `show` | `click` | `search`
  - show: 曝光
  - click: 点击
  - search: 搜索
- type: 内容类型，可选 pub, profile, 不填表示为pub
  - pub: 论文
  - profile: 学者
- first_reach: 首次到达时间，也就是UD的生成时间，格式: YYYY-mm-dd HH:MM:ss。例如： 2021-11-29 10:01:01
- ls: 客户端log id号，每发送一条，数值自增1，从1开始。
- checksum: 检验码。

checksum生成算法：

- 取得所有上报参数，checksum除外
- 以参数名排序，拼接字符: name1=value1&name2=value2.....
- 对拼接字符进行md5加密
- 例如(只说明逻辑用)：
  - https://backend.aminersz.cn/?ud=qqwe&action=show&ls=2233
  - 生成字符`action=show&ls=2233&ud=qqwe`, 其中value需要做url quote
  - checksum is `d10e62367fbb731941ce644b3a59c6ea`
  - 最后实际上报的url是： https://backend.aminersz.cn/?ud=qqwe&action=show&ls=2233&checksum=d10e62367fbb731941ce644b3a59c6ea

## 响应说明

所有请求的响应数据，都符合下面的格式标准。

- 成功；
  - response status code = 200
  - body: json format. {id: 日志id}，其他字段不用关注
- 失败
  - response status code = 403，body里面包含原因说明


## 推荐曝光

每次取得推荐结果，并显示在页面，需要上报。

参数说明：
- action: `show`

## 推荐点击

用户点击了任何一个推荐内容，需要上报。

参数说明：
- action: `click`

## 搜索

用户搜索时上报，覆盖全部有搜索框的地方

参数说明：
- query: 用户输入的查询串
- action: `search`