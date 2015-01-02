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
            kill_existing=True,
            remount_dir=None,
            queue='celery',
            celery_cmd='celery',
            concurrency=None,
            app=None,
            broker=None,
            ld_library_path='/usr/local/lib',
            heartbeat_interval=5,
            maxtasksperchild=1,
            Ofair=True,
            loglevel='info',
            user='ubuntu',
            tmux_history_limit=8000,
            worker_setup_cmd=None,
            master_setup_cmd=None,
    ):

        self._user = user

        # build master sync command
        sync_cmd_list = []
        if git_sync_dir:
            if remount_dir:
                sync_cmd_list += ["sudo mount -o remount %s" % qd(remount_dir)]
            sync_cmd_list += [
                "cd %s" % qd(git_sync_dir),
                "git pull",
                "git submodule init",
                "git submodule update",
            ]
        if master_setup_cmd:
            sync_cmd_list += [master_setup_cmd]
        if sync_cmd_list:
            self._sync_cmd = "; ".join(sync_cmd_list)

        # build worker node command
        celery_args = [
            qs(celery_cmd), 'worker',
            '--hostname', qs('%%h-%s' % queue),
        ]
        if queue:
            celery_args += ['--queues', qs(queue)]
        if app:
            celery_args += ['--app', qs(app)]
        if broker:
            celery_args += ['--broker', qs(broker)]
        if maxtasksperchild:
            celery_args += ['--maxtasksperchild', qs(maxtasksperchild)]
        if concurrency:
            celery_args += ['--concurrency', qs(concurrency)]
        if loglevel:
            celery_args += ['--loglevel', qs(loglevel)]
        if heartbeat_interval:
            celery_args += ['--heartbeat-interval', qs(heartbeat_interval)]
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
            ' '.join(x for x in celery_args),
        ]
        # wait if there is an error
        session_cmd_list += ['read']
        session_cmd = "; ".join(session_cmd_list)

        # build final start command
        tmux_session = "celery-" + queue
        start_cmd_list = []
        if kill_existing:
            start_cmd_list += ["tmux kill-session -t %s" % qs(tmux_session)]
        if remount_dir and kill_existing:
            start_cmd_list += ["sudo mount -o remount %s" % qd(remount_dir)]
        start_cmd_list += [
            "tmux new-session -s %s -d %s" % (qs(tmux_session), qs(session_cmd)),
            "tmux set-option -t %s history-limit %s" % (qs(tmux_session), qs(tmux_history_limit)),
        ]
        self._start_cmd = "; ".join(start_cmd_list)

    def on_add_node(self, node, nodes, master, user, user_shell, volumes):
        run_cmd(node, self._start_cmd, self._user)

    def run(self, nodes, master, user, user_shell, volumes):
        if self._sync_cmd:
            run_cmd(master, self._sync_cmd, self._user, silent=False)
        for node in nodes:
            self.pool.simple_job(
                run_cmd, args=(node, self._start_cmd, self._user), jobid=node.alias)
        self.pool.wait(len(nodes))


class KillCeleryWorker(WorkerSetup):

    def __init__(self, user='ubuntu', queue='celery'):
        tmux_session = "celery-" + queue
        self._kill_cmd = "tmux kill-session -t '%s'" % tmux_session

    def run(self, nodes, master, user, user_shell, volumes):
        for node in nodes:
            self.pool.simple_job(
                run_cmd,
                args=(node, self._kill_cmd, self._user),
                jobid=node.alias,
            )
        self.pool.wait(len(nodes))


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
    if user != 'root':
        node.ssh.switch_user(user)
    node.ssh.execute(cmd, silent=silent)
    if user != 'root':
        node.ssh.switch_user('root')
