import os
import resIpLinux as Res
import rcExceptions as ex
import rcDocker
import rcIfconfigLinux as rcIfconfig
from rcUtilitiesLinux import check_ping
from rcUtilities import which, justcall, to_cidr

class Ip(Res.Ip, rcDocker.DockerLib):
    def __init__(self,
                 rid=None,
                 ipDev=None,
                 ipName=None,
                 mask=None,
                 gateway=None,
                 network=None,
                 del_net_route=False,
                 container_rid=None,
                 optional=False,
                 disabled=False,
                 tags=set([]),
                 always_on=set([]),
                 monitor=False,
                 restart=0,
                 subset=None):
        Res.Ip.__init__(self,
                        rid,
                        ipDev=ipDev,
                        ipName=ipName,
                        mask=mask,
                        optional=optional,
                        disabled=disabled,
                        tags=tags,
                        subset=subset,
                        always_on=always_on,
                        monitor=monitor,
                        restart=restart)
        self.gateway = gateway
        self.network = network
        self.del_net_route = del_net_route
        self.container_rid = str(container_rid)
        self.label = ipName + '@' + ipDev
        self.tags.add("docker")
        self.tags.add(container_rid)
        self.guest_dev = "eth1"

    def on_add(self):
        self.container_name = self.svc.svcname+'.'+self.container_rid
        self.container_name = self.container_name.replace('#', '.')
        rcDocker.DockerLib.on_add(self)
        try:
            self.container_id = self.get_container_id_by_name()
            self.label += '@' + self.container_id
        except Exception as e:
            self.container_id = None
            self.label += '@' + self.container_rid

    def arp_announce(self):
        """ disable the generic arping. We do that in the guest namespace.
        """
        pass

    def get_docker_ifconfig(self):
        try:
            nspid = self.get_nspid()
        except ex.excError as e:
            return
        self.create_netns_link(nspid=nspid, verbose=False)

        cmd = ["ip", "netns", "exec", nspid, "ip", "addr"]
        out, err, ret = justcall(cmd)
        if ret != 0:
            return

        self.delete_netns_link(nspid=nspid, verbose=False)

        ifconfig = rcIfconfig.ifconfig(ip_out=out)
        return ifconfig

    def is_up(self):
        ifconfig = self.get_docker_ifconfig()
        if ifconfig is None:
            return False
        if ifconfig.has_param("ipaddr", self.addr):
            return True
        return False

    def get_docker_interface(self):
        ifconfig = self.get_docker_ifconfig()
        if ifconfig is None:
            return
        for intf in ifconfig.intf:
            if self.addr in intf.ipaddr+intf.ip6addr:
                name = intf.name
                if "@" in name:
                    name = name[:name.index("@")]
                return name
        return

    def startip_cmd(self):
        if "dedicated" in self.tags:
            self.log.info("dedicated mode")
            return self.startip_cmd_dedicated()
        else:
            return self.startip_cmd_shared()

    def startip_cmd_shared(self):
        if os.path.exists("/sys/class/net/%s/bridge" % self.ipDev):
            self.log.info("bridge mode")
            return self.startip_cmd_shared_bridge()
        else:
            self.log.info("macvlan mode")
            return self.startip_cmd_shared_macvlan()

    def startip_cmd_dedicated(self):
        nspid = self.get_nspid()
        self.create_netns_link(nspid=nspid)

        # assign interface to the nspid
        cmd = ["ip", "link", "set", self.ipDev, "netns", nspid, "name", self.guest_dev]
        ret, out, err = self.vcall(cmd)
        if ret != 0:
            return ret, out, err

        # plumb the ip
        cmd = ["ip", "netns", "exec", nspid, "ip", "addr", "add", "%s/%s" % (self.addr, to_cidr(self.mask)), "dev", self.guest_dev]
        ret, out, err = self.vcall(cmd)
        if ret != 0:
            return ret, out, err

        # activate
        cmd = ["ip", "netns", "exec", nspid, "ip", "link", "set", self.guest_dev, "up"]
        ret, out, err = self.vcall(cmd)
        if ret != 0:
            return ret, out, err

        # add default route
        if self.gateway:
            cmd = ["ip", "netns", "exec", nspid, "ip", "route", "add", "default", "via", self.gateway, "dev", self.guest_dev]
            ret, out, err = self.vcall(cmd)
            if ret != 0:
                return ret, out, err

        # announce
        if which("arping") is not None:
            cmd = ["ip", "netns", "exec", nspid, "arping" , "-c", "1", "-A", "-I", self.guest_dev, self.addr]
            self.log.info(" ".join(cmd))
            out, err, ret = justcall(cmd)

        self.delete_netns_link(nspid=nspid)
        return 0, "", ""

    def startip_cmd_shared_bridge(self):
        nspid = self.get_nspid()
        self.create_netns_link(nspid=nspid)
        tmp_guest_dev = "v%spg%s" % (self.guest_dev, nspid)
        tmp_local_dev = "v%spl%s" % (self.guest_dev, nspid)
        mtu = self.ip_get_mtu()

        # create peer devs
        cmd = ["ip", "link", "add", "name", tmp_local_dev, "mtu", mtu, "type", "veth", "peer", "name", tmp_guest_dev, "mtu", mtu]
        ret, out, err = self.vcall(cmd)
        if ret != 0:
            return ret, out, err

        # activate the parent dev
        cmd = ["ip", "link", "set", tmp_local_dev, "master", self.ipDev]
        ret, out, err = self.vcall(cmd)
        if ret != 0:
            return ret, out, err
        cmd = ["ip", "link", "set", tmp_local_dev, "up"]
        ret, out, err = self.vcall(cmd)
        if ret != 0:
            return ret, out, err

        # assign the macvlan interface to the container namespace
        cmd = ["ip", "link", "set", tmp_guest_dev, "netns", nspid]
        ret, out, err = self.vcall(cmd)
        if ret != 0:
            return ret, out, err

        # rename the tmp guest dev
        cmd = ["ip", "netns", "exec", nspid, "ip", "link", "set", tmp_guest_dev, "name", self.guest_dev]
        ret, out, err = self.vcall(cmd)
        if ret != 0:
            return ret, out, err

        # plumb ip
        cmd = ["ip", "netns", "exec", nspid, "ip", "addr", "add", self.addr+"/"+to_cidr(self.mask), "dev", self.guest_dev]
        ret, out, err = self.vcall(cmd)
        if ret != 0:
            return ret, out, err

        # setup default route
        self.ip_setup_route(nspid)

        self.ip_wait()
        self.delete_netns_link(nspid=nspid)
        return 0, "", ""

    def startip_cmd_shared_macvlan(self):
        nspid = self.get_nspid()
        self.create_netns_link(nspid=nspid)
        tmp_guest_dev = "ph%s%s" % (nspid, self.guest_dev)
        mtu = self.ip_get_mtu()

        # create a macvlan interface
        cmd = ["ip", "link", "add", "link", self.ipDev, "dev", tmp_guest_dev, "mtu", mtu, "type", "macvlan", "mode", "bridge"]
        ret, out, err = self.vcall(cmd)
        if ret != 0:
            return ret, out, err

        # activate the parent dev
        cmd = ["ip", "link", "set", self.ipDev, "up"]
        ret, out, err = self.vcall(cmd)
        if ret != 0:
            return ret, out, err

        # assign the macvlan interface to the container namespace
        cmd = ["ip", "link", "set", tmp_guest_dev, "netns", nspid]
        ret, out, err = self.vcall(cmd)
        if ret != 0:
            return ret, out, err

        # rename the tmp guest dev
        cmd = ["ip", "netns", "exec", nspid, "ip", "link", "set", tmp_guest_dev, "name", self.guest_dev]
        ret, out, err = self.vcall(cmd)
        if ret != 0:
            return ret, out, err

        # plumb the ip
        cmd = ["ip", "netns", "exec", nspid, "ip", "addr", "add", "%s/%s" % (self.addr, to_cidr(self.mask)), "dev", self.guest_dev]
        ret, out, err = self.vcall(cmd)
        if ret != 0:
            return ret, out, err

        # setup default route
        self.ip_setup_route(nspid)

        self.ip_wait()
        self.delete_netns_link(nspid=nspid)
        return 0, "", ""

    def ip_get_mtu(self):
        # get mtu
        cmd = ["ip", "link", "show", self.ipDev]
        ret, out, err = self.call(cmd)
        if ret != 0:
            raise ex.excError("failed to get %s mtu: %s" % (self.ipDev, err))
        mtu = out.split()[4]
        return mtu

    def ip_setup_route(self, nspid):
        cmd = ["ip", "netns", "exec", nspid, "ip", "route", "del", "default"]
        ret, out, err = self.call(cmd, errlog=False)

        cmd = ["ip", "netns", "exec", nspid, "ip", "link", "set", self.guest_dev, "up"]
        ret, out, err = self.vcall(cmd)
        if ret != 0:
            return ret, out, err

        if self.gateway:
            cmd = ["ip", "netns", "exec", nspid, "ip", "route", "replace", "default", "via", self.gateway]
            ret, out, err = self.vcall(cmd)
            if ret != 0:
                return ret, out, err

        if self.del_net_route and self.network:
            cmd = ["ip", "netns", "exec", nspid, "ip", "route", "del", self.network+"/"+to_cidr(self.mask), "dev", self.guest_dev]
            ret, out, err = self.vcall(cmd)
            if ret != 0:
                return ret, out, err

        # announce
        if which("arping") is not None:
            cmd = ["ip", "netns", "exec", nspid, "arping" , "-c", "1", "-A", "-I", self.guest_dev, self.addr]
            self.log.info(" ".join(cmd))
            out, err, ret = justcall(cmd)

    def ip_wait(self):
        # ip activation may still be incomplete
        # wait for activation, to avoid startapp scripts to fail binding their listeners
        for i in range(15, 0, -1):
            if check_ping(self.addr, timeout=1, count=1):
                return
        raise ex.excError("timed out waiting for ip activation")

    def get_nspid(self):
        cmd = self.docker_cmd + ["inspect", "--format='{{ .State.Pid }}'", self.container_name]
        out, err, ret = justcall(cmd)
        if ret != 0:
            raise ex.excError("failed to get nspid: %s" % err)
        nspid = out.strip()
        if nspid == "0":
            raise ex.excError("nspid is 0")
        return nspid

    def delete_netns_link(self, nspid=None, verbose=True):
        if nspid is None:
            nspid = self.get_nspid()
        run_d = "/var/run/netns"
        if not os.path.exists(run_d):
            return
        run_netns = os.path.join(run_d, nspid)
        try:
            os.unlink(run_netns)
            if verbose:
                self.log.info("remove %s" % run_netns)
        except:
            pass

    def create_netns_link(self, nspid=None, verbose=True):
        if nspid is None:
            nspid = self.get_nspid()
        run_d = "/var/run/netns"
        if not os.path.exists(run_d):
            os.makedirs(run_d)
        run_netns = os.path.join(run_d, nspid)
        proc_netns = "/proc/%s/ns/net" % nspid
        if os.path.exists(proc_netns) and not os.path.exists(run_netns):
            if verbose:
                self.log.info("create symlink %s -> %s" % (run_netns, proc_netns))
            os.symlink(proc_netns, run_netns)
        # keep a reference on the run_netns file to prevent its removal during our run
        self.ns_fd = open(run_netns, "r")

    def stopip_cmd(self):
        intf = self.get_docker_interface()
        nspid = self.get_nspid()
        self.create_netns_link(nspid=nspid)
        if intf is None:
            raise ex.excError("can't find on which interface %s is plumbed in %s" % (self.addr, self.container_name))
        cmd = ["ip", "netns", "exec", nspid, "ip", "addr", "del", self.addr+"/"+to_cidr(self.mask), "dev", intf]
        ret, out, err = self.vcall(cmd)
        self.delete_netns_link(nspid=nspid)
        return ret, out, err


if __name__ == "__main__":
    help(Ip)

