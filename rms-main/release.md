# v2022.12.12

- 去掉冷启动B路
- 未登陆用户，也就是只有ud用户，需要使用时间超过3天，才会生成个性化数据

# v2023.01.05

- 增加ai2k置顶视频
- 修复推荐TOP重复的bug

# v2023.03.28

product plan:

1. 引入LLaMA补充推荐内容
2. 各类实体的订阅和推荐：学者、期刊、个人主页成果影响力追踪
3. 引用大模型的科技情报生成和推送，包括文本、语音、视频（非必须），其中在科技情报语音推送上探索收费模式
4. 引用大模型的语义召回，提升推荐多样性

tech plan:
1. upgrade meili
2. upgrade milvus

task:
1. research typesense, try to replace meili. Because meili will have too long task list.
2. use a new chinese translate to improve subscribe recommendation

# v2023.04.06

1. fix subscribe children kg too many empty words
2. Change recall favorite algorithm. Use all uid choice data to train a mlogit model, then predict with it. 
   1. First, generate embedding by sentence_transformers; 
   2. Second, generate clusters by kmeans and vectors
   3. Third, fit mlogit model. Use the model to predict click recall type probability.

effect:
1. The search recall have improved very effectively.

# v2023.04.10

1. create user feature vector
2. tuning search recall speed
3. speed subscribe update

# v2023.04.18

1. update interest algorithm, get similarity by compare user vector and title vector

# v2023.05.05

1. Change sentence model to all-mpnet-base-v2
2. fix user vector not update bug