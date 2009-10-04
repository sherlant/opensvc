import optparse
from rcGlobalEnv import *

action_desc = {
	'start':	'start a service, chaining startip-mount-startapp',
	'startip':	'configure service ip adresses',
	'mount':	'prepare devices, logical volumes, mount service filesystems, bootstrap containers',
	'mountnfs':	'mount nfs associated with the service',
	'startapp':	'execute service application startup script',
	'stop':		'stop a service, chaining stopapp-umount-stopip',
	'stopip':	'unconfigure service ip adresses',
	'umount':	'shutdown container, umount service filesystems, deactivate logical volumes',
	'umountnfs':	'umount nfs associated with the service',
	'stopapp':	'execute service application stop script',
	'syncnodes':	'send to peer nodes the service config files and additional files described in the config file',
	'syncdrp':	'send to drp nodes the service config files and additional files described in the config file',
	'configure':	'configure a service container, using configuration file information',
	'create':	'create a new service configuration file',
	'startlxc':	'start a LinuX Container',
	'stoplxc':	'stop a LinuX Container',
	'status':	'display service resource status',
	'freeze':	'set up a flag to block actions on this service',
	'thaw':		'remove the flag to unblock actions on this service',
	'frozen':	'report on the current blocking of actions on this service',
}

def format_desc(svc=False):
	desc = "Commands available to this service:\n"
	for a in action_desc.keys():
		if svc and not hasattr(svc, a):
			continue
		desc += "  {0:13s}{1:65s}\n".format(a, action_desc[a])
	return desc

class svcOptionParser:
	def __init__(self, svc=False):
		__ver = rcEnv.prog + " version " + str(rcEnv.ver)
		__usage = "%prog [options] command\n\n" + format_desc(svc)
		parser = optparse.OptionParser(version=__ver, usage=__usage)
		parser.add_option("--debug", default="False",
				  action="store_true", dest="debug",
				  help="debug mode")
		parser.add_option("-f", "--force", default="False",
				  action="store_true", dest="force",
				  help="force action, ignore sanity check warnings")
		(self.options, self.args) = parser.parse_args()
		if len(self.args) > 1:
			parser.error("More than one action")
		if len(self.args) is 0:
			parser.error("Missing action")
		self.action = self.args[0]
		if svc and not hasattr(svc, self.action):
			parser.error("unsupported action")
	def show(self):
		print ":: option parser dump"
		print "{0:15s}{1:15s}".format('debug', str(self.options.debug))
		print "{0:15s}{1:15s}".format('force', str(self.options.force))
		print "{0:15s}{1:15s}".format('action', self.action)
