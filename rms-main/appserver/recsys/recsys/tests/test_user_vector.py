from django.test import TestCase

from recsys.algorithms.user_vector import UserVectorTrain
from recsys.models import UserVector


class TestUserVectorTrain(TestCase):

    def setUp(self) -> None:
        self.model = UserVectorTrain(8)

    def test_prepare_user_features(self):
        uids = ['60ee895ba22628d38b7442d4',
                '5ef2f3b74c775ed682ebce54',
                '642ce83a3f04ee4556a6d55d',
                '62a6d8fd2c6aa69d88956a7e',
                '6167e0e8d6f0002b50a01bce',
                '61889b2b2cbf5c036fedb536',
                '60f64c0206f573b7939056bc',
                '622af1f1e554229dc92da115',
                '62e9d77e2bfb75ad4faad16c',
                '62c40b4bef11d22fb90fd911',
                '5f6bfffd92c7f9be21bbcc99',
                ]
        self.model.prepare_user_features(uids)
        objs = UserVector.objects.all()
        self.assertEqual(len(objs), len(uids))
