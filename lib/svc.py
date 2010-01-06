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
# To change this template, choose Tools | Templates
# and open the template in the editor.

from resources import Resource, ResourceSet
from freezer import Freezer
import rcStatus
from rcGlobalEnv import rcEnv
import rcExceptions as ex
from lock import svclock, svcunlock
import xmlrpcClient

def fork_dblogger(self, action, begin, end, actionlogfile):
    import os

    try:
        if os.fork() > 0:
            """ return to parent execution
            """
            return
    except:
        """ no dblogging will be done. too bad.
        """
        return

    """ separate the son from the father
    """
    os.chdir('/')
    os.setsid()
    os.umask(0)

    try:
        pid = os.fork()
        if pid > 0:
            os._exit(0)
    except:
        os._exit(1)

    xmlrpcClient.end_action(self, action, begin, end, actionlogfile)
    xmlrpcClient.svcmon_update(self, self.group_status())
    os.unlink(actionlogfile)
    os._exit(0)

class Svc(Resource, Freezer):
    """Service class define a Service Resource
    It contain list of ResourceSet where each ResourceSets contain same resource
    type
    """

    def __init__(self, svcname=None, type="hosted", optional=False, disabled=False):
        """usage : aSvc=Svc(type)"""
        if self.frozen():
            delattr(self.startip)
            delattr(self.stopip)
            delattr(self.mount)
            delattr(self.umount)
        self.svcname = svcname
        self.hostid = rcEnv.nodename
        self.resSets = []
        self.type2resSets = {}
        self.disks = set([])
        Resource.__init__(self, type, optional, disabled)
        Freezer.__init__(self, svcname)

    def __cmp__(self, other):
        """order by service name
        """
        return cmp(self.svcname, other.svcname)

    def __iadd__(self, r):
        """svc+=aResourceSet
        svc+=aResource
        """
        if r.type in self.type2resSets:
            self.type2resSets[r.type] += r

        elif isinstance(r, ResourceSet):
            self.resSets.append(r)
            self.type2resSets[r.type] = r

        elif isinstance(r, Resource):
            R = ResourceSet(r.type, [r])
            self.__iadd__(R)

        else:
            # Error
            pass

        return self

    def get_res_sets(self, type):
         return [ r for r in self.resSets if r.type == type ]

    def has_res_set(self, type):
        if len(get_res_sets(type)) > 0: return True
        else: return False

    def sub_set_action(self, type=None, action=None):
        """Call action on each member of the subset of specified type
        """
        for r in self.get_res_sets(type):
            try:
                r.action(action)
            except ex.excAbortAction:
                break

    def __str__(self):
        output="Service %s available resources:" % (Resource.__str__(self))
        for k in self.type2resSets.keys() : output += " %s" % k
        output+="\n"
        for r in self.resSets:  output+= "  [%s]" % (r.__str__())
        return output

    def status(self, type_list):
        """aggregate status a service
        """
        s = rcStatus.Status()
        for t in type_list:
            for r in self.get_res_sets(t):
                s += r.status()
        return s.status

    def print_status(self, type_list):
        """print each resource status for a service
        """
        for t in type_list:
            for r in self.get_res_sets(t): r.action("print_status")
        rcStatus.print_status("overall", self.status())

    def group_status(self, type_list):
        """print each resource status for a service
        """
        status = {}
        groups = ["container", "ip", "disk", "fs"]
        moregroups = groups + ["overall"]
        for group in moregroups:
            status[group] = rcStatus.Status(rcStatus.NA)
        for t in type_list:
            group = t.split('.')[0]
            if group not in groups:
                raise
            for r in self.get_res_sets(t):
                status[group] += r.status()
                status["overall"] += r.status()
        return status

    def disklist(self):
        """List all disks held by all resources of this service
        """
        disks = set()
        for rs in self.resSets:
            for r in rs.resources:
                disks |= r.disklist()
        self.log.debug("found disks %s held by service" % disks)
        return disks

    def startapp(self):
        self.sub_set_action("app", "start")

    def stopapp(self):
        self.sub_set_action("app", "stop")

    def syncnodes(self):
        self.sub_set_action("rsync", "syncnodes")

    def syncdrp(self):
        self.sub_set_action("rsync", "syncdrp")

    def scsirelease(self):
        self.sub_set_action("disk.vg", "scsirelease")
        self.sub_set_action("disk.zpool", "scsirelease")

    def scsireserv(self):
        self.sub_set_action("disk.vg", "scsireserv")
        self.sub_set_action("disk.zpool", "scsireserv")

    def scsicheckreserv(self):
        self.sub_set_action("disk.vg", "scsicheckreserv")
        self.sub_set_action("disk.zpool", "scsicheckreserv")

    def diskupdate(self):
        self.sub_set_action("disk.vg", "diskupdate")

    def action(self, action):
        from datetime import datetime
        import tempfile
        import logging
        begin = datetime.now()

        """Provision a database entry to store action log later
        """
        xmlrpcClient.begin_action(self, action, begin)

        """Per action logfile to push to database at the end of the action
        """
        f = tempfile.NamedTemporaryFile(delete=False, dir='/var/tmp', prefix=self.svcname+'.'+action)
        actionlogfile = f.name
        f.close()
        log = logging.getLogger()
        actionlogformatter = logging.Formatter("%(asctime)s;%(name)s;%(levelname)s;%(message)s;%(process)d;EOL")
        actionlogfilehandler = logging.FileHandler(actionlogfile)
        actionlogfilehandler.setFormatter(actionlogformatter)
        log.addHandler(actionlogfilehandler)

        """Trigger action
        """
        err = 0
        try:
            svclock(self)
            getattr(self, action)()
        except ex.excError:
            err = 1
            pass
        except:
            """Save the error for deferred raising
            """
            err = 1
            import traceback
            traceback.print_exc()

        """Push result and logs to database
        """
        actionlogfilehandler.close()
        log.removeHandler(actionlogfilehandler)
        end = datetime.now()
        svcunlock(self)
        fork_dblogger(self, action, begin, end, actionlogfile)
        return err

    def restart(self):
	""" stop then start service"""
	# FIXME should test stop() status before start()
        self.stop()
        self.start()


if __name__ == "__main__" :
    for c in (Svc,) :
        help(c)
    print """s1=Svc("Zone")"""
    s1=Svc("Zone")
    print "s1=",s1
    print """s2=Svc("basic")"""
    s2=Svc("basic")
    print "s2=",s2
    print """s1+=Resource("ip")"""
    s1+=Resource("ip")
    print "s1=",s1
    print """s1+=Resource("ip")"""
    s1+=Resource("ip")
    print """s1+=Resource("fs")"""
    s1+=Resource("fs")
    print """s1+=Resource("fs")"""
    s1+=Resource("fs")
    print "s1=",s1

    print """s1.action("status")"""
    s1.action("status")
