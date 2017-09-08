"""
Define the Freezer class, instanciated as a Svc lazy attribute,
providing the methods to freeze, thaw a service and to test if
a service is frozen.
"""
import os
from rcGlobalEnv import rcEnv

class Freezer(object):
    """
    The freezer class, instanciated as a Svc lazy attribute.
    Provides methods to freeze, thaw a service and to test if
    the service is frozen.
    """
    flag_dir = rcEnv.paths.pathvar
    base_flag = os.path.join(flag_dir, 'FROZEN')
    flag = base_flag

    @staticmethod
    def _dummy():
        """
        A no-op method to replace freeze/thaw/frozen when the service
        configuration file does not exist.
        """
        pass

    def _frozen(self, strict=False):
        """
        Return True if the service frozen file flag is present.
        """
        if os.path.exists(self.flag):
            return True
        if not strict and os.path.exists(self.base_flag):
            return True
        return False

    def _freeze(self):
        """
        Create the service frozen file flag.
        """
        open(self.flag, 'w').close()

    def _thaw(self):
        """
        Remove the service frozen file flag.
        """
        if self.flag != self.base_flag and os.path.exists(self.flag):
            os.unlink(self.flag)

    def node_frozen(self):
        """
        Return True if the node frozen file flag is present.
        """
        if os.path.exists(self.base_flag):
            return True
        return False

    def node_freeze(self):
        """
        Create the node frozen file flag.
        """
        if os.path.exists(self.base_flag):
            return
        open(self.base_flag, 'w').close()

    def node_thaw(self):
        """
        Remove the node frozen file flag.
        """
        if not os.path.exists(self.base_flag):
            return
        os.unlink(self.base_flag)

    def __init__(self, name):
        self.flag = self.flag + "." + name
        if not os.path.exists(os.path.join(rcEnv.paths.pathetc, name)):
            self.freeze = self._dummy
            self.thaw = self._dummy
            self.frozen = self._dummy
        else:
            self.freeze = self._freeze
            self.thaw = self._thaw
            self.frozen = self._frozen
