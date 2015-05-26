from django.core.files.storage import get_storage_class
from django.core.cache import cache

from celery.registry import tasks
from celery.task import Task

LOCK_EXPIRE = 60 * 30 # Lock expires in 30 minutes

class CopyToStorage(Task):
    name = "backup_storage.copy"
    ignore_result = True
    default_retry_delay = 3600
    max_retries = 5

    def run(self, file_name, source, target, **kwargs):
        if not file_name:
	    return

        logger = self.get_logger(**kwargs)

        source_storage = get_storage_class(source)()
        target_storage = get_storage_class(target)()

        lock_id = "%s-lock-%s" % (self.name, hash(file_name))

        is_locked = lambda: str(cache.get(lock_id)) == "true"
        acquire_lock = lambda: cache.set(lock_id, "true", LOCK_EXPIRE)
        # memcache delete is very slow, so we'd rather set a false value
        # with a very low expiry time.
        release_lock = lambda: cache.set(lock_id, "nil", 1)

        logger.debug("Copying %s source:%s target:%s" % (file_name,source,target))
        if is_locked():
            logger.debug("%s is already being copied by another worker" % file_name)
            return

        acquire_lock()
        try:
            if file_name and not target_storage.exists(file_name):
                target_storage.save(file_name, source_storage.open(file_name))
        finally:
            release_lock()

tasks.register(CopyToStorage)