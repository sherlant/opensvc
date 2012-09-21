#
# Copyright (c) 2012 Christophe Varoqui <christophe.varoqui@opensvc.com>
# Copyright (c) 2012 Lucien Hercaud <lucien@hercaud.com>
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
import checks
from rcUtilities import justcall, which
import os

path_list = os.environ['PATH'].split(':') + ['/opt/HPQacucli/sbin']
os.environ['PATH'] = ':'.join(path_list)

class check(checks.check):
    chk_type = "raid"
    chk_name = "HP SmartArray"

    def parse_errors(self, out):
        r = []
        lines = out.split('\n')
        if len(lines) == 0:
            return r
        for line in lines:
            l = line.split(': ')
            if len(l) < 2 or not line.startswith('  '):
                continue
            if l[-1].strip() != "OK":
                inst = line.strip().lower()
                status = 1
            else:
                inst = l[0].strip().lower()
                status = 0
            r += [(inst, status)]
        return r

    def check_logicaldrive(self, slot):
        cmd = ['hpacucli', 'controller', 'slot='+slot, 'logicaldrive', 'all', 'show', 'status']
        (out,err,ret) = justcall(cmd)
        if ret != 0:
            return []
        return self.parse_errors(out)

    def check_physicaldrive(self, slot):
        cmd = ['hpacucli', 'controller', 'slot='+slot, 'physicaldrive', 'all', 'show', 'status']
        (out,err,ret) = justcall(cmd)
        if ret != 0:
            return []
        return self.parse_errors(out)

    def check_array(self, slot):
        cmd = ['hpacucli', 'controller', 'slot='+slot, 'array', 'all', 'show', 'status']
        (out,err,ret) = justcall(cmd)
        if ret != 0:
            return []
        return self.parse_errors(out)

    def check_controller(self, slot):
        cmd = ['hpacucli', 'controller', 'slot='+slot, 'show', 'status']
        (out,err,ret) = justcall(cmd)
        if ret != 0:
            return []
        return self.parse_errors(out)

    def do_check(self):
        if not which('hpacucli'):
            return self.undef
        cmd = ['hpacucli', 'controller', 'all', 'show', 'status']
        (out,err,ret) = justcall(cmd)
        if ret != 0:
            return self.undef
        lines = out.split('\n')
        if len(lines) == 0:
            return self.undef
        r = []
        for line in lines:
            if ' Slot ' in line:
                l = line.split()
                idx = l.index('Slot')
                uslot = l[idx+1]
                slot = 'slot ' + uslot
                _r = []
                _r += self.check_controller(uslot)
                _r += self.check_array(uslot)
                _r += self.check_logicaldrive(uslot)
                _r += self.check_physicaldrive(uslot)
                for inst, value in _r:
                    r.append({
                          'chk_instance': ".".join((slot, inst)),
                          'chk_value': str(value),
                          'chk_svcname': '',
                         })
        return r
