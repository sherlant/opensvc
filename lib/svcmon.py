from __future__ import print_function
import os
import sys
import optparse
import time
import datetime
import socket
import threading

#
# add project lib to path
#
prog = "svcmon"

import rcExceptions as ex
import rcColor
from node import Node
from fmt_cluster import format_cluster

CLEAREOL = "\x1b[K"
CLEAREOLNEW = "\x1b[K\n"
CLEAREOS = "\x1b[J"
CURSORHOME = "\x1b[H"

EVENT = threading.Event()

def setup_parser(node):
    __ver = prog + " version " + node.agent_version
    __usage = prog + \
        " [ OPTIONS ]\n" \
        "\n" \
        "Flags:\n" \
        "  O  up\n" \
        "  o  stdby up\n" \
        "  X  down\n" \
        "  x  stdby down\n" \
        "  !  warn\n" \
        "  P  unprovisioned\n" \
        "  *  frozen\n" \
        "  ^  leader node or service placement non-optimal"
    parser = optparse.OptionParser(version=__ver, usage=__usage)
    parser.add_option("--color", default="auto",
                      action="store", dest="color",
                      help="colorize output. possible values are : auto=guess based "
                           "on tty presence, always|yes=always colorize, never|no="
                           "never colorize")
    parser.add_option("--node", action="store", dest="node",
                      help="The node to send a request to. If not specified the "
                           "local node is targeted."),
    parser.add_option("--namespace", action="store", dest="namespace",
                      help="The namespace to switch to for the action. "
                           "Namespaces are cluster partitions. A default "
                           "namespace can be set for the session setting the "
                           "OSVC_NAMESPACE environment variable."),
    parser.add_option("--stats", default=False,
                      action="store_true", dest="stats",
                      help="refresh the information every --interval.")
    parser.add_option("-w", "--watch", default=False,
                      action="store_true", dest="watch",
                      help="refresh the information every --interval.")
    parser.add_option("-i", "--interval", default=0, action="store",
                      dest="interval", type="int",
                      help="with --watch, set the refresh interval. defaults "
                           "to 0, to refresh on event only.")
    parser.add_option("--sections", action="store",
                      dest="sections",
                      help="the comma-separated list of sections to display. "
                           "if not set, all sections are displayed. sections "
                           "names are: threads,arbitrators,nodes,services.")

    parser.add_option(
        "-s", "--service", default=None,
        action="store", dest="parm_svcs",
        help="A service selector expression ``[!]<expr>[<sep>[!]<expr>]`` where:\n\n"
             "- ``!`` is the expression negation operator\n\n"
             "- ``<sep>`` can be:\n\n"
             "  - ``,`` OR expressions\n\n"
             "  - ``+`` AND expressions\n\n"
             "- ``<expr>`` can be:\n\n"
             "  - a shell glob on service names\n\n"
             "  - ``<param><op><value>`` where:\n\n"
             "    - ``<param>`` can be:\n\n"
             "      - ``<rid>:``\n\n"
             "      - ``<group>:``\n\n"
             "      - ``<rid>.<key>``\n\n"
             "      - ``<group>.<key>``\n\n"
             "    - ``<op>`` can be:\n\n"
             "      - ``<``  ``>``  ``<=``  ``>=``  ``=``\n\n"
             "      - ``~`` with regexp value\n\n"
             "Examples:\n\n"
             "- ``*dns,ha*+app.timeout>1``\n\n"
             "- ``ip:+task:``\n\n"
             "- ``!*excluded``\n\n"
             "Note:\n\n"
             "- ``!`` usage requires single quoting the expression to prevent "
             "shell history expansion")
    return parser

def events(node, nodename):
    for msg in node.daemon_events(nodename):
        EVENT.set()

def start_events_thread(node, nodename):
    thr = threading.Thread(target=events, args=(node, nodename,))
    thr.daemon = True
    thr.start()
    return thr

def get_stats(options, node, svcpaths):
    try:
        if options.stats:
            return node._daemon_stats(svcpaths=svcpaths, node=options.node)
        else:
            return None
    except Exception:
        return None

def nodes_info_from_cluster_data(data):
    info = {}
    for node in data.get("cluster", {}).get("nodes", []):
        info[node] = {}
    for node, _data in data.get("monitor", {}).get("nodes", {}).items():
        info[node] = {
            "labels": _data.get("labels", {}),
            "targets": _data.get("targets", {}),
        }
    return info

