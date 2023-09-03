""" Recall Favorite class. Requirement:
- UserVector Table
"""
import datetime
import json
import random

from sklearn.linear_model import LogisticRegression, LogisticRegressionCV
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OneHotEncoder
from sklearn.metrics import classification_report
import pandas as pd
import numpy as np
import logging
from tqdm import tqdm

from django import db
from django.utils import timezone

from recsys.algorithms.constants import Constants
from recsys.algorithms.redis_connection import RedisConnection
from recsys.models import MongoConnection, UserVector


logger = logging.getLogger(__name__)


class RecallFavorite:
    def __init__(self):
        self.last_time = timezone.now() - datetime.timedelta(90)
        self.redis_conn = RedisConnection.get_default()
        self.mongo = MongoConnection.get_aminer_client()
        self.cache_time = 3600*24*30
        self.x_cols = []
        self.uid_feature_map = {}
        self.logit = LogisticRegressionCV(max_iter=300, cv=9, random_state=0)

    def train(self):
        train_data = self.prepare_train_data()
        Y = train_data['click'].to_numpy()
        X = train_data[self.x_cols].to_numpy()
        self.logit.fit(X, Y)
        print("Logit iter {}".format(self.logit.n_iter_))

        for uid, feature in tqdm(self.uid_feature_map.items(), desc="update uid recall type prob"):
            probs = {}
            for recall_type in Constants.RECALL_TYPES:
                recall_type_id = self.recall_type_to_id(recall_type)
                x = list(feature['gender_code']) + list(feature['cluster_code']) + [recall_type_id]
                y = self.logit.predict_proba(np.asarray([x]))
                prob = y[0][1]
                probs[recall_type] = prob

            self.redis_conn.setex(self.get_uid_recall_type_prob_cache_key(uid), self.cache_time, json.dumps(probs))

    def eval(self):
        df = self.prepare_train_data()
        Y = df['click'].to_numpy()
        X = df[self.x_cols].to_numpy()
        X_train, X_test, Y_train, Y_test = train_test_split(X, Y, test_size=0.3, random_state=0)
        self.logit.fit(X_train, Y_train)
        y_pred = self.logit.predict(X_test)
        report = classification_report(Y_test, y_pred, target_names=["not click", "click"])
        print(report)

    def prepare_train_data(self) -> pd.DataFrame:
        """Returns: The dataframe has columns (uid, click, recall_type, recall_type_id, cluster_1 ~ 10, gender)"""
        sql = """
            select
              uid, 
              recall_type,
              click
            from 
              recsys_actionlog_of_all
            where 
              recall_type in %s and
              coalesce(trim(recall_type)) != '' and
              create_at > %s and 
              coalesce(trim(uid)) != ''
            ;
        """
        uids = []
        recall_types = []
        clicks = []
        with db.connection.cursor() as c:
            c.execute(sql, (Constants.RECALL_TYPES, self.last_time))
            for row in c.fetchall():
                uid = row[0]
                uids.append(uid)
                recall_type = row[2]
                recall_types.append(recall_type)
                click = row[2]
                clicks.append(click)

        df = pd.DataFrame({"uid": uids, 'recall_type': recall_types, 'click': clicks})
        uid_feature_map = self.prepare_user_features(uids)

        for idx, row in df.iterrows():
            uid = row['uid']
            df.loc[idx, "recall_type_id"] = self.recall_type_to_id(row['recall_type'])
            feature = uid_feature_map.get(uid)
            if not feature:
                continue
            for i in range(len(feature['gender_code'])):
                col = f"gender_{i}"
                df.loc[idx, col] = feature['gender_code'][i]

            for j in range(len(feature['cluster_code'])):
                col = f"cluster_{j}"
                df.loc[idx, col] = feature['cluster_code'][j]

        cols = df.columns
        gender_cols = []
        cluster_cols = []
        for col in cols:
            if col.find("gender_") > -1:
                gender_cols.append(col)
            elif col.find("cluster_") > -1:
                cluster_cols.append(col)
        self.x_cols = sorted(gender_cols) + sorted(cluster_cols) + ['recall_type_id']
        df = df.fillna(-1)
        return df

    def prepare_user_features(self, uids) -> dict:
        """Return: {uid: {'vector': [float], 'gender_code': [int], 'cluster_code': [int]}}"""
        uid_feature_map = {}
        vectors = []
        genders = []
        uid_list = []
        clusters = []
        user_vectors = UserVector.objects.filter(uid__in=uids)
        for obj in user_vectors:
            vectors.append(obj.vector)
            genders.append(obj.gender)
            uid_list.append(obj.uid)
            clusters.append(obj.cluster)

        # one hot cluster
        onehot_clusters = OneHotEncoder()
        cluster_codes = onehot_clusters.fit_transform(np.array(clusters).reshape(-1, 1)).toarray()

        # one hot gender
        onehot_gender = OneHotEncoder()
        gender_codes = onehot_gender.fit_transform(np.array(genders).reshape(-1, 1)).toarray()

        for i in range(len(uid_list)):
            uid = uid_list[i]
            vector = vectors[i]
            gender = genders[i]
            gender_code = gender_codes[i]
            cluster = clusters[i]
            cluster_code = cluster_codes[i]
            feature = {
                'vector': vector,
                'gender': gender,
                'cluster': cluster,
                'gender_code': gender_code,
                'cluster_code': cluster_code,
            }

            uid_feature_map[uid] = feature

        self.uid_feature_map = uid_feature_map
        return uid_feature_map

    @classmethod
    def recall_type_to_id(cls, recall_type):
        for i, rc in enumerate(Constants.RECALL_TYPES):
            if recall_type == rc:
                return i

        return -1

    @classmethod
    def get_uid_recall_type_prob_cache_key(cls, uid):
        return "recall_favorite_prob_{}".format(uid)

    def predict(self, uid, ud=None):
        """ Get user liked recall type
        :param uid:
        :param ud:
        :return: dict, {recall_type: prob}
        """
        raw = self.redis_conn.get(self.get_uid_recall_type_prob_cache_key(uid))
        if raw:
            return json.loads(raw)

        probabilities = {}
        for recall_type in Constants.RECALL_TYPES:
            probabilities[recall_type] = random.random()

        return probabilities


