#!/bin/sh

. common.sh

find ../../recsys | grep -E "(__pycache__|\.pyc|\.pyo$)" | xargs rm -rf
unset http_proxy
unset https_proxy
unset all_proxy
cd ../../recsys; python manage.py test --debug-mode --failfast $*
