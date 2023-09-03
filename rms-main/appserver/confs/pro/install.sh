#!/bin/sh

PIP="/data/envs/rms/bin/pip"
PY="/data/envs/rms/bin/python"
HOSTS=`seq 49 57`


function python_libs() {
    ${PIP} install -r requirements.txt
    ${PY} -c "import nltk;nltk.download('wordnet');nltk.download('stopwords');nltk.download('omw-1.4');nltk.download('punkt');nltk.download('words')"
}


function python_bins() {
    sudo yum install -y gcc openssl-devel bzip2-devel libffi-devel sqlite-devel lzma-devel postgresql-devel 
    cd ~ && \
      tar zxf Python-3.11.3.tgz && \
      cd Python-3.11.3 && \
      ./configure --enable-optimizations --prefix=/usr/local/python311 && \
      make && \
      sudo make install && \
      sudo /usr/local/python311/bin/pip3 install virtualenv && \
      mkdir /data/envs && \
      /usr/local/python311/bin/virtualenv /data/envs/rms
}

function system_bins() {
    sudo yum install -y git
    sudo yum install -y wget
}


case $1 in
lib)
    python_libs
;;
bin)
    python_bins
;;
*)
    echo "Usage: ./install.sh bin|lib"
;;
esac
