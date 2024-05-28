import asyncio
from watchdog.events import FileSystemEventHandler


class FileSystemHandler(FileSystemEventHandler):
    def __init__(self, filesystem,opcua_server):
        super().__init__()
        self.filesystem = filesystem
        self.server = opcua_server

    def on_created(self, event):
        asyncio.run_coroutine_threadsafe(
            self.filesystem.update_filesystem(event.src_path, 'created'),
            self.server.loop
        )

    def on_deleted(self, event):
        asyncio.run_coroutine_threadsafe(
            self.filesystem.update_filesystem(event.src_path, 'deleted'),
            self.server.loop
        )

    def on_modified(self, event):
        asyncio.run_coroutine_threadsafe(
            self.filesystem.update_filesystem(event.src_path, 'modified'),
            self.server.loop
        )

    def on_moved(self, event):
        asyncio.run_coroutine_threadsafe(
            self.filesystem.update_filesystem(event.dest_path, 'moved'),
            self.server.loop
        )
