"""
Django settings for recsys project.

Generated by 'django-admin startproject' using Django 3.2.5.

For more information on this file, see
https://docs.djangoproject.com/en/3.2/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/3.2/ref/settings/
"""
import os
import socket
from pathlib import Path


# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

ADMINS = [('xiaotao.peng', 'xiaotao.peng@aminer.cn')]


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/3.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-%!mt*h!=qb+7m0=^1+1cfp&l(2#y)ebhilg)k&qh#d6^)1b$3='


ALLOWED_HOSTS = ["*", "apiv2.aminer.cn", "pingback.aminer.cn", "localhost", "10.10.0.39", "10.10.0.38"]


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    "recsys",
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    #'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'recsys.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'recsys.wsgi.application'


# Database
# https://docs.djangoproject.com/en/3.2/ref/settings/#databases


# Password validation
# https://docs.djangoproject.com/en/3.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/3.2/topics/i18n/

LANGUAGE_CODE = 'zh-hans'

TIME_ZONE = 'Asia/Shanghai'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.2/howto/static-files/
STATIC_ROOT = os.path.join(os.path.dirname(__file__), "static")
STATIC_URL = '/static/'

# Default primary key field type
# https://docs.djangoproject.com/en/3.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.qiye.aliyun.com"
EMAIL_PORT = 465
EMAIL_HOST_USER = "support@aminer.cn"
EMAIL_HOST_PASSWORD = "Aminer@2022"
DEFAULT_FROM_EMAIL = "support@aminer.cn"
EMAIL_USE_SSL = True
SERVER_EMAIL = "support@aminer.cn"

EMAIL_SUBJECT_PREFIX = "[{}]: ".format(socket.gethostname())

###############################
# app config
###############################
APP_NAME = "Aminer Recsys"
APP_DESCRIPTION = "Speed Creative"

SSDB = {
    "host": "10.10.0.23",
    "port": 12000,
}

#ALGORITHM_NON_KEYWORD_URL = "http://10.10.0.29:40001/recommend/"
#ALGORITHM_KEYWORD_URL = "http://10.10.0.22:20219/tagRS/"

ALGORITHM_NON_KEYWORD_URL = "http://10.10.0.30/algorithm/non_keyword/"
ALGORITHM_KEYWORD_URL = "http://10.10.0.30/algorithm/keyword/"

FAISS_PAPER_PATH = "/data/cache/aminer/pub.json"
FAISS_EMB_PATH = "/data/cache/aminer/pub_emb.index"

HOT_TOPIC_PATH = "/data/cache/aminer/topic.json"


TEST_UDS = [
    "84b83bb6-b277-4184-8133-e13a9a777844",
    "jpe25Yqk8P1vwp_NsK6VM",
    "b1aca26c-ca90-4425-b8ee-df8218063cd7",
    "HFIot_rQsKVHWORZFR941",
    "5sWq2-NzkA4XjDSpxvkEb",
    "60AjcEdxxUXBpSeQlvSjp",
    "L3g7lgvR3C3eV30qJFfSB",
    "W1YyHga1GS2SMVy5kqd04",
    "TgUYJRZARI-NEHbgCHO0Z",
]


TEST_UIDS = [
    "56938f58c35f4f3ca3d3c591",
    "62144d9cae462b941a37dfe0",
    "6213ab39ae462b941a37df4c",
    "6233eca43fabba7e25e485e2",
    "6233ef4abf1a641bea556e62",
    "62106c1b757ab5a1ba7ccd7e",
    "5f168d674c775ed682f591d2",
    "5d380271530c7086034c4c58",
    '60ee895ba22628d38b7442d4',
]

SUBSCRIBE_SSDB_HOST = "10.10.0.22"
SUBSCRIBE_SSDB_PORT = 20210

GPU_HOST = "10.10.0.22"
GPU_PORT = 22
GPU_USER = "recommender"
GPU_HOME = "/data/cache/aminer"
GPU_HTTP_PORT = 30808
GPU_NON_KEYWORD_RESULT_URL = f"http://{GPU_HOST}:{GPU_HTTP_PORT}/aminer/output_recommendation"
GPU_USER_EVENT_LOG_URL = f"http://{GPU_HOST}:{GPU_HTTP_PORT}/aminer/"

LOCAL_CACHE_HOME = "/data/cache/aminer"
if DEBUG is False and not os.path.exists(LOCAL_CACHE_HOME):
    os.makedirs(LOCAL_CACHE_HOME)

HIGH_QUALITY_PAPER_ID_PATH = os.path.join(LOCAL_CACHE_HOME, "recall_pool.csv")
HIGH_QUALITY_PERSON_ID_PATH = os.path.join(LOCAL_CACHE_HOME, "recall_person.csv")

RECALL_DATA_URL = "http://10.10.0.38/aminer"

API_V2_HOSTS = [
    'apiv2.aminer.cn',
]

MEILI_SEARCH = "http://10.10.0.38:7700"
TOPIC_EMBEDDING_URL = "http://10.10.0.38/get_topic_embedding"
# dashboard url: http://10.10.0.38:8082/#/
TYPESENSE_SEARCH = {
    'nodes': [{
        'host': '10.10.0.38', # For Typesense Cloud use xxx.a1.typesense.net
        'port': '8108',      # For Typesense Cloud use 443
        'protocol': 'http'   # For Typesense Cloud use https
    }],
    'api_key': 'Aa4au1axLyery2QiXfNI8wWNOu3GWlVG1l9aCfoVWRkm8pth',
    'connection_timeout_seconds': 30
}

VECTOR_DB = {
    'nodes': [{
        'host': '10.10.0.22', # For Typesense Cloud use xxx.a1.typesense.net
        'port': '8108',      # For Typesense Cloud use 443
        'protocol': 'http'   # For Typesense Cloud use https
    }],
    'api_key': 'kXlOjmjgW4pSPvQmVvK0e88GtU34JklynXHG1jSSSjxlcR31',
    'connection_timeout_seconds': 30
}

MILVUS_HOST = "10.10.0.22"
MILVUS_PORT = "19530"

PERF_COLLECT_OUTPUT = os.path.join(os.path.dirname(__file__), "perf.csv")

DATA_API_FOREVER_TOKEN = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJhaWQiOiI2MTZmOTk5ZDRhMGY2M2EwNjRkNWYwNTEiLCJhdWQiOlsiYTIyNzI5OWMtMGZhNC00Y2JlLTk1YTgtYThhZjdjZTQ4MzdjIl0sImNpZCI6ImEyMjcyOTljLTBmYTQtNGNiZS05NWE4LWE4YWY3Y2U0ODM3YyIsImV4cCI6MTY2NjA2NTg4MiwiZ2VuZGVyIjowLCJpYXQiOjE2NjYwNjIyODIsImlkIjoiNjE2Zjk5OWQ0YTBmNjNhMDY0ZDVmMDUxIiwiaXNzIjoib2F1dGguYW1pbmVyLmNuIiwianRpIjoiN2RjZWIyMjYtYjU2MS00Zjc1LWE3ZmUtM2Y2YWE1NzRiZjMxIiwibmJmIjoxNjY2MDYyMjgyLCJuaWNrbmFtZSI6ImFtaW5lciIsInN1YiI6IjYxNmY5OTlkNGEwZjYzYTA2NGQ1ZjA1MSIsInQiOiJQYXNzd29yZCJ9.ZJruQEI2k4rDFz2hY-Wy8nmIb26kSnnWmDZ10nnvAuh-V6sFKdUYtEOBEJ6RPg87n6Ivu5WJ5IotEcyj8P9IwpHFpKTn4mBugTP3uxXlf7hJrdZYc2RgsL61GnZQHnY6p9PGleb8EzNQqki2bQj-QGRs7l-iUf_zUsIGygFy1ubsTGdRvA6qLupWuAfLaUSMkwxE-RvHxqzZ41jNhyd0CuRRC3EBRGklaKDfLQfhOQZV33juaxMB1xCrVgxUGdj9qjlGoMesGPMb-xIQWHt3eXHU5q3x67gjFj_ZVWvubAe2LWfj5-45LBQ2umhhw0GFf0QSJVi6UTWfG5BBWDExDA"
DATA_API_HOST = "http://gateway.private.aminer.cn/private"  # private host
APP_VER = "2023.01.05"

OPENAI_KEY = "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"
