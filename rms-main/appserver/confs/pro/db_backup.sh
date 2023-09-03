#!/bin/sh

tables="recsys_hotpaper recsys_subject recsys_ad"
cmd="sudo docker run -u postgres --rm --name pgloader dimitri/pgloader:latest pgloader"

for t in $tables
do
    #if [ ! -f backup/${t}.sql ]; then
    #    mysqldump -h10.10.0.31 -u'azure@recommendation' -p'O8nryiMCQMz31W$' --no-create-info --default-character-set=utf8 --extended-insert rms $t > backup/$t.sql
    #fi

	#if [ ! -f backup/$t.tsv ]; then
	#	/data/envs/rms/bin/python /home/pengxiaotao/mysqldump-to-csv-tsv/mysqldump_to_tsv.py backup/$t.sql > backup/${t}.tsv
	#fi

    echo "$t"	
done

	

$cmd \
	  'mysql://cacti:cacti123@10.10.0.31/rms' \
	  'postgresql:///rms'
	  
#'postgresql://cacti:Cacti_12345@10.10.0.39/rms'
