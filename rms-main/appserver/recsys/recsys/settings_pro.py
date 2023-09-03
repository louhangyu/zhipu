"""
Django settings for recsys project.

Generated by 'django-admin startproject' using Django 3.2.5.

For more information on this file, see
https://docs.djangoproject.com/en/3.2/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/3.2/ref/settings/
"""

from .settings import *

DEBUG = False

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'rms',
        'USER': 'cacti',
        'PASSWORD': 'Cacti_12345',
        'HOST': '10.10.0.39',
        'PORT': '5432',
        "CHARSET": "utf-8",
    }
}

# Custom App config
RECOMMEND_REDIS = [
    {"host": "10.10.0.38", "port": "6379", "ssl": False, "password": "UEWA21CzY3Gwclf5pTXPdpsEUehFFiNQF+tl6NwADl4="},
]

# Celery Configuration Options
#CELERY_TIMEZONE = "Australia/Tasmania"
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 3600
CELERY_BROKER_URL = "redis://:UEWA21CzY3Gwclf5pTXPdpsEUehFFiNQF+tl6NwADl4=@10.10.0.38:6379/0"
CELERY_RESULT_BACKEND = "redis://:UEWA21CzY3Gwclf5pTXPdpsEUehFFiNQF+tl6NwADl4=@10.10.0.38:6379/1"
IMPORTS = ('recsys.background')


REPORT_RECEIVERS = [
    "peng.zhang@aminer.cn",
    "xiaotao.peng@aminer.cn",
    "meiling.huang@aminer.cn",
    "yifan.zhu@aminer.cn",
    "huihui.yuan@aminer.cn",
]

SPACY_WORD_LIB = "en_core_web_lg"

MONGO = {
    "aminer_reader": {
        'host': "192.168.6.208",
        'port': 37017,
        'authSource': "aminer",
        'user': "aminer_platform_reader",
        'password': "Reader@123",
    },
    "aminer": [
        {
            'host': "10.10.0.10",
            'port': 27017,
            'authSource': "admin",
            'user': "aminer_pengxiaotao",
            'password': "UEWA21CzY3Gwclf5pTXPdpsEUehFFiNQF",
        },
        {
            'host': "10.10.0.8",
            'port': 27017,
            'authSource': "admin",
            'user': "aminer_pengxiaotao",
            'password': "UEWA21CzY3Gwclf5pTXPdpsEUehFFiNQF",
        },
        {
            'host': "10.10.0.9",
            'port': 27017,
            'authSource': "admin",
            'user': "aminer_pengxiaotao",
            'password': "UEWA21CzY3Gwclf5pTXPdpsEUehFFiNQF",
        },
    ]
}

PERF_COLLECT_OUTPUT = "/data/weblog/perf.csv"


LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse'
        }
    },
    'formatters': {
        'verbose': {
            'format': '%(levelname)s %(asctime)s %(filename)s:%(funcName)s:%(lineno)d:: %(message)s'
        },
        'simple': {
            'format': '%(levelname)s %(message)s'
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'simple'
        },
        'mail_admins': {
            'level': 'ERROR',
            'filters': ['require_debug_false'],
            'class': 'recsys.admin_mail.AdminEmailHandler',
            'include_html': True,
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': "/data/weblog/rms.debug.log",
            'level': 'DEBUG',
            'formatter': 'verbose',
            'backupCount': 1,
            'maxBytes': 1024*1024*100,
        },
    },
    'loggers': {
        'gunicorn.errors': {
            'level': 'WARNING',
            'handlers': ['file', 'mail_admins'],
            'propagate': True,
        },
        '': {
            'handlers': ['file', "mail_admins"],
            'level': 'WARNING',
            #'level': 'DEBUG',
            'propagate': True,
        },
    }
}