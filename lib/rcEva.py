from rcUtilities import justcall, which
from xml.etree.ElementTree import XML, fromstring
import rcExceptions as ex
import os
import ConfigParser

pathlib = os.path.dirname(__file__)
pathbin = os.path.realpath(os.path.join(pathlib, '..', 'bin'))
pathetc = os.path.realpath(os.path.join(pathlib, '..', 'etc'))
pathtmp = os.path.realpath(os.path.join(pathlib, '..', 'tmp'))
if pathbin not in os.environ['PATH']:
    os.environ['PATH'] += ":"+pathbin

def sssu(cmd, manager, username, password, array=None):
    os.chdir(pathtmp)
    _cmd = ['sssu',
            "select manager %s username=%s password=%s"%(manager, username, password)]
    if array is not None:
        _cmd += ["select system %s"%array]
    _cmd += [cmd]
    out, err, ret = justcall(_cmd)
    if "Error" in out:
        print _cmd
        print out
        raise ex.excError("sssu command execution error")
    return out, err

class Evas(object):
    arrays = []

    def __init__(self):
        self.index = 0
        cf = os.path.join(pathetc, "sssu.conf")
        if not os.path.exists(cf):
            return
        conf = ConfigParser.RawConfigParser()
        conf.read(cf)
        m = {}
        for s in conf.sections():
            try:
                manager = conf.get(s, 'manager')
                username = conf.get(s, 'username')
                password = conf.get(s, 'password')
                m[manager] = [username, password]
            except:
                pass
        del(conf)
        done = []
        for manager, creds in m.items():
            username, password = creds
            out, err = sssu('ls system', manager, username, password)
            _in = False
            for line in out.split('\n'):
                if 'Systems avail' in line:
                    _in = True
                    continue
                if not _in:
                    continue
                name = line.strip()
                self.arrays.append(Eva(name, manager, username, password))
                done.append(name)

    def __iter__(self):
        return self

    def next(self):
        if self.index == len(self.arrays):
            raise StopIteration
        self.index += 1
        return self.arrays[self.index-1]

class Eva(object):
    def __init__(self, name, manager, username, password):
        self.name = name
        self.manager = manager
        self.username = username
        self.password = password
        #self.keys = ['controller']
        self.keys = ['controller', 'vdisk', 'lun']

    def sssu(self, cmd):
        return sssu(cmd, self.manager, self.username, self.password, array=self.name)

    def stripxml(self, buff):
        return buff[buff.index("<object>"):]

    def get_controller(self):
        cmd = 'ls controller full xml'
        buff = self.sssu(cmd)[0]
        return self.stripxml(buff)

    def get_vdisk(self):
        cmd = 'ls vdisk full xml'
        buff = self.sssu(cmd)[0]
        return self.stripxml(buff)

    def get_lun(self):
        cmd = 'ls lun full xml'
        buff = self.sssu(cmd)[0]
        return self.stripxml(buff)

if __name__ == "__main__":
    o = Evas()
    for eva in o:
        print eva.get_controller()
