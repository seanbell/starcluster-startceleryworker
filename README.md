starcluster-plugins
===================

My plugins for starcluster.

Example usage:
<pre>
[plugin start_gpu_celery_worker]
setup_class = celery_worker.StartCeleryWorker
celery_cmd = ../venv/bin/celery
code_dir = ~/styledb
worker_dir = ~/styledb/server
remount_dir = /home
package = styledb
queue = styledb_gpu
concurrency = 8

[plugin kill_gpu_celery_worker]
setup_class = celery_worker.KillCeleryWorker
queue = styledb_gpu
</pre>
