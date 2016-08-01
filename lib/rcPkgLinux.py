import os
from rcUtilities import call, which
from rcGlobalEnv import rcEnv
import datetime
from stat import *

def listpkg_dummy():
    print("pushpkg supported on this system")
    return []

def listpkg_rpm():
    (ret, out, err) = call(cmd, errlog=False, cache=True)
    lines = []
    for line in out.split('\n'):
        if line.startswith('Signature'):
            sig = line.split()[-1].strip()
            continue
        elif not line.startswith('XX'):
            continue
        line = line[2:]
        l = line.split()
        if len(l) < 5:
            continue
        try:
            l[4] = datetime.datetime.fromtimestamp(int(l[4])).strftime("%Y-%m-%d %H:%M:%S")
        except:
            l[4] = ""
        x = [rcEnv.nodename] + l + [sig]
        lines.append(x)
    return lines

def listpkg_deb():
    (ret, out, err) = call(cmd, errlog=False, cache=True)
    lines = []
    arch = ""
    for line in out.split('\n'):
        l = line.split()
        if len(l) < 4:
            continue
        if l[0] != "ii":
            continue
        x = [rcEnv.nodename] + l[1:3] + [arch, "deb"]
        try:
            t = os.stat("/var/lib/dpkg/info/"+l[1]+".list")[ST_MTIME]
            t = datetime.datetime.fromtimestamp(t).strftime("%Y-%m-%d %H:%M:%S")
        except:
            t = ""
        x.append(t)
        lines.append(x)
    return lines

if which('dpkg') is not None:
    cmd = ['dpkg', '-l']
    listpkg = listpkg_deb
elif which('rpm') is not None:
    cmd = ['rpm', '-qai', '--queryformat=XX%{n} %{v}-%{r} %{arch} rpm %{installtime}\n']
    listpkg = listpkg_rpm
else:
    cmd = ['true']
    listpkg = listpkg_dummy

def listpatch():
    return [] 
