""" Get cosine similarity of user vector and paper title vector.
"""
import logging

from recsys.models import UserVector
from recsys.algorithms.constants import Constants
from recsys.algorithms import get_vector_cosine
from recsys.ann import PaperVectorIndex


logger = logging.getLogger(__name__)


class Interest:
    MIN_SIM = 0.001

    def __init__(self, user_type, user_id):
        self.user_type = user_type
        self.user_id = user_id

    def get_similarity(self, title) :
        """ Get similarity of the user and title.
        :param title: str
        :return: float
        """
        if self.user_type != Constants.USER_UID:
            return self.MIN_SIM
        
        if not title:
            return self.MIN_SIM
        
        try:
            user_vector = UserVector.objects.get(uid=self.user_id)
        except Exception as e:
            logger.warning("except when get {}: {}".format(self.user_id, e))
            return self.MIN_SIM
        title_vector = PaperVectorIndex._get_text_vector(title)
        if not title_vector:
            logger.warning(f"uid {self.user_id}, title {title}, vector {title_vector} is blank")
        if isinstance(title, list):
            sims = []
            for i in range(len(title)):
                if title_vector:
                    sim = get_vector_cosine(user_vector.vector, title_vector[i])
                else:
                    sim = 0.0
                sims.append(sim)
        else:
            if title_vector:
                sims = get_vector_cosine(title_vector, user_vector.vector)
            else:
                sims = 0.0
        return sims
