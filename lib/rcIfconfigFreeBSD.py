from subprocess import *

import rcIfconfig

class ifconfig(rcIfconfig.ifconfig):
    def parse(self, out):
        prev = ''
        prevprev = ''
        for w in out.split():
            if 'flags=' in w:
                i = rcIfconfig.interface(prev.replace(':',''))
                self.intf.append(i)

                # defaults
                i.link_encap = ''
                i.scope = ''
                i.bcast = ''
                i.mtu = ''
                i.ipaddr = []
                i.mask = []
                i.ip6addr = []
                i.ip6mask = []
                i.hwaddr = ''
                i.flag_up = False
                i.flag_broadcast = False
                i.flag_running = False
                i.flag_multicast = False
                i.flag_loopback = False

                flags = w.split('<')[1].split('>')[0].split(',')
                if 'UP' in flags:
                    i.flag_up = True
                if 'BROADCAST' in flags:
                    i.flag_broadcast = True
                if 'RUNNING' in flags:
                    i.flag_running = True
                if 'MULTICAST' in flags:
                    i.flag_multicast = True
                if 'LOOPBACK' in flags:
                    i.flag_loopback = True
            elif 'inet' == prev:
                i.ipaddr += [w]
            elif 'inet6' == prev:
                i.ip6addr += [w.split('%')[0]]
            elif 'netmask' == prev:
                i.mask += [w]
            elif 'prefixlen' == prev:
                i.ip6mask += [w]
            elif 'ether' == prev:
                i.hwaddr = w

            prevprev = prev
            prev = w

    def __init__(self, mcast=False):
        rcIfconfig.ifconfig.__init__(self, mcast=mcast)
        out = Popen(['ifconfig', '-a'], stdout=PIPE).communicate()[0]
        self.parse(out)

if __name__ == "__main__":
    o = ifconfig()
    print o
