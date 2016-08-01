import os

class Mount:
    def __init__(self, dev, mnt, type, mnt_opt):
        self.dev = dev.rstrip('/')
        self.mnt = mnt.rstrip('/')
        if mnt is '/':
            self.mnt = mnt
        self.type = type
        self.mnt_opt = mnt_opt

    def __str__(self):
        return "Mount: dev[%s] mnt[%s] type[%s] options[%s]" % \
            (self.dev,self.mnt,self.type,self.mnt_opt)

class Mounts:
    def __init__(self):
        """ OS dependent """
        self.mounts = []

    def __iter__(self):
        return iter(self.mounts)

    def match_mount(self):
        """ OS dependent """
        pass

    def mount(self, dev, mnt):
        for i in self.mounts:
            if self.match_mount(i, dev, mnt):
                return i
        return None

    def has_mount(self, dev, mnt):
        for i in self.mounts:
            if self.match_mount(i, dev, mnt):
                return True
        return False

    def has_param(self, param, value):
        for i in self.mounts:
            if getattr(i, param) == value:
                return i
        return None

    def sort(self, key='mnt', reverse=False):
        if len(self.mounts) == 0:
            return
        if key not in ('mnt', 'dev', 'type'):
            return
        self.mounts.sort(lambda x, y: cmp(getattr(x, key), getattr(y, key)), reverse=reverse)

    def get_fpath_dev(self, fpath):
        last = False
        d = fpath
        while not last:
            d = os.path.dirname(d)
            m = self.has_param("mnt", d)
            if m:
                return m.dev
            if d == os.sep:
                last = True

    def __str__(self):
        output="%s" % (self.__class__.__name__)
        for m in self.mounts:
            output+="\n  %s" % m.__str__()
        return output
