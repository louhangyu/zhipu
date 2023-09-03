# Recall service

# Sync Data

## Sync Publication

- Source: aminer.publication_dupl in mongodb
- Fields:
     ```json
    {
      "title": "A paper title.", # Mandatory
      "abstract": "A paper abstract.", # Optional, used for both OAG and TF-IDF
      "keywords": ["word1", "word2", "word3"], # Optional, only required in OAG mode
      "venue": "a possible venue", # Optional, only required in OAG mode
      "authors": ["author 1", "author 2"], # Optional, only required in OAG mode
      "affiliations": ["org 1", "org 2", "org 3"] # Optional, only required in OAG mode, author's org
      }
     ```
- target: local disk /data/cache/aminer/pub.json, one line one json
- method: 
  - sync by days, time field is `u_t.u_c_t`. Also, you can consider field `year`;
  - If title is null or the number of words of title is less than four, we should ignore it.
- inner implement:
  - create a python file at recsys/utils.py
  - create a function `get_paper_for_emb(paper_id)`

# SDK

Refer to <https://dev.aminer.cn/zhuyifan/get-paper-embedding>


# Server

- 10.11.0.18, first login 10.10.0.33, then login.
  - user: pengxiaotao
  - password: zhipu@pengxt0824.com
