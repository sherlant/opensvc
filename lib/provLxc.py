from provisioning import Provisioning
from rcGlobalEnv import rcEnv
import os

class ProvisioningLxc(Provisioning):
    config_template = """\
lxc.utsname = %(vm_name)s
lxc.tty = 4
lxc.pts = 1024
lxc.console = /tmp/%(vm_name)s.console

lxc.rootfs = %(rootfs)s
lxc.cgroup.devices.deny = a
# /dev/null and zero
lxc.cgroup.devices.allow = c 1:3 rwm
lxc.cgroup.devices.allow = c 1:5 rwm
# consoles
lxc.cgroup.devices.allow = c 5:1 rwm
lxc.cgroup.devices.allow = c 5:0 rwm
lxc.cgroup.devices.allow = c 4:0 rwm
lxc.cgroup.devices.allow = c 4:1 rwm
# /dev/{,u}random
lxc.cgroup.devices.allow = c 1:9 rwm
lxc.cgroup.devices.allow = c 1:8 rwm
lxc.cgroup.devices.allow = c 136:* rwm
lxc.cgroup.devices.allow = c 5:2 rwm
# rtc
lxc.cgroup.devices.allow = c 254:0 rwm

lxc.network.type = veth
lxc.network.flags = up
lxc.network.link = br0
lxc.network.name = eth0
lxc.network.mtu = 1500
"""
    def __init__(self, r):
        Provisioning.__init__(self, r)

        self.section = r.svc.config.defaults()

        # hostname file in the container rootfs
        self.p_hostname = os.path.join(self.section['rootfs'], 'etc', 'hostname')

        # container name and hostname
        if "vm_name" in self.section:
            self.vm_name = self.section["vm_name"]
        else:
            self.vm_name = self.r.svc.svcname

        # lxc root conf dir
        self.d_lxc = os.path.join(os.sep, 'var', 'lib', 'lxc')
        if not os.path.exists(self.d_lxc):
            self.d_lxc = os.path.join(os.sep, 'usr', 'local', 'var', 'lib', 'lxc')
        if not os.path.exists(self.d_lxc):
            self.d_lxc = None

        # container config file
        if self.d_lxc is not None:
            self.config = os.path.join(self.d_lxc, self.vm_name, 'config')

    def validate(self):
        if self.d_lxc is None:
            self.r.log.error("this node is not lxc capable")
            return True

        if not self.check_vm_name():
            return False

        if not self.check_lxc():
            self.r.log.error("container is not created")
            return False

        return True

    def check_lxc(self):
        if os.path.exists(self.config):
            return True
        return False

    def setup_lxc_config(self):
        import tempfile
        f = tempfile.NamedTemporaryFile(delete=False)
        f.write(self.config_template%dict(vm_name=self.vm_name, rootfs=self.section['rootfs']))
        self.config = f.name
        f.close()

    def setup_lxc(self):
        if self.check_lxc():
            self.r.log.info("container is already created")
            return
        name = self.setup_lxc_config()
        cmd = ['lxc-create', '-n', self.vm_name, '-f', self.config]
        (err, out) = self.r.vcall(cmd)
        if err == 0:
            return True
        return False

    def check_vm_name(self):
        if not os.path.exists(self.p_hostname):
            return False

        try:
            with open(self.p_hostname) as f:
                h = f.read().strip()
        except:
            self.r.log.error("can not get container hostname")
            raise
    
        if h != self.vm_name:
            self.r.log.info("container hostname is not %s"%self.vm_name)
            return False

        return True

    def set_vm_name(self):
        if self.check_vm_name():
            self.r.log.info("container hostname already set")
            return
        with open(self.p_hostname, 'w') as f:
            f.write(self.vm_name+'\n')
        self.r.log.info("container hostname set to %s"%self.vm_name)

    def get_template(self):
        template = self.section['template']
        self.template_fname = os.path.basename(template)
        self.template_local = os.path.join(rcEnv.pathtmp, self.template_fname)
        if os.path.exists(self.template_local):
            self.r.log.info("template %s already downloaded"%self.template_fname)
            return
        import urllib
        fname, headers = urllib.urlretrieve(template, self.template_local)
        if 'invalid file' in headers.values():
            self.r.log.error("%s not found"%template)
            raise

    def unpack_template(self):
        import tarfile
        os.chdir(self.section['rootfs'])
        tar = tarfile.open(name=self.template_local, errorlevel=0)
        if os.path.exists(os.path.join(self.section['rootfs'],'etc')):
            self.r.log.info("template already unpacked")
            return
        tar.extractall()
        tar.close()

    def setup_template(self):
        self.set_vm_name()

    def provisioner(self):
        path = self.section['rootfs']
        template = self.section['template']

        if not os.path.exists(path):
            os.makedirs(path)

        self.get_template()
        self.unpack_template()
        self.setup_template()
        self.setup_lxc()

        self.r.log.info("provisioned")
        return True