def _main(node, argv=None):
    parser = setup_parser(node)
    (options, args) = parser.parse_args(argv)
    node.check_privs(argv)
    svcmon(node, options)

def svcmon(node, options=None):
    rcColor.use_color = options.color
    if not options.node:
        options.node = "*"
    chars = 0
    last_refresh = 0

    namespace = options.namespace if options.namespace else os.environ.get("OSVC_NAMESPACE")

    if options.stats and not options.interval:
        options.interval = 3
    if options.interval:
        options.watch = True
    endpoint = socket.gethostname().lower()
    nodes = []
    if "OSVC_CONTEXT" in os.environ:
        endpoint = None
    elif options.node is not None:
        nodes = node.nodes_selector(options.node)
        if nodes and endpoint not in nodes:
            endpoint = nodes[0]

    node.options.update({
        "color": options.color,
    })

    status_data = node._daemon_status(node=endpoint)
    if status_data is None or status_data.get("status", 0) != 0:
        raise ex.excError
    nodes_info = nodes_info_from_cluster_data(status_data)
    expanded_svcs = node.svcs_selector(options.parm_svcs, namespace=namespace, data=status_data)
    if not nodes:
        nodes = node.nodes_selector(options.node, data=nodes_info)

    if options.watch:
        start_events_thread(node, endpoint)
        preamble = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        stats_data = get_stats(options, node, expanded_svcs)
        prev_stats_data = None
        outs = format_cluster(svcpaths=expanded_svcs, node=nodes,
                              data=status_data, sections=options.sections,
                              selector=options.parm_svcs,
                              namespace=namespace)

        if outs is not None:
            print(CURSORHOME+preamble+CLEAREOLNEW+CLEAREOL)
            print(CLEAREOLNEW.join(outs.split("\n"))+CLEAREOS)

        while True:
            now = time.time()
            try:
                EVENT.wait(0.5)
            except Exception:
                break
            stats_changed = options.interval and now - last_refresh >= options.interval
            status_changed = bool(EVENT.is_set())
            EVENT.clear()
            if not status_changed and not stats_changed:
                continue
            if status_changed:
                try:
                    status_data = node._daemon_status(node=endpoint)
                except Exception:
                    # seen on solaris under high load: decode_msg() raising on invalid json
                    continue
                if status_data is None:
                    # can happen when the secret is being reset on daemon join
                    continue
                expanded_svcs = node.svcs_selector(options.parm_svcs, namespace=namespace, data=status_data)
                nodes_info = nodes_info_from_cluster_data(status_data)
                nodes = node.nodes_selector(options.node, data=nodes_info)
            if stats_changed:
                prev_stats_data = stats_data
                stats_data = get_stats(options, node, expanded_svcs)
            if chars == 0:
                print(CURSORHOME+CLEAREOS)
                chars = 1
            preamble = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            outs = format_cluster(
                svcpaths=expanded_svcs,
                node=nodes,
                data=status_data,
                prev_stats_data=prev_stats_data,
                stats_data=stats_data,
                sections=options.sections,
                selector=options.parm_svcs,
                namespace=namespace,
            )
            if outs is not None:
                print(CURSORHOME+preamble+CLEAREOLNEW+CLEAREOL)
                print(CLEAREOLNEW.join(outs.split("\n"))+CLEAREOS)
                pass
            # min delay
            last_refresh = now
            time.sleep(0.2)
    else:
        outs = format_cluster(svcpaths=expanded_svcs, node=nodes,
                              data=status_data, sections=options.sections,
                              selector=options.parm_svcs,
                              namespace=namespace)
        if outs is not None:
            print(outs)


def main(argv=None):
    if argv is None:
        argv = sys.argv
    else:
        argv.insert(0, __file__)

    try:
        node = Node()
    except Exception as exc:
        print(exc, file=sys.stderr)
        return 1

    try:
        _main(node, argv)
        return 0
    except ex.excError as e:
        if str(e):
            print(e, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        sys.stderr.write("Keybord Interrupt\n")
        return 1
    finally:
        node.close()

    return 0

if __name__ == "__main__":
    ret = main()
    sys.exit(ret)

