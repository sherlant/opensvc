#
# Copyright (c) 2013 Christophe Varoqui <christophe.varoqui@opensvc.com>
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
# To change this template, choose Tools | Templates
# and open the template in the editor.

import os
import svc
import rcExceptions as ex
from rcUtilities import justcall
from rcGlobalEnv import rcEnv

class SvcVcs(svc.Svc):

    def __init__(self, svcname, pkg_name=None, optional=False, disabled=False, tags=set([])):
        svc.Svc.__init__(self, svcname, "vcs", optional=optional, disabled=disabled, tags=tags)
        self.pkg_name = pkg_name
        self.domainname = None
        self.vcs_operational = True

        self.n_ip = 0
        self.n_fs = 0
        self.n_vg = 0
        self.n_lv = 0

        self.builder()

    def get_res_val(self, res, p):
        if not self.vcs_operational:
            raise ex.excError("VCS is not operational")
        cmd = ['/opt/VRTSvcs/bin/hares', '-value', res, p]
        out, err, ret = justcall(cmd)
        if ret != 0:
            if "Cannot connect" in out:
                self.vcs_operational = False
            raise ex.excError(out)
        return out.strip()

    def get_grp_val(self, p):
        if not self.vcs_operational:
            raise ex.excError("VCS is not operational")
        cmd = ['/opt/VRTSvcs/bin/hagrp', '-value', self.pkg_name, p]
        out, err, ret = justcall(cmd)
        if ret != 0:
            if "Cannot connect" in out:
                self.vcs_operational = False
            raise ex.excError(out)
        return out.strip()

    def get_domainname(self):
        if self.domainname is not None:
            return self.domainname
        cmd = ['hostname', '-d']
        out, err, ret = justcall(cmd)
        if ret != 0:
            raise ex.excError(err)
        self.domainname = out
        return out.strip()

    def set_nodes(self):
        try:
            s = self.get_grp_val('SystemList')
        except ex.excError, e:
            self.nodes = set([rcEnv.nodename])
            return

        l = s.split()

        # SystemList goes in system/weight pairs
        if len(l) < 2 or len(l) % 2 != 0:
            raise ex.excError("unexpected SystemList value: %s"%s)

        self.nodes = set([])
        domainname = self.get_domainname()
        for i, w in enumerate(l):
            if i % 2 == 1:
                continue
            if len(domainname) > 0 and not w.endswith(domainname):
                w += '.' + domainname
            self.nodes.add(w)

    def builder(self):
        if self.pkg_name is None:
            raise ex.excInitError("pkg name is not set")
        self.set_nodes()
        self.load_hb()
        self.load_resources()

    def load_hb(self):
        rid = 'hb#vcs0'
        m = __import__("resHbVcs")
        r = m.Hb(rid, self.pkg_name)
        self += r

    def load_resources(self):
        if not self.vcs_operational:
            return
        cmd = ['/opt/VRTSvcs/bin/hagrp', '-resources', self.pkg_name]
        out, err, ret = justcall(cmd)
        if ret != 0:
            return
        resource_names = out.strip().split('\n')
        for resource_name in resource_names:
            self.load_resource(resource_name)

    def load_resource(self, name):
        s = self.get_res_val(name, 'Type')
        if s == 'Mount':
            self.load_fs(name)
            self.n_fs += 1
        elif s == 'CFSMount':
            self.load_cfs(name)
            self.n_fs += 1
        elif s  == 'DiskGroup':
            self.load_vg(name)
            self.n_vg += 1
        elif s == 'CVMVolDg':
            self.load_cvg(name)
            self.n_vg += 1
        elif s == 'Volume':
            self.load_lv(name)
            self.n_lv += 1
        elif s == 'IP':
            self.load_ip(name)
            self.n_ip += 1

    def load_lv(self, name):
        lvname = self.get_res_val(name, 'Volume')
        vgname = self.get_res_val(name, 'DiskGroup')
        disabled = True if self.get_res_val(name, 'Enabled') == "0" else False
        monitor = True if self.get_res_val(name, 'Critical') == "1" else False
        rid = 'lv#vcs%d'%self.n_lv
        m = __import__("resLvVcs"+rcEnv.sysname)
        r = m.Lv(rid, vgname, lvname, disabled=disabled, monitor=monitor)
        r.vcs_name = name
        self += r

    def load_cvg(self, name):
        vgname = self.get_res_val(name, 'CVMDiskGroup')
        disabled = True if self.get_res_val(name, 'Enabled') == "0" else False
        monitor = True if self.get_res_val(name, 'Critical') == "1" else False
        rid = 'vg#vcs%d'%self.n_vg
        m = __import__("resVgVcs"+rcEnv.sysname)
        r = m.Vg(rid, vgname, disabled=disabled, monitor=monitor)
        r.vcs_name = name
        self += r

    def load_vg(self, name):
        vgname = self.get_res_val(name, 'DiskGroup')
        disabled = True if self.get_res_val(name, 'Enabled') == "0" else False
        monitor = True if self.get_res_val(name, 'Critical') == "1" else False
        rid = 'vg#vcs%d'%self.n_vg
        m = __import__("resVgVcs"+rcEnv.sysname)
        r = m.Vg(rid, vgname, disabled=disabled, monitor=monitor)
        r.vcs_name = name
        self += r

    def load_ip(self, name):
        dev = self.get_res_val(name, 'Device')
        ipaddr = self.get_res_val(name, 'Address')
        netmask = self.get_res_val(name, 'NetMask')
        disabled = True if self.get_res_val(name, 'Enabled') == "0" else False
        monitor = True if self.get_res_val(name, 'Critical') == "1" else False
        rid = 'ip#vcs%d'%self.n_ip
        m = __import__("resIpVcs"+rcEnv.sysname)
        r = m.Ip(rid, dev, ipaddr, netmask, disabled=disabled, monitor=monitor)
        r.vcs_name = name
        self += r

    def load_fs(self, name):
        dev = self.get_res_val(name, 'BlockDevice')
        mnt = self.get_res_val(name, 'MountPoint')
        mntopt = self.get_res_val(name, 'MountOpt')
        fstype = self.get_res_val(name, 'FSType')
        disabled = True if self.get_res_val(name, 'Enabled') == "0" else False
        monitor = True if self.get_res_val(name, 'Critical') == "1" else False
        rid = 'fs#vcs%d'%self.n_fs
        m = __import__("resMountVcs"+rcEnv.sysname)
        r = m.Mount(rid, mnt, dev, fstype, mntopt,
                    disabled=disabled, monitor=monitor)
        r.vcs_name = name
        self += r

    def load_cfs(self, name):
        dev = self.get_res_val(name, 'BlockDevice')
        mnt = self.get_res_val(name, 'MountPoint')
        mntopt = self.get_res_val(name, 'MountOpt')
        fstype = self.get_res_val(name, 'AMFMountType')
        disabled = True if self.get_res_val(name, 'Enabled') == "0" else False
        monitor = True if self.get_res_val(name, 'Critical') == "1" else False
        rid = 'fs#vcs%d'%self.n_fs
        m = __import__("resMountVcs"+rcEnv.sysname)
        r = m.Mount(rid, mnt, dev, fstype, mntopt,
                    disabled=disabled, monitor=monitor)
        r.vcs_name = name
        self += r

    def resource_monitor(self):
        pass

