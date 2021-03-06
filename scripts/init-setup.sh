#!/bin/sh
#: @author ionlights (John Muchovej)

alias echo="echo -e"
#: colors, because I'm a massochist that likes colored consoles.
#: NOTE: Using \033 ensures POSIX compatability, so it'll work on ANY system.
#:   Black        0;30     Dark Gray     1;30
#:   Red          0;31     Light Red     1;31
#:   Green        0;32     Light Green   1;32
#:   Brown/Orange 0;33     Yellow        1;33
#:   Blue         0;34     Light Blue    1;34
#:   Purple       0;35     Light Purple  1;35
#:   Cyan         0;36     Light Cyan    1;36
#:   Light Gray   0;37     White         1;37
c_RED="\033[0;31m"
c_NONE="\033[0m"

echo "+-----------------------------------------------------------------------+"
echo "| Setting up the \`ucfai-admin\` automation suite.                         |"
echo "+-----------------------------------------------------------------------+"
echo ""
if [[ $1 != "-y" ]]; then
    echo "I'm about to start setting up in the current directory!"
    echo "    `pwd`"
    echo "Shall I continue? [Y/n]"
    read cont

    if [[ cont != "y" || cont != "Y"]]; then
        echo "All right, I'll leave the folder be, then. :)"
        exit -1
    fi
fi

#: grab Jenkins
wget http://mirrors.jenkins.io/war-stable/latest/jenkins.war

#: clone all the repos to use in automation
git_url="git@github.com:ucfai"
declare -a git_repos=("admin data-science intelligence ucfai.github.io hackpack")
for repo in ${git_repos[@]}
do
    echo "> Cloning \`$repo\`..."
    git clone --quiet ${git_url}/${repo}
    if $?; then
        echo "\a${c_RED}!! Failed to clone \`$repo\`! Please do this manually "
        echo "to determine the error!${c_NONE}"
        exit -1
    fi
done

#: OS specific configs
OS=`uname -s`
miniconda_url="https://repo.anaconda.com/miniconda"
case $OS in
    "Darwin")
        echo "Why are you trying to run the build server on your laptop...?"
        wget ${miniconda_url}/Miniconda3-latest-MacOS-x86_64.sh -O miniconda.sh
        path="macos"
        exit
    "Linux")
        echo -n "I hope this is the build server, otherwise this is had better "
        echo "be for development."
        wget ${miniconda_url}/Miniconda3-latest-Linux-x86_64.sh -O miniconda.sh
        path="linux"
        ;;
esac

#: validate that `direnv` is installed
if ! command -v direnv; then
    echo -n "Please install \`direnv\`, this will save your \$PATH from being "
    echo    "modified heavily."
    exit -1
fi

#: install `conda` into an isolated "subsystem"
chmod +x miniconda3.sh
conda_dir="`pwd`/conda"
sh miniconda3.sh -p `pwd`/conda -b
echo "Now that \`conda\` is installed... Prepending your \$PATH with ${conda_dir}"
echo 'export PATH="${conda_dir}:$PATH"' >> .envrc

#: setup the `admin` env
sh admin/scripts/crud-conda-env.sh

unalias echo