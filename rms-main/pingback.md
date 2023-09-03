# Pingback 规范

[[_TOC_]]


- 上报方法：GET
- 参数：x-www-form
- 域名: pingback.aminer.cn

例子：

```
https://pingback.aminer.cn/?uid=xx&ud=xxx
```

## 上报的公共字段

带*为必填。

- uid: aminer用户id，可选; 只有登陆用户才需要增加此项
- ud: 未注册id, 小程序可以使用微信生成唯一设备码
- ip: 客户端IP
- pub_ids: 必填
  - type=pub, 文章ID，多个以"|"线分割，现在PC是一篇paper发送一条; 
  - type=profile, 学者ID;
- keywords: 关键词列表，多个以"|"线分割，请求推荐数据的时候request里面包含的关键词
- action: `show` | `click` | `favorite` | `copy_title` | `subscribe_subject` | `search`
- type: 内容类型，可选 pub, conference, profile, pub_topic，report, 不填表示为pub
  - pub: 论文
  - profile: 学者
- device: 设备类型, 可选pc, wx. wx是微信小程序
- first_reach: 首次到达时间，也就是UD的生成时间，格式: YYYY-mm-dd HH:MM:ss。例如： 2021-11-29 10:01:01
- ls: 客户端log id号，每发送一条，数值自增1，从1开始。
- checksum: 检验码。

checksum生成算法：

- 取得所有上报参数，checksum除外
- 以参数名排序，拼接字符: name1=value1&name2=value2.....
- 对拼接字符进行md5加密
- 例如：
  - http://pingback.aminer.cn/?ud=qqwe&action=show&ls=2233
  - 生成字符`action=show&ls=2233&ud=qqwe`, 其中value需要做url quote
  - checksum is `d10e62367fbb731941ce644b3a59c6ea`
  - 最后实际上报的url是： http://pingback.aminer.cn/?ud=qqwe&action=show&ls=2233&checksum=d10e62367fbb731941ce644b3a59c6ea


## 推荐曝光

每次取得推荐结果，并显示在页面，需要上报。

参数说明：
- action: `show`


## 推荐点击

用户点击了任何一个推荐内容，需要上报。

参数说明：
- action: `click`

## 收藏

参数说明：
- action: `favorite`

## 复制标题

参数说明：
- action: `copy_title` 

## 订阅学科

用户修改学科时上报。

参数说明：
- uid: 用户id，必填
- subject: 学科
- action: subscribe_subject

## 搜索

用户搜索时上报，覆盖全部有搜索框的地方

参数说明：
- query: 用户输入的查询串
- action: `search`

## 删除订阅词

参数说明：
- action: `del_subscribe`
- subscribe_word: 删除的订阅词

## 增加订阅词

参数说明：
- action: `add_subscribe`
- subscribe_word: 新增的订阅词
