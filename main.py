import asyncio
import os
from asyncua import ua, uamethod, Server
from asyncua.common.instantiate_util import instantiate
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
            await self.link_method_to_node(folder_node, "CreateDirectory", self.create_directory)
            await self.link_method_to_node(folder_node, "CreateFile", self.create_file)
            await self.link_method_to_node(folder_node, "Delete", self.delete_node)
            await self.link_method_to_node(folder_node, "MoveOrCopy", self.move_or_copy)
            for item in os.listdir(path):
                item_path = os.path.join(path, item)
                await self.add_filesystem_nodes(item_path, folder_node)
        elif os.path.isfile(path):
            await instantiate(parent=parent_node, node_type=self.file_type, bname=ua.QualifiedName(os.path.basename(path), self.namespace_idx), dname=ua.LocalizedText(os.path.basename(path), ""))
            
    async def add_file_node(self, path, parent_node):
        if os.path.isfile(path):
            await instantiate(parent=parent_node, node_type=self.file_type, bname=ua.QualifiedName(os.path.basename(path), self.namespace_idx), dname=ua.LocalizedText(os.path.basename(path), ""))

    async def link_method_to_node(self, node, method_name, method):
        method_node = await node.get_child(f"0:{method_name}")
        self.server.link_method(method_node, method)

    async def update_filesystem(self, path, change_type):
        print(f"File system change detected: {path} - {change_type}")

    async def start(self):
        async with self.server:
            print(f"Server started at {self.server.endpoint}")
            while True:
                await asyncio.sleep(1)

    @uamethod
    async def create_directory(self, parent, path):
        print(path, parent)
        parent_dir = await self.get_full_path_from_node(parent)
        full_path = os.path.join(parent_dir, path)
        try:
            os.makedirs(full_path)
            parent_node = self.server.get_node(parent)
            await self.add_filesystem_nodes(full_path, parent_node)
            return [ua.Variant(True, ua.VariantType.Boolean)]
        except Exception as e:
            print(f"Error creating directory: {e}")
            return [ua.Variant(False, ua.VariantType.Boolean)]

    @uamethod
    async def create_file(self, parent, path, requestFileOpen):
        print(path, parent)
        parent_dir = await self.get_full_path_from_node(parent)
        full_path = os.path.join(parent_dir, path)
        try:
            with open(full_path, 'w') as f:
                f.write('')
            parent_node = self.server.get_node(parent)
            await self.add_file_node(full_path, parent_node)
            return [ua.Variant(True, ua.VariantType.Boolean), ua.Variant(0, ua.VariantType.UInt32)]
        except Exception as e:
            print(f"Error creating file: {e}")
            return [ua.Variant(False, ua.VariantType.Boolean)]

    @uamethod
    async def delete_node(self, parent, path):
        print(path, parent)
        parent_dir = await self.get_full_path_from_node(parent)
        full_path = os.path.join(parent_dir, path)
        try:
            if os.path.isdir(full_path):
                os.rmdir(full_path)
            elif os.path.isfile(full_path):
                os.remove(full_path)
            return [ua.Variant(True, ua.VariantType.Boolean)]
        except Exception as e:
            print(f"Error deleting node: {e}")
            return [ua.Variant(False, ua.VariantType.Boolean)]

    @uamethod
    async def move_or_copy(self, parent, src_path, dest_path, is_move):
        print(src_path, dest_path, parent)
        parent_dir = await self.get_full_path_from_node(parent)
        full_src_path = os.path.join(parent_dir, src_path)
        full_dest_path = os.path.join(parent_dir, dest_path)
        try:
            if is_move:
                os.rename(full_src_path, full_dest_path)
            else:
                if os.path.isdir(full_src_path):
                    os.system(f"cp -r {full_src_path} {full_dest_path}")
                else:
                    os.system(f"cp {full_src_path} {full_dest_path}")
            parent_node = self.server.get_node(parent)
            await self.add_filesystem_nodes(full_dest_path, parent_node)
            return [ua.Variant(True, ua.VariantType.Boolean)]
        except Exception as e:
            print(f"Error moving or copying node: {e}")
            return [ua.Variant(False, ua.VariantType.Boolean)]

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
