#!/bin/sh


host="10.10.0.39"
port=6379
password="UEWA21CzY3Gwclf5pTXPdpsEUehFFiNQF+tl6NwADl4="

redis-cli -h ${host} -p ${port} -a ${password}
