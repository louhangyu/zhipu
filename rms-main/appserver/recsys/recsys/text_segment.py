''' Text segment.

标签	含义	标签	含义	标签	含义	标签	含义
n	普通名词	f	方位名词	s	处所名词	t	时间
nr	人名	ns	地名	nt	机构名	nw	作品名
nz	其他专名	v	普通动词	vd	动副词	vn	名动词
a	形容词	ad	副形词	an	名形词	d	副词
m	数量词	q	量词	r	代词	p	介词
c	连词	u	助词	xc	其他虚词	w	标点符号
PER	人名	LOC	地名	ORG	机构名	TIME	时间

'''
import jieba
import jieba.posseg
import os
import time
import logging


logger = logging.getLogger(__name__)


default_seg_kernel = None
default_posseg_kernel = None
default_stopwords = None


class TextSegment(object):


    def __init__(self, pos=True, use_paddle=False, use_hmm=True, cut_all=False):
        global default_seg_kernel, default_posseg_kernel, default_stopwords

        self.stopwords_dir = os.path.join(os.path.dirname(__file__), "stopwords")

        if default_posseg_kernel is None:
            default_posseg_kernel = jieba.posseg
        if default_seg_kernel is None:
            default_seg_kernel = jieba
        if default_stopwords is None:
            default_stopwords = set()
            default_stopwords |= self._load_stopwords(os.path.join(os.path.dirname(__file__), "stopwords/baidu_stopwords.txt"))
            default_stopwords |= self._load_stopwords(os.path.join(os.path.dirname(__file__), "stopwords/cn_stopwords.txt"))
            default_stopwords |= self._load_stopwords(os.path.join(os.path.dirname(__file__), "stopwords/hit_stopwords.txt"))
            default_stopwords |= self._load_stopwords(os.path.join(os.path.dirname(__file__), "stopwords/scu_stopwords.txt"))

        self.pos = pos
        self.use_paddle = use_paddle
        self.use_hmm = use_hmm
        self.cut_all = cut_all
        self.kernel = default_seg_kernel if pos is False else default_posseg_kernel
        self.stopwords = default_stopwords
        self.user_words_path = os.path.join(self.stopwords_dir, "user_words.txt")
        jieba.load_userdict(self.user_words_path)

    def _load_stopwords(self, path):
        stopwords = set()

        with open(path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                stopwords.add(line)

        return stopwords

    def is_stop(self, word, postag=None):
        word = word.strip()
        if not word:
            return True
        if word in ["None", "NULL"]:
            return True
        if postag and postag == "x":
            return True
        return word in self.stopwords

    def segment(self, text, remove_stopword=False):
        """
        :param
            text(String): text to segmented
        :return
            [(word, postag, is_stop)]: [(str, str, bool)]
        """
        if not text:
            return []
        start = time.time_ns()
        tokens = self.kernel.cut(text, HMM=self.use_hmm, use_paddle=self.use_paddle)
        if self.pos:
            segmented = [(word, pos, self.is_stop(word, pos)) for word, pos in tokens]
        else:
            segmented = [(x, "", self.is_stop(x)) for x in tokens]
        if remove_stopword:
            segmented = list(filter(lambda x: x[2] is False, segmented))
        end = time.time_ns()

        logger.info("Spend %.2f ns, %s => %s ", end-start, text, segmented)
        return segmented