#
# Copyright (c) 2010 Christophe Varoqui <christophe.varoqui@free.fr>'
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
import logging

from rcGlobalEnv import rcEnv
from rcUtilities import which
from xml.etree.ElementTree import ElementTree, XML

import rcExceptions as ex
import rcStatus
import time
import datetime
import resSync
os.environ['PATH'] += ":/usr/symcli/bin"

class syncSymSrdfS(resSync.Sync):

    def postsync(self):
        self.do_dgimport()

    def presync(self):
        s = self.svc.group_status(excluded_groups=set(["sync", "hb"]))
        if self.svc.force or s['overall'].status == rcStatus.UP:
            self.do_rdf_dgexport()

    def files_to_sync(self):
        return [self.dgfile_rdf_name()]
   
    def do_local_dgexport(self):
        cmd = ['symdg', 'export', self.symdg, '-f', self.dgfile_local_name()]
        (ret, out, err) = self.call(cmd)
        if ret != 0:
            raise ex.excError("Failed to run command %s"% ' '.join(cmd) )
        return out
        
    def do_rdf_dgexport(self):
        cmd = ['symdg', 'export', self.symdg, '-f', self.dgfile_rdf_name(), '-rdf']
        (ret, out, err) = self.call(cmd)
        if ret != 0:
            raise ex.excError("Failed to run command %s"% ' '.join(cmd) )
        return out
        
    def do_dgremove(self):
        cmd = ['symdg', 'delete', self.symdg, '-force']
        (ret, out, err) = self.call(cmd)
        if ret != 0:
            raise ex.excError("Failed to run command %s"% ' '.join(cmd) )
        return out

    def is_dgimport_needed(self):
        self.do_local_dgexport()
        import filecmp
        if filecmp.cmp(self.dgfile_local_name(), self.dgfile_rdf_name(), shallow=False):
            return False
        return True

    def do_dgimport(self):
        if self.symdg in self.get_dg_list():
            if not self.is_dgimport_needed():
                self.log.info("symrdf dg %s is already up to date"%self.symdg)
                return
            else:
                self.do_dgremove()
        self.log.info("symrdf dg %s will be imported from file"%self.symdg)
        cmd = ['symdg', 'import', self.symdg, '-f', self.dgfile_rdf_name()]
        (ret, out, err) = self.call(cmd)
        if ret != 0:
            raise ex.excError("Failed to run command %s"% ' '.join(cmd) )
        return out

    def dgfile_local_name(self):
        return os.path.join(rcEnv.pathvar, 'symrdf_' + self.svc.svcname + '.dg.local')

    def dgfile_rdf_name(self):
        return os.path.join(rcEnv.pathvar, 'symrdf_' + self.svc.svcname + '.dg.rdf')

    def flush_cache(self):
        self.rdf_query_cache = None

    def get_symdevs(self):
        for symdev in self.symdevs:
            l = symdev.split(':')
            if len(l) != 2:
                self.log.error("symdevs must be in symid:symdev ... format")
                raise ex.excError
            self.symdev[l[0],l[1]] = dict(symid=l[0], symdev=l[1])

    def rdf_query(self, cache=True):
        if cache and self.rdf_query_cache is not None:
            return self.rdf_query_cache
        cmd = ['symrdf', '-g', self.symdg, '-rdfg', str(self.rdfg), 'query', '-output', 'xml_e']
        (ret, out, err) = self.call(cmd)
        if ret != 0:
            raise ex.excError("Failed to run command %s"% ' '.join(cmd) )
        self.rdf_query_cache = out
        return out

    def dg_query(self):
        cmd = ['symdg', 'list', '-output', 'xml_e']
        (ret, out, err) = self.call(cmd)
        if ret != 0:
            raise ex.excError("Failed to run command %s"% ' '.join(cmd) )
        return out

    # browse local device groups and build dict with list
    def get_dg_list(self):
        try:
            rdf_query = self.dg_query()
        except:
            return {}
        self.xmldg = XML(rdf_query)
        self.dglist = {} 
        for dg in self.xmldg.iter("DG_Info"):
	        name = dg.find('name').text
	        self.dglist[name] = None
        
        return self.dglist

    def get_dg_rdf_type(self):
        rdf_query = self.rdf_query()
        self.xmldg = XML(rdf_query)
        rdftype = self.xmldg.find('DG/DG_Info/type').text
        return rdftype

    def is_rdf1_dg(self):
        if self.get_dg_rdf_type() == "RDF1":
            return True
        return False

    def is_rdf2_dg(self):
        if self.get_dg_rdf_type() == "RDF2":
            return True
        return False

    def is_rdf21_dg(self):
        if self.get_dg_rdf_type() == "RDF21":
            return True
        return False


    def get_dg_state(self):
        h = {}
        for pair in self.xmldg.iter("RDF_Pair"):
            mode = pair.find('mode').text
            state = pair.find('pair_state').text
            key = mode + "/" + state
            h[key] = None
        if len(h) == 1:
            retmsg = h.keys()[0]
        else:
            retmsg = "mixed srdf pairs state"
        return retmsg

    def get_rdfpairs_from_dg(self):
        cmd = ['symrdf', '-g', self.symdg, '-rdfg', str(self.rdfg), 'query', '-output', 'xml_e']
        (ret, out, err) = self.call(cmd)
        if ret != 0:
            raise ex.excError

	    self.rdfpairs = {}   # remote_symm;remote_dev;rdfg
	    self.xmldg = XML(out)

        for pair in self.xmldg.iter("RDF_Pair"):
	        source = pair.find('Source/dev_name').text
	        target = pair.find('Target/dev_name').text
	        self.rdfpairs[source] = target
        print self.rdfpairs

    def is_synchronous_mode(self):
        cmd = ['/usr/symcli/bin/symrdf', '-g', self.symdg, '-rdfg', str(self.rdfg), 'verify', '-synchronous']
        (ret, out, err) = self.call(cmd)
        if ret == 0:
            return True
        return False

    def is_asynchronous_mode(self):
        cmd = ['/usr/symcli/bin/symrdf', '-g', self.symdg, '-rdfg', str(self.rdfg), 'verify', '-asynchronous']
        (ret, out, err) = self.call(cmd)
        if ret == 0:
            return True
        return False

    def is_acp_disk_mode(self):
        cmd = ['/usr/symcli/bin/symrdf', '-g', self.symdg, '-rdfg', str(self.rdfg), 'verify', '-acp_disk']
        (ret, out, err) = self.call(cmd)
        if ret == 0:
            return True
        return False

    def is_synchronized_state(self):
        cmd = ['/usr/symcli/bin/symrdf', '-g', self.symdg, '-rdfg', str(self.rdfg), 'verify', '-synchronized']
        (ret, out, err) = self.call(cmd)
        if ret == 0:
            return True
        return False

    def is_synchronous_and_synchronized_state(self):
        cmd = ['/usr/symcli/bin/symrdf', '-g', self.symdg, '-rdfg', str(self.rdfg), 'verify', '-synchronous', '-synchronized']
        (ret, out, err) = self.call(cmd)
        if ret == 0:
            return True
        return False

    def is_syncinprog_state(self):
        cmd = ['/usr/symcli/bin/symrdf', '-g', self.symdg, '-rdfg', str(self.rdfg), 'verify', '-syncinprog']
        (ret, out, err) = self.call(cmd)
        if ret == 0:
            return True
        return False

    def is_suspend_state(self):
        cmd = ['/usr/symcli/bin/symrdf', '-g', self.symdg, '-rdfg', str(self.rdfg), 'verify', '-suspended']
        (ret, out, err) = self.call(cmd)
        if ret == 0:
            return True
        return False

    def is_split_state(self):
        cmd = ['/usr/symcli/bin/symrdf', '-g', self.symdg, '-rdfg', str(self.rdfg), 'verify', '-split']
        (ret, out, err) = self.call(cmd)
        if ret == 0:
            return True
        return False

    def is_failedover_state(self):
        cmd = ['/usr/symcli/bin/symrdf', '-g', self.symdg, '-rdfg', str(self.rdfg), 'verify', '-failedover']
        (ret, out, err) = self.call(cmd)
        if ret == 0:
            return True
        return False

    def is_partitioned_state(self):
        cmd = ['/usr/symcli/bin/symrdf', '-g', self.symdg, '-rdfg', str(self.rdfg), 'verify', '-partitioned']
        (ret, out, err) = self.call(cmd)
        if ret == 0:
            return True
        return False

    # SRDF/A expected state is consistent AND enabled
    def is_consistent_state(self):
        cmd = ['/usr/symcli/bin/symrdf', '-g', self.symdg, '-rdfg', str(self.rdfg), 'verify', '-consistent']
        (ret, out, err) = self.call(cmd)
        if ret == 0:
            return True
        return False

    def is_enabled_state(self):
        cmd = ['/usr/symcli/bin/symrdf', '-g', self.symdg, '-rdfg', str(self.rdfg), 'verify', '-enabled']
        (ret, out, err) = self.call(cmd)
        if ret == 0:
            return True
        return False

    def can_sync(self, target=None):
        return True

    def resume(self):
        cmd = ['/usr/symcli/bin/symrdf', '-g', self.symdg, '-rdfg' , str(self.rdfg), '-noprompt', 'resume']
        (ret, out, err) = self.vcall(cmd)
        if ret != 0:
            raise ex.excError("Failed to run command %s"% ' '.join(cmd) )
        self.flush_cache()

    def suspend(self):
        cmd = ['/usr/symcli/bin/symrdf', '-g', self.symdg, '-rdfg' , str(self.rdfg), '-noprompt', 'suspend']
        (ret, out, err) = self.vcall(cmd)
        if ret != 0:
            raise ex.excError("Failed to run command %s"% ' '.join(cmd) )
        self.flush_cache()

    def establish(self):
        cmd = ['/usr/symcli/bin/symrdf', '-g', self.symdg, '-rdfg' , str(self.rdfg), '-noprompt', 'establish']
        (ret, out, err) = self.vcall(cmd)
        if ret != 0:
            raise ex.excError("Failed to run command %s"% ' '.join(cmd) )
        self.flush_cache()

    def failover(self):
        cmd = ['/usr/symcli/bin/symrdf', '-g', self.symdg, '-rdfg' , str(self.rdfg), '-noprompt', 'failover']
        (ret, out, err) = self.vcall(cmd)
        if ret != 0:
            raise ex.excError("Failed to run command %s"% ' '.join(cmd) )
        self.flush_cache()

    def failoverestablish(self):
        cmd = ['/usr/symcli/bin/symrdf', '-g', self.symdg, '-rdfg' , str(self.rdfg), '-noprompt', 'failover', '-establish']
        (ret, out, err) = self.vcall(cmd)
        if ret != 0:
            raise ex.excError("Failed to run command %s"% ' '.join(cmd) )
        self.flush_cache()

    def split(self):
        cmd = ['/usr/symcli/bin/symrdf', '-g', self.symdg, '-rdfg' , str(self.rdfg), '-noprompt', 'split']
        (ret, out, err) = self.vcall(cmd)
        if ret != 0:
            raise ex.excError
        self.flush_cache()

    def swap(self):
        cmd = ['/usr/symcli/bin/symrdf', '-g', self.symdg, '-rdfg' , str(self.rdfg), '-noprompt', 'swap']
        (ret, out, err) = self.vcall(cmd)
        if ret != 0:
            raise ex.excError
        self.flush_cache()

    def get_syminfo(self):
        # self.get_symdevs()
	    self.get_dg_rdf_type()
        #self.get_symld()
       # self.get_pairs()

    def get_last(self):
        if self.last is not None:
            return
        for symid, symdev in self.symdev:
            ld = self.symld[symid,symdev]
            # format: Thu Feb 25 10:20:56 2010
            last = datetime.datetime.strptime(ld['clone_lastaction'], "%a %b %d %H:%M:%S %Y")
            if self.last is None or last > self.last:
                self.last = last

    def _status(self, verbose=False):
        try:
            self.get_syminfo()
        except ex.excError as e:
            self.status_log(str(e))
            return rcStatus.WARN
        state = self.get_dg_state()
        self.status_log("current state %s"%state)
        if self.is_synchronous_and_synchronized_state():
            return rcStatus.UP
        self.status_log("expecting synchronous/synchronized")
        return rcStatus.WARN

    # SRDF split 
    def syncsplit(self):
        self.split()

    # SRDF suspend 
    def syncquiesce(self):
        self.suspend()

    # SRDF swap
    def syncswap(self):
        self.swap()

    def syncbreak(self):
        self.split()

    # SRDF establish
    def syncresync(self):
        self.establish()

    def syncestablish(self):
        self.establish()

    def start(self):
        if rcEnv.nodename in self.svc.drpnodes:
            if self.is_rdf2_dg():
                if self.is_synchronous_and_synchronized_state():
                    self.split()
                    return
                elif self.is_partitioned_state():
                    self.log.warning("symrdf dg %s is RDF2 and partitioned. failover is preferred action."%self.symdg)
                    self.failover()
                    return
                elif self.is_failedover_state():
                    self.log.info("symrdf dg %s is already RDF2 and FailedOver."%self.symdg)
                    return
                elif self.is_suspend_state():
                    self.log.warning("symrdf dg %s is RDF2 and suspended: R2 data may be outdated"%self.symdg)
                    self.split()
                    return
                elif self.is_split_state():
                    self.log.info("symrdf dg %s is RDF2 and already splitted."%self.symdg)
                    return
                else:
                    raise ex.excError("symrdf dg %s is RDF2 on drp node and unexpected SRDF state, you have to manually return to a sane SRDF status.")
            elif self.is_rdf1_dg():
                if self.is_synchronous_and_synchronized_state():
                    return
                else:
                    raise ex.excError("symrdf dg %s is RDF1 on drp node, you have to manually return to a sane SRDF status.")
        elif rcEnv.nodename in self.svc.nodes:
            if self.is_rdf1_dg():
                if self.is_synchronous_and_synchronized_state():
                    self.log.info("symrdf dg %s is RDF1 and synchronous/synchronized."%self.symdg)
                    return
                elif self.is_partitioned_state():
                    self.log.warning("symrdf dg %s is RDF1 and partitioned."%self.symdg)
                    return
                elif self.is_failedover_state():
                    raise ex.excError("symrdf dg %s is RDF1 and write protected, you have to manually run either syncsplit+syncestablish (ie loosing R2 data), or syncfailback (ie loosing R1 data)"%self.symdg)
                elif self.is_suspend_state():
                    self.log.warning("symrdf dg %s is RDF1 and suspended."%self.symdg)
                    return
                elif self.is_split_state():
                    self.log.warning("symrdf dg %s is RDF1 and splitted."%self.symdg)
                    return
                else:
                    raise ex.excError("symrdf dg %s is RDF1 on primary node and unexpected SRDF state, you have to manually return to a sane SRDF status.")
            elif self.is_rdf2_dg():         # start on metrocluster passive node
                if self.is_synchronous_and_synchronized_state():
                    self.failoverestablish() 
                elif self.is_partitioned_state():
                    self.log.warning("symrdf dg %s is RDF2 and partitioned, failover is preferred action."%self.symdg)
                    self.failover() 
                    return
                else:
                    raise ex.excError("symrdf dg %s is RDF2 on primary node, you have to manually return to a sane SRDF status.")

