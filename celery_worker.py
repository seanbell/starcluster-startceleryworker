from starcluster.clustersetup import ClusterSetup
from starcluster.logger import log
from starcluster import threadpool


def run_cmd(node, cmd, user='ubuntu', silent=True):
    log.info("%s@%s: %s" % (user, node.alias, cmd))
    if user != 'root':
        node.ssh.switch_user(user)
    node.ssh.execute(cmd, silent=silent)
    if user != 'root':
        node.ssh.switch_user('root')


class WorkerSetup(ClusterSetup):

    @property
    def pool(self):
        if not getattr(self, '_pool', None):
            self._pool = threadpool.get_thread_pool(size=20, disable_threads=False)
        return self._pool


class StartCeleryWorker(WorkerSetup):

    def __init__(self, code_dir, worker_dir, package, queue, concurrency,
                 celery_cmd='celery', remount_dir=None,
                 ld_library_path='/usr/local/lib'):

        if int(concurrency) > 0:
            concurrency_opt = "--concurrency=%s" % concurrency
        else:
            concurrency_opt = ""

        session = "celery-%s" % queue
        node_name = "$(hostname)-%s" % queue
        celery_cmd = "; ".join([
            "export LD_LIBRARY_PATH=ld_library_path:$LD_LIBRARY_PATH",
            "cd %s" % worker_dir,
            "%s worker -A %s -Q %s -l info --maxtasksperchild=1 -Ofair --heartbeat-interval=60 %s -n %s" % (
                celery_cmd, package, queue, concurrency_opt, node_name),
        ])
        self._sync_cmd = "; ".join([
            "sudo mount -o remount '%s'" % remount_dir if remount_dir else "echo 'no remount'",
            "cd %s" % code_dir,
            "git pull",
            "git submodule init",
            "git submodule update",
        ])
        self._start_cmd = "; ".join([
            "tmux kill-session -t %s" % session,
            "sudo mount -o remount '%s'" % remount_dir if remount_dir else "echo 'no remount'",
            "tmux new-session -s %s -d '%s'" % (session, celery_cmd),
        ])

    def on_add_node(self, node, nodes, master, user, user_shell, volumes):
        run_cmd(node, self._start_cmd)

    def run(self, nodes, master, user, user_shell, volumes):
        run_cmd(master, self._sync_cmd, silent=False)
        for node in nodes:
            self.pool.simple_job(
                run_cmd, args=(node, self._start_cmd), jobid=node.alias)
        self.pool.wait(len(nodes))


class KillCeleryWorker(WorkerSetup):

    def __init__(self, queue):
        session = "celery-%s" % queue
        self._kill_cmd = "tmux kill-session -t %s" % session

    def run(self, nodes, master, user, user_shell, volumes):
        for node in nodes:
            self.pool.simple_job(
                run_cmd, args=(node, self._kill_cmd), jobid=node.alias)
        self.pool.wait(len(nodes))
