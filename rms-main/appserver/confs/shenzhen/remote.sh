
install_python(){
    sudo yum install -y gcc openssl-devel bzip2-devel libffi-devel sqlite-devel lzma-devel postgresql-devel && \
    cd /home/aminer && \
    tar zxf Python-3.9.16.tgz && \
    cd Python-3.9.16 && \
    ./configure --enable-optimizations --prefix=/usr/local/python39 --with-ensurepip=install --enable-loadable-sqlite-extensions && \
    sudo make clean install && \
    mkdir /data/envs
}

install_venv(){
    sudo /usr/local/python39/bin/pip3 install -i https://pypi.tuna.tsinghua.edu.cn/simple virtualenv && \
    sudo mkdir -p /data/envs && \
    sudo chown -R aminer:aminer /data/envs && \
    /usr/local/python39/bin/virtualenv /data/envs/rms
}

install_nginx() {
    sudo yum install -y epel-release && \
    sudo yum install -y nginx
}

install_postgres() {
    sudo yum install -y net-tools
    sudo yum install -y https://download.postgresql.org/pub/repos/yum/reporpms/EL-7-x86_64/pgdg-redhat-repo-latest.noarch.rpm
    sudo yum install -y postgresql14-server
    sudo /usr/pgsql-14/bin/postgresql-14-setup initdb
    sudo systemctl enable postgresql-14
    sudo systemctl start postgresql-14
    # add user
    echo "Add User:"
    echo "sudo -u postgres psql"
    echo "CREATE USER cacti SUPERUSER;"
    echo "ALTER USER cacti WITH ENCRYPTED PASSWORD 'Cacti_12345';"
    echo "ALTER USER cacti WITH CREATEDB;"
    echo "ALTER USER cacti WITH LOGIN;"
    echo "create database rms;"
    echo "grant all privileges on database rms to cacti;"
    echo "CREATE USER reporter;"
    echo "ALTER USER reporter WITH ENCRYPTED PASSWORD 'report_1232*()';"
    echo "ALTER USER reporter WITH LOGIN;"
    echo "grant pg_read_all_data to reporter;"
    echo "CREATE USER feature_dev;"
    echo "ALTER USER feature_dev WITH ENCRYPTED PASSWORD 'howtodoit12345_*&%';"
    echo "ALTER USER feature_dev WITH LOGIN;"
    echo "grant pg_read_all_data to feature_dev;"
    echo "Append 'host  all  all 0.0.0.0/0 md5' to pg_hba.conf"

}

install_supervisord() {
    cd /data/webapp/rms/appserver/confs/shenzhen && ./install.sh local
    sudo systemctl disable firewalld
    sudo systemctl stop firewalld
    cd /etc/systemd/user; sudo ln -s /data/webapp/rms/appserver/confs/shenzhen/supervisord-rms.service
}

#install_python
#install_venv
install_nginx
#install_postgres
install_supervisord