FROM ubuntu:xenial
ENV DEBIAN_FRONTEND noninteractive
ENV TERM=xterm


RUN apt-get -y --force-yes update
RUN apt-get -y --force-yes  install locales


# Set the locale
RUN locale-gen en_US.UTF-8
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US:en
ENV LC_ALL en_US.UTF-8

# Upgrade packages
RUN apt-get -y --force-yes upgrade
RUN apt-get -y --force-yes install software-properties-common curl git wget unzip nano build-essential autoconf libxml2-dev libssl-dev libbz2-dev libcurl3-dev libjpeg-dev libpng-dev libfreetype6-dev libgmp3-dev libc-client-dev libldap2-dev libmcrypt-dev libmhash-dev freetds-dev libz-dev ncurses-dev libpcre3-dev libsqlite-dev libaspell-dev libreadline6-dev librecode-dev libsnmp-dev libtidy-dev libxslt-dev
RUN apt-get -y --force-yes install ruby-dev debhelper python3-dev devscripts libxml2-dev

RUN apt-get -y --force-yes install python3-pip python3-setuptools libpython3-dev
RUN apt-get -y --force-yes install python-pip python-setuptools libpython-dev
RUN apt-get install locales
RUN add-apt-repository "deb http://repo.aptly.info/ squeeze main" -y
RUN apt-key adv --keyserver keys.gnupg.net --recv-keys E083A3782A194991
RUN apt-get update
RUN apt-get -yq --force-yes install dh-virtualenv goaccess aptly

RUN apt-get install postgresql libpq-dev postgresql-client postgresql-client-common -y
RUN apt-get autoclean

ADD . /home/

WORKDIR /home/
