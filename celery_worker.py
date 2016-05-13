import pipes

from starcluster import threadpool
from starcluster.clustersetup import ClusterSetup
from starcluster.logger import log


class WorkerSetup(ClusterSetup):

    @property
    def pool(self):
        if not getattr(self, '_pool', None):
            self._pool = threadpool.get_thread_pool(size=20, disable_threads=False)
        return self._pool


class StartCeleryWorker(WorkerSetup):

    def __init__(
            self,
            git_sync_dir,
            worker_dir,
            kill_existing='True',
            delete_pyc_files='True',
            remount_dir='',
            queue='celery',
            celery_cmd='celery',
            concurrency='',
            app='',
            broker='',
            ld_library_path='/usr/local/lib',
            heartbeat_interval='5',
            gossip='False',
            maxtasksperchild='1024',
            Ofair='True',
            loglevel='info',
            user='ubuntu',
            tmux_history_limit='8000',
            worker_setup_cmd='',
            master_setup_cmd='',
            git_pull_cmd='git pull origin master',
            git_submodule_update_cmd='git submodule update --init --recursive',
            setup_docker='False',
    ):
        print 'StartCeleryWorker.__init__(%r)' % locals()

        self._user = user

        # error checking
        kill_existing = to_bool(kill_existing)
        delete_pyc_files = to_bool(delete_pyc_files)
        gossip = to_bool(gossip)
        Ofair = to_bool(Ofair)
        setup_docker = to_bool(setup_docker)

        # setup to be done as root
        root_init_cmd_list = []
        if setup_docker:
            root_init_cmd_list += ["groupadd -f docker"]
            root_init_cmd_list += ["adduser %s docker" % self._user]
        self._root_init_cmd = "; ".join(root_init_cmd_list)

        # build master sync command
        sync_cmd_list = []
        if remount_dir.strip():
            sync_cmd_list += ["sudo mount -o remount %s" % qd(remount_dir)]
        if git_sync_dir.strip():
            sync_cmd_list += ["cd %s" % qd(git_sync_dir)]
            if git_pull_cmd:
                sync_cmd_list += [git_pull_cmd]
            if git_submodule_update_cmd:
                sync_cmd_list += [git_submodule_update_cmd]
        if delete_pyc_files:
            sync_cmd_list += ["find %s -name '*.pyc' -delete" % qd(worker_dir)]
        if master_setup_cmd:
            sync_cmd_list += [master_setup_cmd]
        if sync_cmd_list:
            self._sync_cmd = "; ".join(sync_cmd_list)

        # build worker node command
        celery_args = [
            celery_cmd, 'worker',
            # the token 'PUBLIC_IP_ADDRESS' will get replaced with the actual
            # IP -- at this point, we don't know the IP.
            '--hostname', qs('%%h-PUBLIC_IP_ADDRESS-%s' % queue),
            '--queues', qs(queue),
        ]
        if app.strip():
            celery_args += ['--app', qs(app)]
        if broker.strip():
            celery_args += ['--broker', qs(broker)]
        if concurrency.strip():
            celery_args += ['--concurrency', int(concurrency)]
        if maxtasksperchild.strip():
            celery_args += ['--maxtasksperchild', int(maxtasksperchild)]
        if heartbeat_interval.strip():
            celery_args += ['--heartbeat-interval', int(heartbeat_interval)]
        if loglevel.strip():
            celery_args += ['--loglevel', qs(loglevel)]
        if not gossip:
            celery_args += ['--without-gossip']
        if Ofair:
            celery_args += ['-Ofair']

        # session_cmd: command that runs inside the tmux session
        session_cmd_list = [
            # (use double quotes so that bash expands $LD_LIBRARY_PATH)
            'export LD_LIBRARY_PATH="' + ld_library_path + ':$LD_LIBRARY_PATH"'
        ]
        if worker_setup_cmd:
            session_cmd_list += [worker_setup_cmd]
        session_cmd_list += [
            'cd %s' % qd(worker_dir),
            ' '.join(str(x) for x in celery_args),
        ]
        session_cmd = "; ".join(session_cmd_list)

        # build final start command
        tmux_session = "celery-" + queue
        start_cmd_list = []
        if kill_existing:
            start_cmd_list += ["tmux kill-session -t %s" % qs(tmux_session)]
        if remount_dir.strip() and kill_existing:
            start_cmd_list += ["sudo mount -o remount %s" % qd(remount_dir)]
        start_cmd_list += [
            "tmux new-session -s %s -d %s" % (qs(tmux_session), qs(session_cmd)),
            "tmux set-option -t %s history-limit %s" % (qs(tmux_session), int(tmux_history_limit)),
        ]
        self._start_cmd = "; ".join(start_cmd_list)

    def on_add_node(self, node, nodes, master, user, user_shell, volumes):
        print 'StartCeleryWorker.on_add_node(...)'
        if self._root_init_cmd:
            run_cmd(node, self._root_init_cmd, 'root')
        start_cmd = self._start_cmd.replace('PUBLIC_IP_ADDRESS', node.ip_address)
        run_cmd(node, start_cmd, self._user)

    def run(self, nodes, master, user, user_shell, volumes):
        print "StartCeleryWorker.run(%s, %s, %s, %s, %s)" % (nodes, master, user, user_shell, volumes)
        if self._sync_cmd:
            run_cmd(master, self._sync_cmd, self._user, silent=False)
        for node in nodes:
            if self._root_init_cmd:
                self.pool.simple_job(
                    run_cmd, args=(node, self._root_init_cmd, 'root'), jobid=node.alias)
            start_cmd = self._start_cmd.replace('PUBLIC_IP_ADDRESS', node.ip_address)
            self.pool.simple_job(
                run_cmd, args=(node, start_cmd, self._user), jobid=node.alias)
        self.pool.wait(len(nodes))


class KillCeleryWorker(WorkerSetup):

    def __init__(self, user='ubuntu', queue='celery'):
        tmux_session = "celery-" + queue
        self._user = user
        self._kill_cmd = "tmux kill-session -t '%s'" % tmux_session

    def run(self, nodes, master, user, user_shell, volumes):
        for node in nodes:
            self.pool.simple_job(
                run_cmd,
                args=(node, self._kill_cmd, self._user),
                jobid=node.alias,
            )
        self.pool.wait(len(nodes))


def to_bool(s):
    if s:
        s = s.strip()
        if s == 'True':
            return True
        elif s == 'False':
            return False
        else:
            raise ValueError("Expected True or False, got: '%s'" % s)
    return False


def qd(s):
    """ Quote a directory """
    if s is not None:
        s = str(s).strip()
        if s.startswith('~/') and '"' not in s and "'" not in s:
            return '"$HOME/%s"' % s[2:]
        else:
            return pipes.quote(s)
    else:
        return ''


def qs(s):
    """ Strip and quote-escape a string """
    if s is not None:
        s = str(s).strip()
        return pipes.quote(s)
    else:
        return ''


def run_cmd(node, cmd, user, silent=True):
    log.info("%s@%s: %s" % (user, node.alias, cmd))
    node.ssh.switch_user(user)
    node.ssh.execute(cmd, silent=silent)
    node.ssh.switch_user('root')
