import provisioning
import rcExceptions as ex

class Prov(provisioning.Prov):
    def __init__(self, r):
        provisioning.Prov.__init__(self, r)

    def is_provisioned(self):
        return self.r.has_it()

    def unprovisioner(self):
        cmd = ["zpool", "destroy", "-f", self.r.name]
        self.r.vcall(cmd)

    def provisioner(self):
        try:
            self.name = self.r.name
            self.vdev = self.r.svc.conf_get(self.r.rid, "vdev")
        except Exception as e:
            raise ex.excError(str(e))

        cmd = ["zpool", "create", "-m", "legacy", self.name] + self.vdev
        self.r.vcall(cmd)

