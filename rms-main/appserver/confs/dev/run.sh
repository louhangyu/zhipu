#!/bin/sh

./common.sh



case $1 in
app)
    cd ${WORK_DIR}; ${PYTHON} manage.py runserver
;;
test)
    shift
    cd ${WORK_DIR}; ${PYTHON} manage.py test $*
;;
rq)
    shift
    cd ${WORK_DIR}; ${PYTHON} manage.py rqworker $*
;;
migrate)
    cd ${WORK_DIR}; ${PYTHON} manage.py migrate
;;
help)
    cd ${WORK_DIR}; ${PYTHON} manage.py help
;;
*)
    echo "Usage: ./run.sh app|test|help|migrate|rq"
;; 
esac
