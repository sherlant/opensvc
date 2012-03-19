#
# Copyright (c) 2011 Christophe Varoqui <christophe.varoqui@opensvc.com>
# Copyright (c) 2011 Cyril Galibern <cyril.galibern@opensvc.com>
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

import svc
import resContainerOvm as ovm
from rcGlobalEnv import rcEnv
from subprocess import *

class SvcOvm(svc.Svc):
    """ Define Ovm (xen) services"""

    def __init__(self, svcname, vmname=None, vmuuid=None, guestos=None, optional=False, disabled=False, tags=set([])):
        svc.Svc.__init__(self, svcname, optional=optional, disabled=disabled, tags=tags)
        if vmname is None:
            vmname = svcname
        self.vmuuid = vmuuid
        self.vmname = vmname
        self.guestos = guestos
        self += ovm.Ovm(vmname, vmuuid, disabled=disabled)
        self.runmethod = rcEnv.rsh.split() + [vmname]

    def _migrate(self):
        self.sub_set_action("container.ovm", "_migrate")

    def vm_hostname(self):
        if hasattr(self, 'vmhostname'):
            return self.vmhostname
        if self.guestos == "windows":
            self.vmhostname = self.vmname
            return self.vmhostname
        cmd = self.runmethod + ['hostname']
        p = Popen(cmd, stdout=PIPE, stderr=PIPE)
        out, err = p.communicate()
        if p.returncode != 0:
            self.vmhostname = self.vmname
        else:
            self.vmhostname = out.strip()
        return self.vmhostname

