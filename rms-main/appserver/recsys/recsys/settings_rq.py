from .settings_pro import *


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
            'class': 'django.utils.log.AdminEmailHandler',
            'include_html': True,
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': "/data/weblog/rms-rq.debug.log",
            'level': 'DEBUG',
            'formatter': 'verbose',
            'backupCount': 1,
            'maxBytes': 1024*1024*100,
        },
    },
    'loggers': {
        "rq.worker": {
            "handlers": ["file", "mail_admins"],
            "level": "WARNING"
        },
        '': {
            'handlers': ['file', "mail_admins"],
            'level': 'WARNING',
            'propagate': True,
        },
    }
}


