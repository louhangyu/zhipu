#!/bin/sh


#cd /data/webapp/rms/appserver/recsys; /data/envs/rms/bin/celery -A recsys events
cd /data/webapp/rms/appserver/recsys; /data/envs/rms/bin/celery -A recsys flower
