import fcntl
import os
import time
import rcExceptions as ex
from rcGlobalEnv import rcEnv

def svclock(svc, timeout=30, delay=5):
    for i in range(timeout//delay):
        try:
            svclock_nowait(svc)
            return
        except ex.excError:
            time.sleep(delay)
    svc.log.error("timed out waiting for lock")
    raise ex.excError
    
def svclock_nowait(svc):
    lock = os.path.join(rcEnv.pathlock, svc.svcname)
    pid = 0

    if not os.path.exists(rcEnv.pathlock):
        os.makedirs(rcEnv.pathlock)
    else:
        try:
            with open(lock, 'r') as fd:
	        pid = int(fd.read())
                fd.close()
        except:
            pass

    try:
        svc.lockfd = os.open(lock, os.O_RDWR|os.O_SYNC|os.O_CREAT|os.O_TRUNC, 0644)
    except:
        svc.log.error("can not create lock file %s"%lock)
        raise

    try:
        """ test if we already own the lock
        """
        if pid == os.getpid():
            return

        """ FD_CLOEXEC makes sure the lock is the held by processes
            we fork from this process
        """
        fcntl.flock(svc.lockfd, fcntl.LOCK_EX|fcntl.LOCK_NB)
        flags = fcntl.fcntl(svc.lockfd, fcntl.F_GETFD)
        flags |= fcntl.FD_CLOEXEC

        """ acquire lock
        """
        fcntl.fcntl(svc.lockfd, fcntl.F_SETFD, flags)

        """ drop our pid in the lockfile
        """
        os.write(svc.lockfd, str(os.getpid()))
        os.fsync(svc.lockfd)
    except IOError:
        svc.log.warn("another action is currently running (pid=%s)"%pid)
        raise ex.excError
    except:
        raise

def svcunlock(svc):
    os.close(svc.lockfd)
