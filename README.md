starcluster-plugins
===================

My plugins for starcluster.

### Typical usage:
Add this to your `~/.starcluster/config` file:
<pre>
[plugin start_celery_worker]
setup_class = celery_worker.StartCeleryWorker

# The base of the git code repository that the workers use.  The repo and all
# submodules will be updated.
git_sync_dir = ~/repo

# the directory where the celery worker will run
worker_dir = ~/repo/code

# location of the celery package (used by the -A argument for celery)
app = my.celery.app

# name of the celery queue (celery is the default queue name)
queue = celery

# number of worker processes to run (or None to run all processes)
concurrency = None

[plugin kill_celery_worker]
setup_class = celery_worker.KillCeleryWorker
queue = celery
</pre>

Note that you can have multiple plugins with different names (e.g.
`[plugin start_gpu_celery_worker]`, `[plugin start_cpu_celery_worker']).

### Other options for start_celery_worker:
<pre>
# use a different command to start celery, such as with a venv (with respect to
# the path worker_dir)
celery_cmd='../venv/bin/celery'

# remount the base directory of the NFS filesystem, to be remounted before
# any code is run (this helps ensure it is up to date)
remount_dir = /home

# use a different broker than the one specified in your config
broker=None,

# Add extra paths to LD_LIBRARY_PATH for the worker
ld_library_paths=['/usr/local/lib'],

# Use a different heartbeat (in seconds)
heartbeat_interval=5,

# Restart the workers after a different number of tasks (change to be higher if
# you have lots of little tasks)
maxtasksperchild=1,

# Whether to include -Ofair (I find that it helps increase worker utilization).
Ofair=True,

# Different log level
loglevel='info',
</pre>
