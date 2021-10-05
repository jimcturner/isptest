#!/bin/bash
echo "Crude Linux Shell script to install Python3.8.2 *alongside* any existing versions"
echo "based on the instructions found here: https://installvirtual.com/install-python-3-7-on-raspberry-pi/"
echo "cd into home folder"
cd ~/ || exit 1 # terminate the script if the folder can't be cd'd into
#echo "run sudo apt-get update"
#apt-get update || { echo "apt-get update failed" && exit 1; }
#echo "run sudo apt-get upgrade"
#apt-get upgrade

echo "installing dependencies"
apt-get install --assume-yes build-essential tk-dev libncurses5-dev libncursesw5-dev libreadline6-dev libdb5.3-dev libgdbm-dev libsqlite3-dev libssl-dev libbz2-dev libexpat1-dev liblzma-dev zlib1g-dev libffi-dev screen || { echo "apt-get install failed" && exit 1; }

echo "downloading Python installer into current folder"
wget https://www.python.org/ftp/python/3.8.2/Python-3.8.2.tgz || { echo "Failed to fetch Python installer" && exit 1; }

echo "unpacking Python installer"
sudo tar zxf Python-3.8.2.tgz || { echo "untar failed" && exit 1; }

echo "cd into Python-3.8.2 folder"
cd Python-3.8.2 || exit 1 # terminate the script if the folder can't be cd'd into
echo "building Python from source code"
./configure
make -j 4
make altinstall


