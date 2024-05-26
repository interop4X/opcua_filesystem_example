import asyncio
import os
from asyncua import ua, Server
from asyncua.common.instantiate_util import instantiate
from asyncua.common.node import Node
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Konfigurationsordner, der als Root für das OPC UA File System dient
ROOT_DIR = "root"


class FileSystemHandler(FileSystemEventHandler):
    def __init__(self, server):
        super().__init__()
        self.server = server

    def on_created(self, event):
        asyncio.run_coroutine_threadsafe(self.server.update_filesystem(
            event.src_path, 'created'), self.server.loop)

    def on_deleted(self, event):
        asyncio.run_coroutine_threadsafe(self.server.update_filesystem(
            event.src_path, 'deleted'), self.server.loop)

    def on_modified(self, event):
        asyncio.run_coroutine_threadsafe(self.server.update_filesystem(
            event.src_path, 'modified'), self.server.loop)

    def on_moved(self, event):
        asyncio.run_coroutine_threadsafe(self.server.update_filesystem(
            event.dest_path, 'moved'), self.server.loop)


class OPCUAFileSystemServer:
    def __init__(self, endpoint):
        self.server = Server()
        self.server.set_endpoint(endpoint)
        self.namespace_idx = None
        self.fileRoot = None
        self.loop = asyncio.get_event_loop()


    async def init_server(self):
        await self.server.init()
        self.namespace_idx = await self.server.register_namespace("http://example.org/filesystem")
        objects = self.server.nodes.objects
        self.fileRoot = await objects.add_folder(ua.NodeId(self.namespace_idx,42), ua.QualifiedName("FileSystem", 0))

       # Referenztypen für File und Folder holen
        self.file_type = await self.server.nodes.base_object_type.get_child(
            "0:FileType")
        self.folder_type = await self.server.nodes.base_object_type.get_child(
            ["0:FolderType", "0:FileDirectoryType"])

        # Watchdog observer
        event_handler = FileSystemHandler(self)
        observer = Observer()
        observer.schedule(event_handler, ROOT_DIR, recursive=True)
        observer.start()

        # Initial Scan
        await self.add_filesystem_nodes(ROOT_DIR, self.fileRoot)

    async def add_filesystem_nodes(self, path, parent_node):
        if os.path.isdir(path):
            print(os.path.basename(path))
            folder_node = await instantiate(parent=parent_node, node_type=self.folder_type, bname=ua.QualifiedName(os.path.basename(path), self.namespace_idx), instantiate_optional=False, dname=ua.LocalizedText(os.path.basename(path), ""))
            for item in os.listdir(path):
                item_path = os.path.join(path, item)
                await self.add_filesystem_nodes(item_path, folder_node[0])
        elif os.path.isfile(path):
            await instantiate(parent=parent_node, node_type=self.file_type, bname=ua.QualifiedName(os.path.basename(path), self.namespace_idx), dname=ua.LocalizedText(os.path.basename(path), ""))

    async def update_filesystem(self, path, change_type):
        # Hier können Sie die Logik zur Aktualisierung des Dateisystems auf Basis von Ereignissen implementieren
        print(f"File system change detected: {path} - {change_type}")

    async def start(self):
        async with self.server:
            print(f"Server started at {self.server.endpoint}")
            while True:
                await asyncio.sleep(1)


async def main():
    server = OPCUAFileSystemServer("opc.tcp://0.0.0.0:48400")
    await server.init_server()
    await server.start()

if __name__ == "__main__":
    asyncio.run(main())
