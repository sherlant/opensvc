import checks
from rcUtilities import justcall

class check(checks.check):
    chk_type = "vg_u"

    def find_svc(self, vgname):
        for svc in self.svcs:
            for rs in svc.get_res_sets('disk.vg'):
                for r in rs.resources:
                    if r.name == vgname:
                        return svc.svcname
        return ''

    def do_check(self):
        r = []
        cmd = ['lsvg']
        out, err, ret = justcall(cmd)
        if ret != 0:
            return self.undef
        vgs = out.split('\n')
        for vg in vgs:
            r += self._do_check(vg)
        return r

    def _do_check(self, vg):
        cmd = ['lsvg', '-p', vg]
        out, err, ret = justcall(cmd)
        if ret != 0:
            return self.undef
        lines = out.split('\n')
        if len(lines) < 3:
            return self.undef
        r = []
        for line in lines[2:]:
            l = line.split()
            if len(l) != 5:
                continue
            size = int(l[2])
            free = int(l[3])
            val = int(100*(size-free)/size)
            r.append({'chk_instance': vg,
                      'chk_value': str(val),
                      'chk_svcname': self.find_svc(l[0]),
                     }
                    )
        return r
