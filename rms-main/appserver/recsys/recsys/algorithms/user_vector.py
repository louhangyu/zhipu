"""Implement user vector model update.
"""
import datetime
from sklearn.cluster import KMeans, MiniBatchKMeans
import logging
from tqdm import tqdm

from django import db
from django.utils import timezone

from recsys.algorithms.constants import Constants
from recsys.models import MongoConnection, UserVector
from recsys.ann import PaperVectorIndex


logger = logging.getLogger(__name__)


class UserVectorTrain:
    def __init__(self, n_cluster=16, max_iter=500, random_state=0, prev_days=365):
        self.last_time = timezone.now() - datetime.timedelta(prev_days)
        self.mongo = MongoConnection.get_aminer_client()
        self.n_cluster = n_cluster
        self.max_iter = max_iter
        self.random_state = random_state

    def train(self) -> None:
        # fetch uids who have keywords
        sql = """
            select
              distinct(uid)
            from 
              recsys_actionlog_of_all
            where 
              recall_type in %s and
              coalesce(trim(keywords)) != '' and
              create_at > %s and 
              coalesce(trim(uid)) != ''
            ;
        """
        uids = []
        with db.connection.cursor() as c:
            c.execute(sql, (Constants.RECALL_TYPES, self.last_time))
            for row in c.fetchall():
                uid = row[0]
                uids.append(uid)
        print("Found {} uids".format(len(uids)))
        self.train_for_uids(uids)

    def train_for_uids(self, uids:list[str]) -> None:
        vectors, genders, subscribes_list, titles, uid_list = self.prepare_user_features(uids)
        clusters = self.train_cluster(vectors)
        # update model
        for i in range(len(vectors)):
            uid = uids[i]
            vector = vectors[i]
            gender = genders[i]
            subscribes = subscribes_list[i]
            title = titles[i]
            cluster = clusters[i]

            try:
                obj = UserVector.objects.get(uid=uid)
            except:
                obj = UserVector(
                    uid=uid,
                    gender=gender,
                    subscribes=subscribes,
                    title=title,
                    vector=vector,
                    cluster=cluster
                )

            obj.gender = gender
            obj.subscribes = subscribes
            obj.title = title
            obj.vector = vector
            obj.cluster = cluster
            obj.save()

    def rebuild(self):
        UserVector.objects.all().delete()

    def prepare_user_features(self, uids: list[str]):
        """Return: vectors, genders, subscribes_list, titles, uid_list
        """
        from recsys.algorithms.base import BaseAlgorithm

        projection = {'_id': 1, 'experts_topic': 1, 'subject': 1, "gender": 1, "title": 1}
        users = self.mongo.find_by_ids("aminer", "usr", list(set(uids)), projection)
        vectors = []
        genders = []
        uid_list = []
        titles = []
        subscribes_list = []
        for user in tqdm(users, desc="prepare user features"):
            if "experts_topic" in user:
                subscribes = []
                experts_topic = user.get("experts_topic")
                if experts_topic and isinstance(experts_topic, list):
                    for item in experts_topic:
                        if 'input_name' not in item:
                            continue
                        subscribes.append(item['input_name'])
                    subscribes = sorted(subscribes)
            else:
                subscribes = []
            subscribes_list.append(subscribes)

            if 'subject' in user:
                subject = user['subject'] or ""
            else:
                subject = ""

            if 'title' in user:
                title = user['title']
            else:
                title = ""
            titles.append(title)
            tokens = subscribes + [subject] + [title]
            en_tokens = []
            for token in tokens:
                en_token = BaseAlgorithm.translate_chinese(token)
                en_tokens.append(en_token)
            vector = PaperVectorIndex._get_text_vector(" ".join(en_tokens))
            vectors.append(vector)

            if 'gender' in user and user['gender']:
                gender = int(user['gender'])
            else:
                gender = -1
            genders.append(gender)

            uid = str(user['_id'])
            uid_list.append(uid)

        return vectors, genders, subscribes_list, titles, uid_list

    def train_cluster(self, vectors: list[float]) -> list:
        """Returns: [cluster_id]
        """
        if len(vectors) > self.n_cluster:
            km = KMeans(n_clusters=self.n_cluster, random_state=self.random_state, max_iter=self.max_iter)
            km.fit(vectors)
            clusters = km.labels_
            print("KMeans iter {}, inertia {}".format(km.n_iter_, km.inertia_))
        else:
            clusters = [0] * self.n_cluster
        return clusters

