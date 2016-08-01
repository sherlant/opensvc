import resIp as Res
import rcExceptions as ex
from rcUtilitiesLinux import check_ping
from rcUtilities import which, to_cidr, to_dotted

class Ip(Res.Ip):
    def check_ping(self, timeout=5, count=1):
        self.log.info("checking %s availability"%self.addr)
        return check_ping(self.addr, timeout=timeout, count=count)

    def start_link(self):
        if which("ip"):
           cmd = ['ip', 'link', 'set', 'dev', self.ipDev, 'up']
        else:
           cmd = ['ifconfig', self.ipDev, 'up']
        ret, out, err = self.vcall(cmd)
        if ret != 0:
            return ret, out, err

    def startip_cmd(self):
        if ':' in self.addr:
            cmd = ['ifconfig', self.ipDev, 'inet6', 'add', '/'.join([self.addr, to_cidr(self.mask)])]
        else:
            cmd = ['ifconfig', self.stacked_dev, self.addr, 'netmask', to_dotted(self.mask), 'up']

        ret, out, err = self.vcall(cmd)
        if ret != 0:
            return ret, out, err

        # ip activation may still be incomplete
        # wait for activation, to avoid startapp scripts to fail binding their listeners
        for i in range(5, 0, -1):
            if check_ping(self.addr, timeout=1, count=1):
                return ret, out, err
        self.log.error("timed out waiting for ip activation")
        raise ex.excError

    def stopip_cmd(self):
        if ':' in self.addr:
            cmd = ['ifconfig', self.ipDev, 'inet6', 'del', '/'.join([self.addr, to_cidr(self.mask)])]
        else:
            if self.stacked_dev is None:
                return 1, "", "no stacked dev found"
            cmd = ['ifconfig', self.stacked_dev, 'down']
        return self.vcall(cmd)

if __name__ == "__main__":
    for c in (Ip,) :
        help(c)

