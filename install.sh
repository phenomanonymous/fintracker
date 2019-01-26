#!/usr/bin/env bash

# TODO: which python then handle pip vs pip3

command -v pip >/dev/null 2>&1 || { echo "pip is not installed, running `sudo easy_install pip`"; sudo easy_install pip; }
#echo ">pip installing virtualenv"
#pip install --user virtualenv
#echo ">creating virtualenv env"
#python -m virtualenv env
#source env/bin/activate

# CHECK HERE IF ROBINHOOD ALREADY EXISTS
echo ">Cloning robinhood repo and installing it as pip module"
git clone https://github.com/Jamonek/Robinhood.git
cd Robinhood
echo ">pip installing Robinhood"
pip install --user .
cd ..
echo ">Removing Robinhood dir"
rm -rf Robinhood
echo ">pip installing dependencies"
pip install --user httplib2 google-api-python-client oauth2client selenium selenium-requests

if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo ">sudo apt-get install chromium-chromedriver"
    sudo apt-get install chromium-chromedriver
elif [[ "$OSTYPE" == "darwin"* ]]; then # mac
    command -v brew >/dev/null 2>&1 || { echo "brew is not installed, installing brew"; /usr/bin/ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"; }
    echo ">brew cask install chromedriver"
    brew cask install chromedriver
else
    echo "Unhandled OS type"
fi

echo ">done"