# self.svc.force = True ou False            

    def refresh_svcstatus(self):
        self.svcstatus = self.svc.group_status(excluded_groups=set(["sync", 'hb']))

    def get_svcstatus(self):
        if len(self.svcstatus) == 0:
            self.refresh_svcstatus()

    def __init__(self,
                 rid=None,
                 symdg=None,
                 rdfg=None,
                 symdevs=[],
                 precopy_timeout=300,
                 sync_max_delay=None,
                 sync_interval=None,
                 sync_days=None,
                 sync_period=None,
                 optional=False,
                 disabled=False,
                 tags=set([]),
                 internal=False,
                 subset=None):
        resSync.Sync.__init__(self,
                              rid=rid,
                              type="sync.symsrdfs",
                              sync_max_delay=sync_max_delay,
                              sync_interval=sync_interval,
                              sync_days=sync_days,
                              sync_period=sync_period,
                              optional=optional,
                              disabled=disabled,
                              tags=tags,
                              subset=subset)

        self.rdf_query_cache = None
        self.label = "srdf/s symdg %s"%(symdg)
        self.symdg = symdg
        self.rdfg = rdfg
        self.symdevs = symdevs
        self.precopy_timeout = precopy_timeout
        self.disks = set([])
        self.symdev = {}
        self.pdevs = {}
        self.svcstatus = {}
        self.symld = {}
        self.pairs = []
        self._pairs = []
        self.active_pairs = []
        self.last = None

    def __str__(self):
        return "%s symdg=%s symdevs=%s rdfg=%s" % (resSync.Sync.__str__(self),\
                self.symdg, self.symdevs, self.rdfg)

