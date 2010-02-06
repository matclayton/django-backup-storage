from django.core.files.storage import get_storage_class, Storage
 
from backup_storage.tasks import CopyToStorage
from django.utils.encoding import force_unicode

import os
  
class QueuedBackupStorage(Storage):
    def __init__(self, local, remote):
        self.local_class = local
        self.local = get_storage_class(self.local_class)()
        self.remote_class = remote
        self.remote = get_storage_class(self.remote_class)()
    
    def open(self, name, **kwargs):
        return self.local.open(name, **kwargs)   
        
    def save(self, name, content):
        """
        Saves new content to the file specified by name. The content should be a
        proper File object, ready to be read from the beginning.
        """
        # Get the proper name for the file, as it will actually be saved.
        if name is None:
            name = content.name

        name = self.get_available_name(name)
        # Save to local file storage system
        name = self.local._save(name, content)
        # Add to Queue to push to remote file system
        CopyToStorage.delay(name, self.local_class, self.remote_class)

        # Store filenames with forward slashes, even on Windows
        return force_unicode(name.replace('\\', '/'))
    
    def get_valid_name(self, name):
        return self.local.get_valid_name(name)  
    
    def get_available_name(self, name):
        """
        Returns a filename that's free on both target storage systems, and
        available for new content to be written to.
        """
        dir_name, file_name = os.path.split(name)
        file_root, file_ext = os.path.splitext(file_name)
        # If the filename already exists, keep adding an underscore (before the
        # file extension, if one exists) to the filename until the generated
        # filename doesn't exist.
        while self.exists(name):
            file_root += '_'
            # file_ext includes the dot.
            name = os.path.join(dir_name, file_root + file_ext)
        return name 
    
    def path(self, name):
        return self.local.path(name)
    
    def delete(self, name):
        self.local.delete(name)
        self.remote.delete(name)
    
    def exists(self, name):
        return (self.local.exists(name) or self.remote.exists(name))
    
    def listdir(self, name):
        return self.local.listdir(name)
    
    def size(self, name):
        return self.local.size(name) if self.local.exists(name) else self.remote.size(name)
    
    def url(self, name):
        return self.local.url(name) if self.local.exists(name) else self.remote.url(name)