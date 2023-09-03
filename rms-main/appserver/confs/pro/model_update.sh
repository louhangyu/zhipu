#!/bin/sh


WORK_DIR=`pwd`
HOT_PAPER="${WORK_DIR}/data/hot_paper_v.csv"
LDA_PAPER="${WORK_DIR}/data/papers.csv"
TEMP_OUTPUT="/data/weblog/rms_output_back"
OUTPUT="/data/weblog/rms_output"


case $1 in
train)
	./command.sh algorithm_update --mode train --hot-paper ${HOT_PAPER} --lda-paper ${LDA_PAPER} --output ${TEMP_OUTPUT} 
	if [ $? -eq 0 ]; then
	    cp -vrf ${TEMP_OUTPUT}/* ${OUTPUT}
	fi
;;
predict)
	./command.sh algorithm_update --mode predict --hot-paper ${HOT_PAPER} --lda-paper ${LDA_PAPER} --output ${TEMP_OUTPUT} 
	./command.sh algorithm_update --algorithm best --mode predict --hot-paper ${HOT_PAPER} --lda-paper ${LDA_PAPER} --output ${TEMP_OUTPUT} 
;;
*)
        echo "Usage: ./model_update.sh train|predict"
;;
esac



