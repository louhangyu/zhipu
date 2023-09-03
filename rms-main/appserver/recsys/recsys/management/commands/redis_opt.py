import gzip
import json
import pprint
from concurrent.futures import ThreadPoolExecutor, as_completed

from tqdm import tqdm

from django.core.management.base import BaseCommand
from django.core.management.base import CommandParser
import logging

from recsys.algorithms.aggregate import RedisConnection, Aggregate

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Redis operation"

    def add_arguments(self, parser:CommandParser):
        parser.add_argument('--key',
                            type=str,
                            required=True,
                            help="key")
        parser.add_argument('--cmd',
                            type=str,
                            required=False,
                            default="Get",
                            help="Support get|del|flush_pub|flush_ai2k")

    def handle(self, *args, **options):
        key = options['key']
        cmd = options['cmd'].lower()

        agg = Aggregate()
        redis = RedisConnection()
        if cmd == "get":
            raw = redis.get(key)
            if raw:
                try:
                    raw = gzip.decompress(raw)
                    pprint.pprint(json.loads(raw))
                except:
                    pprint.pprint(json.loads(raw))
            else:
                print("not found '{}'".format(key))
        elif cmd == "del":
            redis.delete(key)
        elif cmd == "flush_pub":
            patterns = agg.get_pub_cache_key("*")
            pub_keys = redis.keys(patterns)
            pub_keys = [str(k).strip("'").split("_")[-1] for k in pub_keys]
            print(f"Pub cached {len(pub_keys)}")
            with tqdm(desc="Flush publications", total=len(pub_keys)) as bar:
                with ThreadPoolExecutor(max_workers=4) as ex:
                    futures = [ex.submit(agg.preload_pub, k, False) for k in pub_keys]
                    for future in as_completed(futures, timeout=3600*4):
                        try:
                            future.result(timeout=60)
                        except Exception as e:
                            logger.warning("load item failed: {}".format(e))
                        finally:
                            bar.update()
        elif cmd == "flush_ai2k":
            patterns = agg.get_ai2k_cache_key("*")
            keys = redis.keys(patterns)
            print(f"AI2K cached {len(keys)}")
            for k in tqdm(keys):
                ai2k_id = str(k).strip("'").split("_")[-1]
                agg.preload_ai2k(ai2k_id, False)
        else:
            raise Exception("Unknown command. Only support get|del")
