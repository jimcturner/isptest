#!/bin/bash
# Script to install isptest into a raspberry Pi and register it as a service, so that it (optionally) starts automatically

# It will wget isptest.pyz and isptestlauncher.pyz and generateInstallScripts
# All install files will be copied into /opt/isptest

# generateInstallScripts.pyz will  create
#       1) A launcher config file with a name name based on the sync source ID
#       2) an isptest_service bash script that will invoke isptestlauncher with the file specified in 1)
#       3) An uninstall.sh script that will remove all traces of the application
#       4) An enable_start_isptest_boot.sh script (that will register isptest as a service to be started at boot)
#       5) A disable _start_isptest_boot.sh script (that will unregister isptest as a service, but not delete the isptest_service file)
#       NOTE: If generateInstallScripts.pyz [config file] is invoked guided mode/config file generation will be skipped and the
#             existing config filename will be incorporated into the bash scripts/config files generated by this Python script

# It will prompt the user:
#       Auto start at boot?, and if Yes, invoke the enable_start_isptest_boot.sh script
#       Add static route? If yes, will add a static route for the destination address in /lib/dhcpcd/dhcpcd-hooks/40-route


# Specify location of the Python Interpreter
# NOTE: The latest version of Raspberry Pi OS ships with Python 3.9 so the default system interpreter is fine
#PATH_TO_PYTHON_INTERPRETER="/usr/local/bin/python3.8" <<< - this is deprecated code. No longer need to specify the ver
# Get the absolute path of the 'system' python interpreter and store in PATH_TO_PYTHON_INTERPRETER
PATH_TO_PYTHON_INTERPRETER=`which python`

# Specify the path where the isptest application folder will be created
PATH_TO_ISPTEST="/opt"
# Specify the name of the folder that will be created in $PATH_TO_ISPTEST to hold all application data
ISPTEST_FOLDER_NAME="isptest"

# Specify the remote URL where the files isptestlauncher.pyz isptest.pyz and generateInstallScripts.pyz
# can be fetched for the initial installation. Additionally, this location will be passed to generateInstallScripts.pyz
# which will insert it into the resultant launcher config file used by isptestlauncher.pyz.
# When isptestlauncher.pyz receives an 'upgrade' request (via the isptest.pyz exit code, see isptestlauncher.pyz help)
# it will attempt to fetch a new version of isptest.pyz from this location
# when an update is triggered
# NOTE: isptest is currently hosted on git, hence this is currently Git branch dependant - see GIT_BRANCH variable
# specify the git branch to be used to download the .pyz application files
GIT_BRANCH="master"
ISPTEST_APPLICATION_FILES_URL="https://github.com/jimcturner/isptest/raw/$GIT_BRANCH"

# Specify the default stream destination IP address that will pre-populate the user dialog in the config wizard
WIZARD_DEFAULT_DEST_ADDRESS="212.58.231.102"
# Specify the default stream destination UDP port no that will pre-populate the user dialog in the config wizard
WIZARD_DEFAULT_UDP_DEST_PORT=8001
# Specify an additional switches to be passed to isptest (via the isptestlauncher config file)
# -c disables auto version checking
# -m specifies 'minimal write mode' to preserve the Raspberry Pi's SD card
ADDITIONAL_ISPTEST_SWITCHES="-c -m"


echo "isptest installer script V1.1, James Turner 03/05/22"
# Test to see if isptest folder already exists (from a previous installation)
if test -d "$PATH_TO_ISPTEST/$ISPTEST_FOLDER_NAME"; then
    echo "$PATH_TO_ISPTEST/$ISPTEST_FOLDER_NAME already exists, backing up existing contents into $PATH_TO_ISPTEST/$ISPTEST_FOLDER_NAME/old_files"
    cd "$PATH_TO_ISPTEST/$ISPTEST_FOLDER_NAME" || exit 1
    mkdir old_files
    mv * old_files
else
    echo "creating destination folder isptest in $PATH_TO_ISPTEST"
    cd $PATH_TO_ISPTEST || exit 1
    mkdir $ISPTEST_FOLDER_NAME
    cd "$PATH_TO_ISPTEST/$ISPTEST_FOLDER_NAME" || exit 1
fi


echo "getting python executables required for installation"
echo "getting isptestlauncher.pyz from $ISPTEST_APPLICATION_FILES_URL"
wget "$ISPTEST_APPLICATION_FILES_URL/isptestlauncher.pyz"

echo "getting isptest.pyz from $ISPTEST_APPLICATION_FILES_URL"
wget "$ISPTEST_APPLICATION_FILES_URL/isptest.pyz"

echo "getting generateInstallScripts.pyz from $ISPTEST_APPLICATION_FILES_URL"
wget "$ISPTEST_APPLICATION_FILES_URL/generateInstallScripts.pyz"

echo "installing dependencies: Linux screen"
apt-get install --assume-yes screen || { echo "apt-get install failed" && exit 1; }

# Create an array op options that will be passed to generateInstallScripts.pyz
opt=(--upgrade-url "$ISPTEST_APPLICATION_FILES_URL/isptest.pyz")
opt+=(--python-interpreter-path "$PATH_TO_PYTHON_INTERPRETER")
opt+=(--install-path "$PATH_TO_ISPTEST/$ISPTEST_FOLDER_NAME")
opt+=(--wizard-default-address "$WIZARD_DEFAULT_DEST_ADDRESS")
opt+=(--wizard-default-port "$WIZARD_DEFAULT_UDP_DEST_PORT")
opt+=(--additional-switches "$ADDITIONAL_ISPTEST_SWITCHES")

echo "Invoke generateInstallScripts.pyz to generate bash scripts required for installation:"
echo "$PATH_TO_PYTHON_INTERPRETER generateInstallScripts.pyz ${opt[*]}"
"$PATH_TO_PYTHON_INTERPRETER" generateInstallScripts.pyz "${opt[@]}"
