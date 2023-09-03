import os
import numpy as np
from sentence_transformers import SentenceTransformer, CrossEncoder

from django.conf import settings

from recsys.contriever.contriever import Contriever
from transformers import AutoTokenizer


sentence_model_cache_dir = os.path.join(settings.LOCAL_CACHE_HOME, "sentence_model")
if os.path.exists(sentence_model_cache_dir) is False:
    os.makedirs(sentence_model_cache_dir)

sentence_model_name = "distiluse-base-multilingual-cased-v1"
sentence_model_path = os.path.join(sentence_model_cache_dir, "sentence-transformers_" + sentence_model_name)
sentence_model = None
sentence_model_dim = 512

# contriever_model_name = "facebook/contriever-msmarco"
contriever_model_name = "facebook/mcontriever-msmarco"
contriever_model = None
contriever_model_dim = 768
token_model = None

cross_model_name = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
cross_model = None


def get_sentence_model():
    global sentence_model

    if sentence_model != None:
        return sentence_model

    if os.path.exists(sentence_model_path) is False:
        sentence_model = SentenceTransformer(model_name_or_path=sentence_model_name, cache_folder=sentence_model_cache_dir)
    else:
        sentence_model = SentenceTransformer(model_name_or_path=sentence_model_path, cache_folder=sentence_model_cache_dir)

    return sentence_model


def get_contriever_model():
    global contriever_model

    if contriever_model:
        return contriever_model
    
    contriever_model = Contriever.from_pretrained(contriever_model_name)
    return contriever_model


def get_token_model():
    global token_model
    if token_model:
        return token_model
    
    token_model = AutoTokenizer.from_pretrained(contriever_model_name)
    return token_model


def get_cross_model():
    global cross_model 
    if cross_model:
        return cross_model 
    
    cross_model = CrossEncoder(cross_model_name)
    return cross_model
    

def get_vector_cosine(v1, v2):
    if v1 is None or v2 is None:
        return 0.0
    v1 = np.asarray(v1)
    v2 = np.asarray(v2)

    sim = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
    if np.isnan(sim):
        return 0
    return sim
