StartCeleryWorker
=================

A plugin to start celery workers on every node of a StarCluster cluster.

Each celery worker is contained in a tmux session, so you don't need to worry
about log files taking up too much disk space.  Each worker logs to the screen
on its local tmux session.  Using tmux sessions makes it easier to reliably
kill celery workers.  The tmux session is named `"celery-" + queue`.

### Installation
1. Check out this repository.
2. Add a symlink to `celery_worker.py` in `~/.starcluster/plugins/`.
3. Configure the plugin in `~/.starcluster/config` (see below).

### Typical configuration:
Add this to your `~/.starcluster/config` file:
<pre>
[plugin start_celery_worker]
setup_class = celery_worker.StartCeleryWorker

# The base of the git code repository that the workers use.  The repo and all
# submodules will be updated via "git pull; git submodule init; git submodule
# update".
git_sync_dir = ~/repo

# Directory where the celery worker will run
worker_dir = ~/repo/code

# Python package containing the celery app (used by the -A argument for celery)
app = my.celery.app

# Name of the celery queue (default: celery).  You can specify multiple queues
# as a comma-separated list (e.g. queue = video,image).
queue = celery

# Number of worker processes to run (leave blank or omit to use all processes)
concurrency =

# If True, kill existing workers before starting.  If set to False, existing workers
# will continue running and duplicate start commands will have no effect.
kill_existing = True

[plugin kill_celery_worker]
setup_class = celery_worker.KillCeleryWorker
queue = celery
</pre>

Note that you can have multiple plugins with different names (e.g.
`[plugin start_gpu_celery_worker]`, `[plugin start_cpu_celery_worker']`).

When you start a new cluster or add a new node, workers will automatically be
started if you add the "start" version of the plugin to your `PLUGINS` list
(you should not add the "kill" version).  Note that if you change the
configuration after starting the cluster, new nodes will still be added with
the old configuration.  If someone knows how to fix this, please let me know!

### Command line

##### Start/restart your workers:
<pre>
starcluster runplugin start_celery_worker cluster_name
</pre>
If the workers are already started, running start again will re-sync the code,
kill them, and then start them again.

##### Kill your workers:
<pre>
starcluster runplugin kill_celery_worker cluster_name
</pre>

##### View the log on a worker:

Print a capture of the tmux pane (assuming user `ubuntu`):
<pre>
starcluster sshnode -u ubuntu cluster_name node001 "tmux capture-pane -p -S '-100' -t celery-queue"
</pre>
Replace `queue` with your queue name.  The argument `-S '-100'` gives an extra 100 lines of history.

Or log in and attach to the pane:
<pre>
starcluster sshnode -u ubuntu cluster_name node001
tmux attach -t celery-queue
</pre>


### Other options for start_celery_worker:
Include these under `[plugin start_gpu_celery_worker]`:
<pre>
# Clear out `*.pyc` files before starting the worker (default True)
delete_pyc_files = True

# Run a command (inside each worker tmux session) before the celery worker starts
# (e.g. to download a data file to local instance storage inside /mnt/ubuntu)
worker_setup_cmd = cd /mnt/ubuntu; f=file.npy; wget http://example.com/$f -O $f

# Run a command on the master once at the beginning
# (e.g. to pull and compile code)
master_setup_cmd = cd ~/caffe; git pull origin dev; make clean; make all; make pycaffe

# Use a different command to start celery, such as with a venv (with respect to
# the path worker_dir)
celery_cmd = ../venv/bin/celery

# Remount the base directory of the NFS filesystem, to be remounted before
# any code is run (this helps ensure it is up to date).
# NOTE: This is ignored if kill_existing is not True.
remount_dir = /home

# Use a different broker than the one specified in your config
broker = amqp://guest@localhost//

# Add extra paths to LD_LIBRARY_PATH for the worker
ld_library_paths = /usr/local/lib:/some/other/path

# Use a different heartbeat (in seconds)
heartbeat_interval = 5

# Restart the workers after a different number of tasks (change to be higher if
# you have lots of little tasks)
maxtasksperchild = 1

# Whether to include -Ofair (I find that it helps increase worker utilization).
Ofair = True

# Celery log level
loglevel = info

# Run as a different user (make sure you add this line to the KillCeleryWorker
# plugin as well)
user = ubuntu

# Tmux buffer size (increase to store more of the recent log output)
tmux_history_limit = 10000
</pre>
