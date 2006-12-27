
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

