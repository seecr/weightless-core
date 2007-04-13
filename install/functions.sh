
# set -o nounset
set -o errexit

function message {
 echo "*
* $1
"
}

function isroot {
 if [ "`id -u`" != "0" ]
 then
   echo "Need to be root"
   exit -1
 fi
}


function aptitude_install {
	repository=$1
	distro=$2
	component=$3
	shift 3
	package=$*
	APTFILE=/etc/apt/sources.list.d/$distro'_'$component.list
	message "Adding temporary repository to APT ($repository $distro $component)"
	echo "deb $repository $distro $component" > $APTFILE
	aptitude update
	aptitude install $package
	message "Removing temporary repository ($repository $distro $component)"
	rm $APTFILE
	aptitude update
}
