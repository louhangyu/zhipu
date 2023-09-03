#!/bin/sh

PY="/data/envs/rms/bin/python"

${PY} nginx_rotate.py rotate --accesslog /data/weblog/pingback.access.log --target /data/weblog/pingback

${PY} nginx_rotate.py rotate --accesslog /data/weblog/apiv2.access.log --target /data/weblog/apiv2
