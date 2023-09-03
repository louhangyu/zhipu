#!/bin/sh

PIP="/data/envs/rms/bin/pip"
PY="/data/envs/rms/bin/python"
HOSTS=`seq 49 57`


function python_libs() {
    ${PIP} install -r requirements.txt

    ${PY} -c "import nltk;nltk.download('wordnet');nltk.download('stopwords');nltk.download('omw-1.4');nltk.download('punkt');nltk.download('words')"

    #${PY} -m spacy download en_core_web_sm
    #${PY} -m spacy download en_core_web_lg
    ${PY} -m spacy download en_core_web_trf
}


function python_bins() {
    cd /home/aminer && \
    tar zxf Python-3.9.16.tgz && \
    cd Python-3.9.16 && \
    ./configure --enable-optimizations --prefix=/usr/local/python39 && \
    make && \
    make install && \
    mkdir /data/envs && \
    /usr/local/python39/bin/virtualenv /data/envs/rms
}


function system_bins() {
    sudo yum install -y git
    sudo yum install -y wget
}


function upload_python() {
    hosts=${HOSTS}
    #hosts="52"
    for h in $hosts
    do
        #scp -i ~/Documents/gitroom/devops/deploy/id_rsa ~/Downloads/Python-3.9.16.tgz aminer@192.168.0.${h}:/home/aminer
        scp -i ~/Documents/gitroom/devops/deploy/id_rsa ~/Downloads/en_core_web_trf-3.5.0-py3-none-any.whl aminer@192.168.0.${h}:/home/aminer
    done
}


function remote_install() {
    hosts=`seq 54 57`
    #hosts=${HOSTS}
    #hosts="54"
    for h in $hosts
    do
        echo "Host ${h}"
        ssh -i ~/Documents/gitroom/devops/deploy/id_rsa aminer@192.168.0.${h} 'bash -s' < ./remote.sh
    done
}


case $1 in
upload)
    upload_python
;;
local)
    #python_bins
    python_libs
;;
remote)
    remote_install
;;
*)
    echo "Usage: ./install.sh upload|local|remote"
;;
esac