from rcUtilities import justcall
import rcExceptions as ex
import snap
from rcZfs import dataset_exists

class Snap(snap.Snap):
    """Defines a snap object with ZFS
    """

    def snapcreate(self, m):
        """ create a snapshot for m
        add self.snaps[m] with
            dict(snapinfo key val)
        """
        dataset = m.device
        if not dataset_exists(dataset, 'filesystem'):
            raise ex.syncNotSnapable
        snapdev = dataset +'@osvc_sync'
        mountPoint = m.mountPoint
        snapMountPoint= mountPoint + '/.zfs/snapshot/osvc_sync/'
        if dataset_exists(snapdev, 'snapshot'):
            (ret, buff, err) = self.vcall(['zfs', 'destroy', snapdev ])
            if ret != 0:
                raise ex.syncSnapDestroyError
        (ret, buff, err) = self.vcall(['zfs', 'snapshot', snapdev ])
        if ret != 0:
            raise ex.syncSnapCreateError
        self.snaps[mountPoint]={'snap_mnt' : snapMountPoint, \
                                'snapdev' : snapdev }

    def snapdestroykey(self, snap_key):
        """ destroy a snapshot for a mountPoint
        """
        snapdev = self.snaps[snap_key]['snapdev']
        if not dataset_exists(snapdev, 'snapshot'):
            return
        (ret, buff, err) = self.vcall(['zfs', 'destroy', snapdev ])
        if ret != 0:
            raise ex.syncSnapDestroyError
