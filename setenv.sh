#!/bin/bash

export PATH=/usr/bin:/mingw64/bin:/mingw32/bin:$PATH

_mhmake=`which mhmake 2> /dev/null`
if [ ! -x "$_mhmake" ] ; then
  echo "Executable mhmake not found, using x64 in-tree build instead."
  DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
  export PATH=$DIR/tools/mhmake/Release64:$PATH
fi

rm -f commands.sh
python2 setenv.py $1 > commands.sh
chmod +x commands.sh
source commands.sh
rm -f commands.sh
if [[ "$MHMAKECONF" == "" ]] ; then
  export MHMAKECONF=`cygpath -w $DIR`
  export PYTHON3=python3
fi

export IS64=$1

