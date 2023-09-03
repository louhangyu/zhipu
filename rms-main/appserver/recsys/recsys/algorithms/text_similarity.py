import logging
import string
import nltk
import numpy as np
from nltk.stem import WordNetLemmatizer
from nltk.corpus import stopwords
from nltk.corpus import words as english_words
from sklearn.feature_extraction.text import TfidfVectorizer

stop_words = set(stopwords.words('english'))
word_net_lemma = WordNetLemmatizer()
english_valid_words = set(english_words.words())

logger = logging.getLogger(__name__)


class TextSimilarity:

    def __init__(self):
        self.vec_model: TfidfVectorizer = TfidfVectorizer()

    def train(self, texts):
        texts = [" ".join(self.tidy_text(x)) for x in texts if x]
        if not texts:
            logger.warning(f"texts are empty.")
            return
        self.vec_model.fit(texts)
        #x = self.vec_model.fit_transform(texts)
        #logger.info(f"Train done. {x.shape}")

    def get_similarity(self, text1, text2):
        """ Get similarity of the text.
        :param text: str
        :return: float, similarity
        """
        v1 = self.get_vector(text1)
        v2 = self.get_vector(text2)
        if v1 is None:
            logger.info(f"'{text1}' vector is blank")
            return 0.0
        if v2 is None:
            logger.info(f"'{text2}' vector is blank")
            return 0.0
        s = float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))
        if np.isnan(s) or np.isinf(s):
            return 0.0

        return float(s)

    def get_vector(self, text):
        words = self.tidy_text(text)
        if not words:
            logger.warning("'{}' don't have valid words".format(text))
            return None
        vec = self.vec_model.transform([" ".join(words)]).toarray()[0]
        logger.info(f"{text} -> {vec}")
        return vec

    @classmethod
    def tidy_text(cls, title):
        """ Tokenize
        :param title: str
        :return: [str], return list of word
        """
        if not title:
            return []
        result = []
        words = nltk.wordpunct_tokenize(title.strip())
        words = [w.lower() for w in words if w not in string.punctuation]
        for w in words:
            w = word_net_lemma.lemmatize(w)
            if w not in stop_words:
                result.append(w)

        return result




