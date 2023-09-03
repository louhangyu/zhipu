import requests
import json
import datetime
import time


def main():
    headers = {}
    #message = '计算机视觉方向的论文在图像分类、目标检测、图像分割等任务上取得了哪些重要的成果？'
    message = "Transformer 来源于哪篇论文，哪年提出来的?"
    #message = 'what is BFS?'
    #message = "What are the ways to combine knowledge graph and big models?"
    round_id = 0 
    body = json.dumps([
        {
            "parameters": {
                "num": 6,
                "uid": "60ee895ba22628d38b7442d4",
                'message': message,
                "bussiness": "chat",
                'round_id': round_id,
            },
        }
    ])
    #url = 'http://10.10.0.30:4091/chat/'
    url = 'http://backend.aminer.cn/chat'
    
    start = time.time()
    r = requests.get(url, params={'body': body}, headers=headers, timeout=60, stream=True)
    if r.status_code != 200:
        print(f"failed, status code {r.status_code}, {r.text}")
    else:
        print(f"{datetime.datetime.now()}: ready to recv, spend {time.time() - start}s")
        resp_message = ""
        for line in r.iter_lines(decode_unicode=True):
            print(f"{datetime.datetime.now()}: \"{line}\", spend {time.time() - start}s")
            seperator_idx = line.find(":")
            name = line[:seperator_idx]
            value = line[seperator_idx+1:]
            if name == "data":
                resp_message += json.loads(value)['data']['message']
        print(f"{datetime.datetime.now()}: done, spend {time.time() - start}s")

        print("Recv: ", resp_message)


if __name__ == "__main__":
    main()
