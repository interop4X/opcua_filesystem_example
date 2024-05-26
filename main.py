import asyncio
import os
from asyncua import ua, uamethod, Server
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
        self.fileRoot = await objects.add_folder(ua.NodeId(self.namespace_idx, 42), ua.QualifiedName("FileSystem", 0))

        # Referenztypen für File und Folder holen
        self.file_type = await self.server.nodes.base_object_type.get_child(["0:FileType"])
        self.folder_type = await self.server.nodes.base_object_type.get_child(["0:FolderType", "0:FileDirectoryType"])

        # Watchdog observer
        event_handler = FileSystemHandler(self)
        observer = Observer()
        observer.schedule(event_handler, ROOT_DIR, recursive=True)
        observer.start()

        # Initial Scan
        await self.add_filesystem_nodes(ROOT_DIR, self.fileRoot)

    async def add_filesystem_nodes(self, path, parent_node):
        if os.path.isdir(path):
            instantiate_result = await instantiate(parent=parent_node, node_type=self.folder_type, bname=ua.QualifiedName(os.path.basename(path), self.namespace_idx), instantiate_optional=False, dname=ua.LocalizedText(os.path.basename(path), ""))
            folder_node = instantiate_result[0]
            create_dir_node = await folder_node.get_child("0:CreateDirectory")
            self.server.link_method(create_dir_node, self.create_directory)
            for item in os.listdir(path):
                item_path = os.path.join(path, item)
                await self.add_filesystem_nodes(item_path, folder_node)
        elif os.path.isfile(path):
            await instantiate(parent=parent_node, node_type=self.file_type, bname=ua.QualifiedName(os.path.basename(path), self.namespace_idx), dname=ua.LocalizedText(os.path.basename(path), ""))

    async def update_filesystem(self, path, change_type):
        print(f"File system change detected: {path} - {change_type}")

    async def start(self):
        async with self.server:
            print(f"Server started at {self.server.endpoint}")
            while True:
                await asyncio.sleep(1)

    async def add_method(self, parent, name, func, input_args, output_args):
        method = await parent.add_method(
            ua.NodeId(f"{name}", self.namespace_idx),
            ua.QualifiedName(name, self.namespace_idx),
            func,
            input_args,
            output_args
        )

    @uamethod
    async def create_directory(self, parent, path):
        print(path, parent)
        parent_dir = await self.get_full_path_from_node(parent)
        full_path = os.path.join(parent_dir, path)
        try:
            os.makedirs(full_path)
            parent_node = self.server.get_node(parent)
            await self.add_filesystem_nodes(full_path, parent_node)
            return True
        except Exception as e:
            print(f"Error creating directory: {e}")
            return False

    async def create_file(self, parent, path):
        try:
            with open(path, 'w') as f:
                f.write('')
            return True
        except Exception as e:
            print(f"Error creating file: {e}")
            return False

    async def delete_node(self, parent, path):
        try:
            if os.path.isdir(path):
                os.rmdir(path)
            elif os.path.isfile(path):
                os.remove(path)
            return True
        except Exception as e:
            print(f"Error deleting node: {e}")
            return False

    async def move_or_copy(self, parent, src_path, dest_path, is_move):
        try:
            if is_move:
                os.rename(src_path, dest_path)
            else:
                if os.path.isdir(src_path):
                    os.system(f"cp -r {src_path} {dest_path}")
                else:
                    os.system(f"cp {src_path} {dest_path}")
            return True
        except Exception as e:
            print(f"Error moving or copying node: {e}")
            return False

    async def get_full_path_from_node(self, node_id):
        path_elements = []
        current_node = self.server.get_node(node_id)
        while current_node.nodeid != self.fileRoot.nodeid:
            browse_name = await current_node.read_browse_name()
            path_elements.append(browse_name.Name)
            current_node = await current_node.get_parent()
        path_elements.reverse()
        return os.path.join(*path_elements)



async def main():
    server = OPCUAFileSystemServer("opc.tcp://0.0.0.0:48400")
    await server.init_server()
    await server.start()

if __name__ == "__main__":
    asyncio.run(main())
