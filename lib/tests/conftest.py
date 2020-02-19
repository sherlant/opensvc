import sys
import os
from contextlib import contextmanager

sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__),
                                                 "..")))
import rcGlobalEnv  # nopep8
import pytest  # nopep8


@pytest.fixture(scope='function', name='osvc_path_tests')
def osvc_path_tests_fixture(tmpdir):
    test_dir = str(tmpdir)
    rcGlobalEnv.rcEnv.paths.pathetc = os.path.join(test_dir, 'etc')
    rcGlobalEnv.rcEnv.paths.pathetcns = os.path.join(test_dir, 'etc', 'namespaces')
    rcGlobalEnv.rcEnv.paths.pathlog = os.path.join(test_dir, 'log')
    rcGlobalEnv.rcEnv.paths.pathtmpv = os.path.join(test_dir, 'tmp')
    rcGlobalEnv.rcEnv.paths.pathvar = os.path.join(test_dir, 'var')
    rcGlobalEnv.rcEnv.paths.pathlock = os.path.join(test_dir, 'lock')
    rcGlobalEnv.rcEnv.paths.nodeconf = os.path.join(test_dir, 'etc', 'node.conf')
    rcGlobalEnv.rcEnv.paths.clusterconf = os.path.join(test_dir, 'etc', 'cluster.conf')
    rcGlobalEnv.rcEnv.paths.lsnruxsock = os.path.join(test_dir, 'var', 'lsnr', 'lsnr.sock')
    rcGlobalEnv.rcEnv.paths.lsnruxh2sock = os.path.join(test_dir, 'var', 'lsnr', 'h2.sock')
    rcGlobalEnv.rcEnv.paths.daemon_pid = os.path.join(test_dir, 'var', "osvcd.pid")
    rcGlobalEnv.rcEnv.paths.daemon_pid_args = os.path.join(test_dir, 'var', "osvcd.pid.args")
    os.makedirs(os.path.join(rcGlobalEnv.rcEnv.paths.pathvar, 'lsnr'))
    os.makedirs(os.path.join(rcGlobalEnv.rcEnv.paths.pathvar, 'node'))
    os.makedirs(rcGlobalEnv.rcEnv.paths.pathtmpv)
    os.makedirs(rcGlobalEnv.rcEnv.paths.pathlog)
    return tmpdir


@pytest.fixture(scope='function')
def mock_argv(mocker):
    def func(argv):
        mocker.patch.object(sys, 'argv', argv)

    return func


@pytest.fixture(scope='function')
def non_existing_file(tmp_path):
    assert os.path.exists(str(tmp_path))
    return os.path.join(str(tmp_path), 'foo')


@pytest.fixture(scope='function')
def tmp_file(tmp_path):
    return os.path.join(str(tmp_path), 'tmp-file')


@pytest.fixture(scope='function')
def capture_stdout():
    @contextmanager
    def func(filename):
        _stdout = sys.stdout
        try:
            with open(filename, 'w') as output_file:
                sys.stdout = output_file
                yield
        finally:
            sys.stdout = _stdout
    return func


@pytest.fixture(scope='function', name='mock_sysname')
def mock_sysname_fixture(mocker):
    def func(sysname):
        mocker.patch.object(rcGlobalEnv.rcEnv, 'sysname', sysname)

    return func


@pytest.fixture(scope='function')
def has_node_config(osvc_path_tests):

    pathetc = rcGlobalEnv.rcEnv.paths.pathetc
    os.mkdir(pathetc)
    with open(os.path.join(pathetc, 'node.conf'), mode='w+') as node_config_file:
        """This fixture set non default port and tls_port for listener.
        This avoid port conflict with live daemon.
        """
        config_txt = """[DEFAULT]
id = nodeuuid

[listener]
port = 1224
tls_port = 1225
"""
        node_config_file.write(config_txt)


@pytest.fixture(scope='function')
def has_service_lvm(osvc_path_tests, mock_sysname):
    mock_sysname('Linux')
    pathetc = rcGlobalEnv.rcEnv.paths.pathetc
    os.mkdir(pathetc)
    with open(os.path.join(pathetc, 'svc.conf'), mode='w+') as svc_file:
        config_txt = """
[DEFAULT]
id = abcd

[disk#simple]
type = lvm
vgname = vgname1

[disk#optional]
type = lvm
vgname = vgname1
optional = true

[disk#scsireserv]
type = lvm
vgname = vgname1
scsireserv = true

[disk#scsireserv-optional]
type = lvm
vgname = vgname1
scsireserv = true
optional = true
"""
        svc_file.write(config_txt)


@pytest.fixture(scope='function')
def has_service_with_fs_flag(osvc_path_tests):
    pathetc = rcGlobalEnv.rcEnv.paths.pathetc
    os.mkdir(pathetc)
    with open(os.path.join(pathetc, 'svc.conf'), mode='w+') as svc_file:
        config_txt = """
[DEFAULT]
id = abcd

[fs#flag1]
type = flag
"""
        svc_file.write(config_txt)
