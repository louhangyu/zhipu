#!/bin/sh


host="10.10.0.28"
port=6380
password="UEWA21CzY3Gwclf5pTXPdpsEUehFFiNQF+tl6NwADl4="

redis-cli -h ${host} -p ${port} -a ${password} --tls
