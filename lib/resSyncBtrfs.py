import os
from rcGlobalEnv import rcEnv
import datetime
from subprocess import *
import rcExceptions as ex
import rcStatus
import resSync
from rcUtilities import justcall
import rcBtrfs

class SyncBtrfs(resSync.Sync):
    """define btrfs sync resource to be btrfs send/btrfs receive between nodes
    """
    def sort_rset(self, rset):
        rset.resources.sort(lambda x, y: cmp(x.src_subvol, y.src_subvol))

    def __init__(self,
                 rid=None,
                 target=None,
                 src=None,
                 dst=None,
                 delta_store=None,
                 sender=None,
                 recursive=False,
                 snap_size=0,
                 sync_max_delay=None,
                 schedule=None,
                 optional=False,
                 disabled=False,
                 tags=set([]),
                 subset=None):
        resSync.Sync.__init__(self,
                              rid=rid,
                              type="sync.btrfs",
                              sync_max_delay=sync_max_delay,
                              schedule=schedule,
                              optional=optional,
                              disabled=disabled,
                              tags=tags,
                              subset=subset)

        self.label = "btrfs of %s to %s"%(src, ", ".join(target))
        self.target = target
        self.sender = sender
        self.recursive = recursive

        if ":" not in src or src.index(":") == len(src) - 1:
            raise ex.excInitError("malformed src value")
        if ":" not in dst or dst.index(":") == len(dst) - 1:
            raise ex.excInitError("malformed dst value")

        self.src_label = src[:src.index(":")]
        self.src_subvol = src[src.index(":")+1:]
        if dst is None:
            self.dst_label = self.src_label
            self.dst_subvol = self.src_subvol
        else:
            self.dst_label = dst[:dst.index(":")]
            self.dst_subvol = dst[dst.index(":")+1:]

        if delta_store is None:
            self.delta_store = rcEnv.pathvar
        else:
            self.delta_store = delta_store
        self.dst_btrfs = {}
        self.src_btrfs = None

    def init_src_btrfs(self):
        if self.src_btrfs is not None:
            return
        try:
            self.src_btrfs = rcBtrfs.Btrfs(label=self.src_label, log=self.log)
        except rcBtrfs.ExecError as e:
            raise ex.excError(str(e))

    def pre_action(self, rset, action):
        """Prepare snapshots
        Don't sync PRD services when running on !PRD node
        skip snapshot creation if delay_snap in tags
        delay_snap should be used for oracle archive datasets
        """
        resources = [ r for r in rset.resources if not r.skip and not r.is_disabled() ]

        if len(resources) == 0:
            return

        if not action.startswith('sync'):
            return

        s = self.svc.group_status(excluded_groups=set(["sync", "hb", "app"]))
        if not self.svc.force and s['overall'].status != rcStatus.UP:
            self.log.debug("won't sync this resource for a service not up")
            raise ex.excAbortAction

        if self.svc.svctype == 'PRD' and rcEnv.host_mode != 'PRD':
            self.log.debug("won't sync a PRD service running on a !PRD node")
            raise ex.excAbortAction

        self.init_src_btrfs()
        for i, r in enumerate(resources):
            if 'delay_snap' in r.tags:
                continue
            r.get_targets(action)
            tgts = r.targets.copy()
            if len(tgts) == 0:
                continue

            r.get_src_info()

            if not r.src_btrfs.has_subvol(r.src_snap_tosend):
                r.create_snap(r.src, r.src_snap_tosend)

    def __str__(self):
        return "%s target=%s src=%s" % (resSync.Sync.__str__(self),\
                self.target, self.src)

    def create_snap(self, snap_orig, snap):
        self.init_src_btrfs()
        try:
            self.src_btrfs.snapshot(snap_orig, snap, readonly=True, recursive=self.recursive)
        except rcBtrfs.ExistError:
            self.log.error('%s should not exist'%snap)
            raise ex.excError
        except rcBtrfs.ExecError:
            raise ex.excError

    def get_src_info(self):
        self.init_src_btrfs()
        subvol = self.src_subvol.replace('/','_')
        base = self.src_btrfs.snapdir + '/' + subvol
        self.src_snap_sent = base + '@sent'
        self.src_snap_tosend = base + '@tosend'
        self.src = os.path.join(self.src_btrfs.rootdir, self.src_subvol)

    def get_dst_info(self, node):
        if node not in self.dst_btrfs:
            try:
                self.dst_btrfs[node] = rcBtrfs.Btrfs(label=self.dst_label, log=self.log, node=node)
            except rcBtrfs.ExecError as e:
                raise ex.excError(str(e))
            #self.dst_btrfs[node].setup_snap()
        subvol = self.src_subvol.replace('/','_')
        base = self.dst_btrfs[node].snapdir + '/' + subvol
        self.dst_snap_sent = base + '@sent'
        self.dst_snap_tosend = base + '@tosend'
        self.dst = os.path.join(self.dst_btrfs[node].rootdir, self.dst_subvol)

    def get_peersenders(self):
        self.peersenders = set([])
        if 'nodes' == self.sender:
            self.peersenders |= self.svc.nodes
            self.peersenders -= set([rcEnv.nodename])

    def get_targets(self, action=None):
        self.targets = set()
        if 'nodes' in self.target and action in (None, 'sync_nodes'):
            self.targets |= self.svc.nodes
        if 'drpnodes' in self.target and action in (None, 'sync_drp'):
            self.targets |= self.svc.drpnodes
        self.targets -= set([rcEnv.nodename])

    def sync_nodes(self):
        self._sync_update('sync_nodes')

    def sync_drp(self):
        self._sync_update('sync_drp')

    def sanity_checks(self):
        if not self.svc.force:
            s = self.svc.group_status(excluded_groups=set(["sync", "hb", "app"]))
            if s['overall'].status != rcStatus.UP:
                if not self.svc.cron:
                    self.log.info("won't sync this resource for a service not up")
                raise ex.excError

        """ Refuse to sync from a flex non-primary node
        """
        if self.svc.clustertype in ["flex", "autoflex"] and \
           self.svc.flex_primary != rcEnv.nodename:
            if not self.svc.cron:
                self.log.info("won't sync this resource from a flex non-primary node")
            raise ex.excError

    def sync_full(self):
        self.init_src_btrfs()
        try:
            self.sanity_checks()
        except ex.excError:
            return
        self.get_src_info()
        if not self.src_btrfs.has_subvol(self.src_snap_tosend):
            self.create_snap(self.src, self.src_snap_tosend)
        self.get_targets()
        for n in self.targets:
            self.get_dst_info(n)
            self.btrfs_send_initial(n)
            self.rotate_snaps(n)
            self.install_snaps(n)
        self.rotate_snaps()
        self.write_statefile()
        for n in self.targets:
            self.push_statefile(n)

    def btrfs_send_incremental(self, node):
        if self.recursive :  
            send_cmd = ['btrfs', 'send', '-R',
                        '-c', self.src_snap_sent,
                        '-p', self.src_snap_sent,
                        self.src_snap_tosend]
        else:
            send_cmd = ['btrfs', 'send',
                        '-c', self.src_snap_sent,
                        '-p', self.src_snap_sent,
                        self.src_snap_tosend]

        receive_cmd = ['btrfs', 'receive', self.dst_btrfs[node].snapdir]
        if node is not None:
            receive_cmd = rcEnv.rsh.strip(' -n').split() + [node] + receive_cmd

        self.log.info(' '.join(send_cmd + ["|"] + receive_cmd))
        p1 = Popen(send_cmd, stdout=PIPE)
        p2 = Popen(receive_cmd, stdin=p1.stdout, stdout=PIPE)
        buff = p2.communicate()
        if p2.returncode != 0:
            if buff[1] is not None and len(buff[1]) > 0:
                self.log.error(buff[1])
            self.log.error("sync update failed")
            raise ex.excError
        if buff[0] is not None and len(buff[0]) > 0:
            self.log.info(buff[0])

    def btrfs_send_initial(self, node=None):
        if self.recursive :  
            send_cmd = ['btrfs', 'send', '-R', self.src_snap_tosend]
        else:
            send_cmd = ['btrfs', 'send', self.src_snap_tosend]

        receive_cmd = ['btrfs', 'receive', self.dst_btrfs[node].snapdir]
        if node is not None:
            receive_cmd = rcEnv.rsh.strip(' -n').split() + [node] + receive_cmd

        self.log.info(' '.join(send_cmd + ["|"] + receive_cmd))
        p1 = Popen(send_cmd, stdout=PIPE)
        p2 = Popen(receive_cmd, stdin=p1.stdout, stdout=PIPE)
        buff = p2.communicate()
        if p2.returncode != 0:
            if buff[1] is not None and len(buff[1]) > 0:
                self.log.error(buff[1])
            self.log.error("full sync failed")
            raise ex.excError
        if buff[0] is not None and len(buff[0]) > 0:
            self.log.info(buff[0])

    def remove_snap_tosend(self, node=None):
        self.init_src_btrfs()
        if node is not None:
            o = self.dst_btrfs[node]
            subvol = self.dst_snap_tosend
        else:
            o = self.src_btrfs
            subvol = self.src_snap_tosend

        if not o.has_subvol(subvol):
            return

        try:
            o.subvol_delete(subvol, recursive=self.recursive)
        except rcBtrfs.ExecError:
            raise ex.excError()

    def remove_snap(self, node=None):
        self.init_src_btrfs()
        if node is not None:
            o = self.dst_btrfs[node]
            subvol = self.dst_snap_sent
        else:
            o = self.src_btrfs
            subvol = self.src_snap_sent

        if not o.has_subvol(subvol):
            return

        try:
            o.subvol_delete(subvol, recursive=self.recursive)
        except rcBtrfs.ExecError:
            raise ex.excError()

    def rename_snap(self, node=None):
        self.init_src_btrfs()
        if node is None:
            o = self.src_btrfs
            src = self.src_snap_tosend
            dst = self.src_snap_sent
        else:
            o = self.dst_btrfs[node]
            src = self.dst_snap_tosend
            dst = self.dst_snap_sent

        if o.has_subvol(dst):
            self.log.error("%s should not exist"%self.dst_snap_sent)
            raise ex.excError

        if self.recursive :
            # ??
            cmd = ['mv', src, dst]
        else:
            cmd = ['mv', src, dst]

        if node is not None:
            cmd = rcEnv.rsh.split() + [node] + cmd
        ret, out, err = self.vcall(cmd)

        if ret != 0:
            raise ex.excError

    def remove_dst(self, node=None):
        if node is None:
            return

        subvols = self.dst_btrfs[node].get_subvols_in_path(self.dst)

        try:
            self.dst_btrfs[node].subvol_delete(subvols)
        except rcBtrfs.ExecError:
            raise ex.excError()
            
    def install_dst(self, node=None):
        if node is None:
            return
        try:
            self.dst_btrfs[node].snapshot(self.dst_snap_sent, self.dst, readonly=False)
        except rcBtrfs.ExistError:
            self.log.error('%s should not exist'%snap)
            raise ex.excError()
        except rcBtrfs.ExecError:
            self.log.error("failed to install snapshot %s on node %s"%(self.dst, node))
            raise ex.excError()

    def install_snaps(self, node=None):
        self.remove_dst(node)
        self.install_dst(node)

    def rotate_snaps(self, node=None):
        self.remove_snap(node)
        self.rename_snap(node)

    def _sync_update(self, action):
        self.init_src_btrfs()
        try:
            self.sanity_checks()
        except ex.excError:
            return
        self.get_targets(action)
        if len(self.targets) == 0:
            return
        self.get_src_info()

        if not self.src_btrfs.has_subvol(self.src_snap_tosend):
            self.create_snap(self.src, self.src_snap_tosend)

        for n in self.targets:
            self.get_dst_info(n)
            self.remove_snap_tosend(n)
            if self.src_btrfs.has_subvol(self.src_snap_sent) and self.dst_btrfs[n].has_subvol(self.dst_snap_sent):
                self.btrfs_send_incremental(n)
            else:
                self.btrfs_send_initial(n)
            self.rotate_snaps(n)
            self.install_snaps(n)

        self.rotate_snaps()
        self.write_statefile()
        for n in self.targets:
            self.push_statefile(n)

    def start(self):
        pass

    def stop(self):
        pass

    def can_sync(self, target=None):
        try:
            ls = self.get_local_state()
            ts = datetime.datetime.strptime(ls['date'], "%Y-%m-%d %H:%M:%S.%f")
        except IOError:
            self.log.error("btrfs state file not found")
            return True
        except:
            import sys
            import traceback
            e = sys.exc_info()
            print(e[0], e[1], traceback.print_tb(e[2]))
            return False
        if self.skip_sync(ts):
            self.status_log("Last sync on %s older than %i minutes"%(ts, self.sync_max_delay))
            return False
        return True

    def _status(self, verbose=False):
        self.init_src_btrfs()
        try:
            ls = self.get_local_state()
            now = datetime.datetime.now()
            last = datetime.datetime.strptime(ls['date'], "%Y-%m-%d %H:%M:%S.%f")
            delay = datetime.timedelta(minutes=self.sync_max_delay)
        except IOError:
            self.status_log("btrfs state file not found")
            return rcStatus.WARN
        except:
            import sys
            import traceback
            e = sys.exc_info()
            print(e[0], e[1], traceback.print_tb(e[2]))
            return rcStatus.WARN
        if last < now - delay:
            self.status_log("Last sync on %s older than %i minutes"%(last, self.sync_max_delay))
            return rcStatus.WARN
        return rcStatus.UP

    def check_remote(self, node):
        rs = self.get_remote_state(node)
        if self.snap1_uuid != rs['uuid']:
            self.log.error("%s last update uuid doesn't match snap1 uuid"%(node))
            raise ex.excError

    def get_remote_state(self, node):
        self.set_statefile()
        cmd1 = ['cat', self.statefile]
        cmd = rcEnv.rsh.split() + [node] + cmd1
        (ret, out, err) = self.call(cmd)
        if ret != 0:
            self.log.error("could not fetch %s last update uuid"%node)
            raise ex.excError
        return self.parse_statefile(out, node=node)

    def get_local_state(self):
        self.set_statefile()
        with open(self.statefile, 'r') as f:
            out = f.read()
        return self.parse_statefile(out)

    def get_snap_uuid(self, snap):
        self.init_src_btrfs()
        self.snap_uuid = self.src_btrfs.get_transid(snap)

    def set_statefile(self):
        self.statefile = os.path.join(rcEnv.pathvar,
                                      self.svc.svcname+'_'+self.rid+'_btrfs_state')

    def write_statefile(self):
        self.set_statefile()
        self.get_snap_uuid(self.src_snap_sent)
        self.log.info("update state file with snap uuid %s"%self.snap_uuid)
        with open(self.statefile, 'w') as f:
             f.write(str(datetime.datetime.now())+';'+self.snap_uuid+'\n')

    def _push_statefile(self, node):
        cmd = rcEnv.rcp.split() + [self.statefile, node+':'+self.statefile.replace('#', '\#')]
        ret, out, err = self.vcall(cmd)
        if ret != 0:
            raise ex.excError

    def push_statefile(self, node):
        self.set_statefile()
        self._push_statefile(node)
        self.get_peersenders()
        for s in self.peersenders:
            self._push_statefile(s)

    def parse_statefile(self, out, node=None):
        self.set_statefile()
        if node is None:
            node = rcEnv.nodename
        lines = out.strip().split('\n')
        if len(lines) != 1:
            self.log.error("%s:%s is corrupted"%(node, self.statefile))
            raise ex.excError
        fields = lines[0].split(';')
        if len(fields) != 2:
            self.log.error("%s:%s is corrupted"%(node, self.statefile))
            raise ex.excError
        return dict(date=fields[0], uuid=fields[1])

