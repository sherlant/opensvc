import sys
import os
import optparse
import string
import platform

#
# add project lib to path
#
prog = "svcmon"

import svcBuilder
import rcExceptions as ex
from rcUtilities import *
from lock import *
import node
from rcStatus import colorize

sysname, nodename, x, x, machine, x = platform.uname()

if sysname == "Windows":
    mp = False
else:
    try:
        from multiprocessing import Process, Queue, Lock
        mp = True
    except:
        mp = False

try:
    from version import version
except:
    version = "dev"

def max_len(svcs):
    _len = 7
    for svc in svcs:
        l = len(getattr(svc, "svcname"))
        if _len < l:
            _len = l
        for container in svc.get_resources('container'):
            l = len(getattr(container, "name")) + 2
            if _len < l:
                _len = l
    return _len

def svcmon_normal1(svc,upddb=False, fmt=None, queue=None, lock=None):
    # don't schedule svcmon updates for encap services.
    # those are triggered by the master node
    status = svc.group_status()
    l = []
    applen = 10
    app = str(svc.app)
    if len(app) > applen:
        app = app[:applen-1]+"*"
    data = [
              svc.svcname,
              app,
              svc.svctype,
              '-',
              "yes" if svc.frozen() else "no",
              "yes" if svc.disabled else "no",
              colorize(status["avail"]),
              colorize(status["overall"]),
    ]
    if options.verbose:
        data += [
              colorize(status["container"]),
              colorize(status["ip"]),
              colorize(status["disk"]),
              colorize(status["fs"]),
              colorize(status.get("share", "n/a")),
              colorize(status["app"]),
              colorize(status["hb"]),
              colorize(status["sync"]),
        ]
    buff = fmt % tuple(data)
    l.append(buff)
    containers = svc.get_resources("container")
    if len(containers) > 0 and svc.has_encap_resources:
        for container in containers:
            try:
                s = svc.encap_json_status(container)
            except ex.excNotAvailable as e:
                s = {'resources': [],
                     'ip': 'n/a',
                     'disk': 'n/a',
                     'sync': 'n/a',
                     'hb': 'n/a',
                     'container': 'n/a',
                     'fs': 'n/a',
                     'share': 'n/a',
                     'app': 'n/a',
                     'avail': 'n/a',
                     'overall': 'n/a'}

            data = [
                      ' @'+container.name,
                      '-',
                      '-',
                      container.type.replace('container.', ''),
                      '-',
                      '-',
                      colorize(s["avail"]),
                      colorize(s["overall"]),
            ]
            if options.verbose:
                data += [
                      colorize(s["container"]),
                      colorize(s["ip"]),
                      colorize(s["disk"]),
                      colorize(s["fs"]),
                      colorize(s.get("share", "n/a")),
                      colorize(s["app"]),
                      colorize(s["hb"]),
                      colorize(s["sync"]),
                ]
            buff = fmt % tuple(data)
            l.append(buff)

    if lock is not None:
        lock.acquire()
    print('\n'.join(l))
    if lock is not None:
        lock.release()

    if upddb:
        o = svc.svcmon_push_lists(status)
        _size = len(str(o))
        if queue is None or _size > 30000:
            # multiprocess Queue not supported, can't combine results
            g_vars, g_vals, r_vars, r_vals = svc.svcmon_push_lists(status)
            svc.node.collector.call('svcmon_update_combo', g_vars, g_vals, r_vars, r_vals)
        else:
            queue.put(svc.svcmon_push_lists(status))

def svcmon_normal(svcs, upddb=False):
    svcname_len = max_len(svcs)
    fmt = '%-' + str(svcname_len) + 's'
    if options.verbose:
        fmt += ' %-10s %-7s %-9s | %-6s %-8s | %-10s %-10s | %-10s %-10s %-10s %-10s %-10s %-10s %-10s %-10s'
        print(" "*svcname_len+" app        type    container | frozen disabled | avail      overall    | container  ip         disk       fs         share      app        hb         sync")
        print(" "*svcname_len+" -----------------------------+-----------------+-----------------------+----------------------------------------------------------------------------------")
    else:
        fmt += ' %-10s %-7s %-9s | %-6s %-8s | %-10s %-10s'
        print(" "*svcname_len+" app        type    container | frozen disabled | avail      overall    ")
        print(" "*svcname_len+" -----------------------------+-----------------+-----------------------")

    ps = []
    queues = {}
    try:
        lock = Lock()
    except:
        lock = None

    for svc in svcs:
        if svc.encap and upddb:
            continue
        if not mp:
            svcmon_normal1(svc, upddb, fmt, None)
            continue
        try:
            queues[svc.svcname] = Queue(maxsize=32000)
        except:
            # some platform don't support Queue's synchronize (bug 3770)
            queues[svc.svcname] = None
        p = Process(target=svcmon_normal1, args=(svc, upddb, fmt, queues[svc.svcname], lock))
        p.start()
        ps.append(p)
    for p in ps:
        p.join()

    if upddb and mp:
        g_vals = []
        r_vals = []
        if options.delay > 0:
            import random
            import time
            delay = int(random.random()*options.delay)
            time.sleep(delay)

        for svc in svcs:
            if svc.svcname not in queues or queues[svc.svcname] is None:
                continue
            if queues[svc.svcname].empty():
                continue
            g_vars, _g_vals, r_vars, _r_vals = queues[svc.svcname].get()
            g_vals.append(_g_vals)
            r_vals.append(_r_vals)
        if len(g_vals) > 0:
            svc.node.collector.call('svcmon_update_combo', g_vars, g_vals, r_vars, r_vals)

__ver = prog + " version " + version
__usage = prog + " [ OPTIONS ]\n"
parser = optparse.OptionParser(version=__ver, usage=__usage)
parser.add_option("--service", default="", action="store", dest="parm_svcs",
                  help="comma-separated list of service to display status of")
parser.add_option("--refresh", default=False, action="store_true", dest="refresh",
                  help="do not use resource status cache")
parser.add_option("--updatedb", default=False, action="store_true", dest="upddb",
                  help="update resource status in central database")
parser.add_option("--verbose", default=False, action="store_true", dest="verbose",
                  help="display resource groups status for each selected service")
parser.add_option("--maxdelaydb", default=0, action="store", type="int", dest="delay",
                  help="introduce a random delay before pushing to database to level the load on the collector")
parser.add_option("--debug", default=False, action="store_true", dest="debug",
                  help="debug mode")

(options, args) = parser.parse_args()

node = node.Node()

def main():
    if options.upddb:
        lockf = 'svcmon.lock'
        try:
            lockfd = monlock(fname=lockf)
        except ex.excError:
            return 1
        except:
            import traceback
            traceback.print_exc()
            return 1
 

    if len(options.parm_svcs) > 0:
        node.build_services(svcnames=options.parm_svcs.split(','))
    else:
        node.build_services()

    node.set_rlimit()

    for s in node.svcs:
        s.options.debug = options.debug
        s.options.refresh = options.upddb
        if options.refresh:
            s.options.refresh = options.refresh

    svcmon_normal(node.svcs, options.upddb)

    node.close()

    if options.upddb:
        try:
            monunlock(lockfd)
        except ex.excError:
            return 1
        except:
            import traceback
            traceback.print_exc()
            return 1

    return 0

if __name__ == "__main__":
    r = main()
    sys.exit(r)

