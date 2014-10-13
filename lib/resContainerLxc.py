#
# Copyright (c) 2009 Christophe Varoqui <christophe.varoqui@free.fr>'
# Copyright (c) 2009 Cyril Galibern <cyril.galibern@free.fr>'
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#
import os
from datetime import datetime
from subprocess import *

import sys
import rcStatus
import resources as Res
from rcUtilitiesLinux import check_ping
from rcUtilities import which, justcall
from rcGlobalEnv import rcEnv
import resContainer
import rcExceptions as ex

class Lxc(resContainer.Container):
    """
     container status transition diagram :
       ---------
      | STOPPED |<---------------
       ---------                 |
           |                     |
         start                   |
           |                     |
           V                     |
       ----------                |
      | STARTING |--error-       |
       ----------         |      |
           |              |      |
           V              V      |
       ---------    ----------   |
      | RUNNING |  | ABORTING |  |
       ---------    ----------   |
           |              |      |
      no process          |      |
           |              |      |
           V              |      |
       ----------         |      |
      | STOPPING |<-------       |
       ----------                |
           |                     |
            ---------------------
    """

    def files_to_sync(self):
        # the config file might be in a umounted fs resource
        # in which case, no need to ask for its sync as the sync won't happen
        try:
            self.find_cf()
        except:
            return []
        if self.cf is None:
            return []

        l = [self.cf]
        try:
            fstab = self.get_cf_value("lxc.mount")
            if os.path.exists(fstab):
                l.append(fstab)
        except:
            pass
        return l

    def rcp_from(self, src, dst):
        rootfs = self.get_rootfs()
        if len(rootfs) == 0:
            raise ex.excError()
        src = rootfs + src
        cmd = ['cp', src, dst]
        out, err, ret = justcall(cmd)
        if ret != 0:
            raise ex.excError("'%s' execution error:\n%s"%(' '.join(cmd), err))
        return out, err, ret

    def rcp(self, src, dst):
        rootfs = self.get_rootfs()
        if len(rootfs) == 0:
            raise ex.excError()
        dst = rootfs + dst
        cmd = ['cp', src, dst]
        out, err, ret = justcall(cmd)
        if ret != 0:
            raise ex.excError("'%s' execution error:\n%s"%(' '.join(cmd), err))
        return out, err, ret

    def lxc(self, action):
        self.find_cf()
        outf = '/var/tmp/svc_'+self.name+'_lxc_'+action+'.log'
        if action == 'start':
            cmd = ['lxc-start', '-d', '-n', self.name, '-o', outf, '-f', self.cf]
        elif action == 'stop':
            cmd = ['lxc-stop', '-n', self.name, '-o', outf]
        else:
            self.log.error("unsupported lxc action: %s" % action)
            return 1

        t = datetime.now()
        (ret, out, err) = self.vcall(cmd)
        len = datetime.now() - t
        self.log.info('%s done in %s - ret %i - logs in %s' % (action, len, ret, outf))
        if ret != 0:
            raise ex.excError

    def get_cf_value(self, param):
        self.find_cf()
        value = None
        if not os.path.exists(self.cf):
            return None
        with open(self.cf, 'r') as f:
            for line in f.readlines():
                if param not in line:
                    continue
                if line.strip()[0] == '#':
                    continue
                l = line.replace('\n', '').split('=')
                if len(l) < 2:
                    continue
                if l[0].strip() != param:
                    continue
                value = ' '.join(l[1:]).strip()
                break
        return value

    def get_rootfs(self):
        rootfs = self.get_cf_value("lxc.rootfs")
        if rootfs is None:
            self.log.error("could not determine lxc container rootfs")
            raise ex.excError
        return rootfs

    def install_drp_flag(self):
        rootfs = self.get_rootfs()
        flag = os.path.join(rootfs, ".drp_flag")
        self.log.info("install drp flag in container : %s"%flag)
        with open(flag, 'w') as f:
            f.write(' ')
            f.close()

    def container_start(self):
        self.lxc('start')

    def container_stop(self):
        self.lxc('stop')

    def container_forcestop(self):
        """ no harder way to stop a lxc container, raise to signal our
            helplessness
        """
        raise ex.excError

    def _ping(self):
        return check_ping(self.addr, timeout=1)

    def is_up_on(self, nodename):
        return self.is_up(nodename)

    def is_up(self, nodename=None):
        if which("lxc-ps"):
            return self.is_up_ps(nodename=nodename)
        else:
            return self.is_up_info(nodename=nodename)

    def is_up_info(self, nodename=None):
        cmd = ['lxc-info', '--name', self.name]
        if nodename is not None:
            cmd = rcEnv.rsh.split() + [nodename] + cmd
        out, err, ret = justcall(cmd)
        if ret != 0:
            return False
        if 'RUNNING' in out:
            return True
        return False

    def is_up_ps(self, nodename=None):
        cmd = ['lxc-ps', '--name', self.name]
        if nodename is not None:
            cmd = rcEnv.rsh.split() + [nodename] + cmd
        out, err, ret = justcall(cmd)
        if ret != 0:
            return False
        if self.name in out:
            return True
        return False

    def get_container_info(self):
        cpu_set = self.get_cf_value("lxc.cgroup.cpuset.cpus")
        if cpu_set is None:
            vcpus = 0
        else:
            vcpus = len(cpu_set.split(','))
        return {'vcpus': str(vcpus), 'vmem': '0'}

    def check_manual_boot(self):
        return True

    def check_capabilities(self):
        if not which('lxc-info'):
            self.log.debug("lxc-info is not in PATH")
            return False
        return True

    def find_cf(self):
        if self.cf is not None:
            return

        d_lxc = os.path.join('var', 'lib', 'lxc')

        # seen on debian squeeze : prefix is /usr, but containers'
        # config files paths are /var/lib/lxc/$name/config
        # try prefix first, fallback to other know prefixes
        prefixes = [os.path.join(os.sep),
                    os.path.join(os.sep, 'usr'),
                    os.path.join(os.sep, 'usr', 'local')]
        for prefix in [self.prefix] + [p for p in prefixes if p != self.prefix]:
            cf = os.path.join(prefix, d_lxc, self.name, 'config')
            if os.path.exists(cf):
                cf_d = os.path.dirname(cf)
                if not os.path.exists(cf_d):
                    os.makedirs(cf_d)
                self.cf = cf
                return

        # on Oracle Linux, config is in /etc/lxc
        cf = os.path.join(os.sep, 'etc', 'lxc', self.name, 'config')
        if os.path.exists(cf):
            self.cf = cf
            return

        self.cf = None
        raise ex.excError("unable to find the container configuration file")

    def find_prefix(self):
        prefixes = [os.path.join(os.sep),
                    os.path.join(os.sep, 'usr'),
                    os.path.join(os.sep, 'usr', 'local')]
        for prefix in prefixes:
             if os.path.exists(os.path.join(prefix, 'bin', 'lxc-start')):
                 return prefix
        return None

    def __init__(self,
                 rid,
                 name,
                 guestos="Linux",
                 cf=None,
                 optional=False,
                 disabled=False,
                 monitor=False,
                 restart=0,
                 subset=None,
                 tags=set([]),
                 always_on=set([])):
        resContainer.Container.__init__(self,
                                        rid=rid,
                                        name=name,
                                        type="container.lxc",
                                        guestos=guestos,
                                        optional=optional,
                                        disabled=disabled,
                                        monitor=monitor,
                                        restart=restart,
                                        subset=subset,
                                        tags=tags,
                                        always_on=always_on)

        if which('lxc-attach') and os.path.exists('/proc/1/ns/pid'):
            self.runmethod = ['lxc-attach', '-n', name, '--']
            # override getaddr from parent class with a noop
            self.getaddr = self.dummy
        else:
            self.runmethod = rcEnv.rsh.split() + [name]
            # enable ping test on start
            self.ping = self._ping
        self.cf = cf

    def dummy(self):
        pass

    def on_add(self):
        self.prefix = self.find_prefix()
        if self.prefix is None:
            self.log.error("lxc install prefix not found")
            raise ex.excInitError

    def __str__(self):
        return "%s name=%s" % (Res.Resource.__str__(self), self.name)

    def provision(self):
        m = __import__("provLxc")
        prov = m.ProvisioningLxc(self)
        prov.provisioner()
