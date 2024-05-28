import asyncio
from asyncua import ua, uamethod, Server
from asyncua.common.instantiate_util import instantiate
from watchdog.observers import Observer
from filesystem_handler import FileSystemHandler
import os

# Konfigurationsordner, der als Root für das OPC UA Dateisystem dient
ROOT_DIR = "root"


class OPCUAServer:
    def __init__(self, endpoint):
        self.server = Server()
        self.server.set_endpoint(endpoint)
        self.namespace_idx = None
        self.loop = asyncio.get_event_loop()

    async def init_server(self):
        await self.server.init()
        self.namespace_idx = await self.server.register_namespace("http://example.org/filesystem")
        objects = self.server.nodes.objects
        self.file_system_root = await objects.add_folder(ua.NodeId(self.namespace_idx, 42), ua.QualifiedName("FileSystem", 0))
        return self.file_system_root, self.namespace_idx

    async def start(self):
        async with self.server:
            print(f"Server gestartet an {self.server.endpoint}")
            while True:
                await asyncio.sleep(1)

    def link_method(self, method_node, method):
        self.server.link_method(method_node, method)


class FileSystem:
    def __init__(self, server, root_node, namespace_idx):
        self.server = server
        self.root_node = root_node
        self.namespace_idx = namespace_idx
        self.open_files = {}  # Dictionary zur Verwaltung offener Dateihandles

    async def init_filesystem(self):
        self.file_type = await self.server.nodes.base_object_type.get_child(["0:FileType"])
        self.folder_type = await self.server.nodes.base_object_type.get_child(["0:FolderType", "0:FileDirectoryType"])
        await self.add_filesystem_nodes(ROOT_DIR, self.root_node)

    async def add_filesystem_nodes(self, path, parent_node):
        if os.path.isdir(path):
            result = await instantiate(parent=parent_node, node_type=self.folder_type, bname=ua.QualifiedName(os.path.basename(path), self.namespace_idx), instantiate_optional=False, dname=ua.LocalizedText(os.path.basename(path), ""))
            folder_node = result[0]
            await self.link_methods_to_folder(folder_node)
            for item in os.listdir(path):
                item_path = os.path.join(path, item)
                await self.add_filesystem_nodes(item_path, folder_node)
        elif os.path.isfile(path):
            await self.add_file_node(path, parent_node)

    async def add_file_node(self, path, parent_node):
        result = await instantiate(parent=parent_node, node_type=self.file_type, bname=ua.QualifiedName(os.path.basename(path), self.namespace_idx), dname=ua.LocalizedText(os.path.basename(path), ""))
        file_node = result[0]
        await self.link_methods_to_file(file_node)

    async def link_methods_to_folder(self, folder_node):
        await self.link_method_to_node(folder_node, "CreateDirectory", self.create_directory)
        await self.link_method_to_node(folder_node, "CreateFile", self.create_file)
        await self.link_method_to_node(folder_node, "Delete", self.delete_node)
        await self.link_method_to_node(folder_node, "MoveOrCopy", self.move_or_copy)

    async def link_methods_to_file(self, file_node):
        await self.link_method_to_node(file_node, "Open", self.open_file)
        await self.link_method_to_node(file_node, "Close", self.close_file)
        await self.link_method_to_node(file_node, "Read", self.read_file)
        await self.link_method_to_node(file_node, "Write", self.write_file)
        await self.link_method_to_node(file_node, "SetPosition", self.set_position)

    async def link_method_to_node(self, node, method_name, method):
        method_node = await node.get_child(f"0:{method_name}")
        self.server.link_method(method_node, method)

    async def update_filesystem(self, path, change_type):
        print(f"Dateisystemänderung erkannt: {path} - {change_type}")

    async def get_full_path_from_node(self, node_id):
        path_elements = []
        current_node = self.server.get_node(node_id)
        while current_node.nodeid != self.root_node.nodeid:
            browse_name = await current_node.read_browse_name()
            path_elements.append(browse_name.Name)
            current_node = await current_node.get_parent()
        path_elements.reverse()
        return os.path.join(*path_elements)

    def convert_mode(self, mode):
        modes = {1: "rb", 2: "wb", 3: "ab", 5: "r+b", 6: "w+b", 7: "a+b"}
        return modes.get(mode, "Invalid mode")

    @uamethod
    async def create_directory(self, parent, path):
        parent_dir = await self.get_full_path_from_node(parent)
        full_path = os.path.join(parent_dir, path)
        try:
            os.makedirs(full_path)
            await self.add_filesystem_nodes(full_path, self.server.get_node(parent))
            return [ua.Variant(True, ua.VariantType.Boolean)]
        except Exception as e:
            print(f"Fehler beim Erstellen des Verzeichnisses: {e}")
            return [ua.Variant(False, ua.VariantType.Boolean)]

    @uamethod
    async def create_file(self, parent, path, requestFileOpen):
        parent_dir = await self.get_full_path_from_node(parent)
        full_path = os.path.join(parent_dir, path)
        try:
            with open(full_path, 'w') as f:
                f.write('')
            await self.add_file_node(full_path, self.server.get_node(parent))
            return [ua.Variant(True, ua.VariantType.Boolean), ua.Variant(0, ua.VariantType.UInt32)]
        except Exception as e:
            print(f"Fehler beim Erstellen der Datei: {e}")
            return [ua.Variant(False, ua.VariantType.Boolean)]

    @uamethod
    async def delete_node(self, parent, path):
        parent_dir = await self.get_full_path_from_node(parent)
        full_path = os.path.join(parent_dir, path)
        try:
            if os.path.isdir(full_path):
                os.rmdir(full_path)
            elif os.path.isfile(full_path):
                os.remove(full_path)
            return [ua.Variant(True, ua.VariantType.Boolean)]
        except Exception as e:
            print(f"Fehler beim Löschen des Knotens: {e}")
            return [ua.Variant(False, ua.VariantType.Boolean)]

    @uamethod
    async def move_or_copy(self, parent, src_path, dest_path, is_move):
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
            await self.add_filesystem_nodes(full_dest_path, self.server.get_node(parent))
            return [ua.Variant(True, ua.VariantType.Boolean)]
        except Exception as e:
            print(f"Fehler beim Verschieben oder Kopieren des Knotens: {e}")
            return [ua.Variant(False, ua.VariantType.Boolean)]

    @uamethod
    async def open_file(self, parent, mode):
        full_path = await self.get_full_path_from_node(parent)
        try:
            python_mode = self.convert_mode(mode)
            file_handle = open(full_path, python_mode)
            self.open_files[parent] = file_handle
            return ua.Variant(0, ua.VariantType.UInt32)
        except Exception as e:
            print(f"Fehler beim Öffnen der Datei: {e}")
            return False

    @uamethod
    async def close_file(self, parent, file_handle):
        try:
            if parent in self.open_files:
                self.open_files[parent].close()
                del self.open_files[parent]
        except Exception as e:
            print(f"Fehler beim Schließen der Datei: {e}")

    @uamethod
    async def read_file(self, parent, file_handle, length):
        try:
            if parent in self.open_files:
                data = self.open_files[parent].read(length)
                return ua.Variant(data, ua.VariantType.ByteString)
            else:
                return False
        except Exception as e:
            print(f"Fehler beim Lesen der Datei: {e}")
            return False

    @uamethod
    async def write_file(self, parent, file_handle, data):
        try:
            if parent in self.open_files:
                self.open_files[parent].write(data)
        except Exception as e:
            print(f"Fehler beim Schreiben der Datei: {e}")

    @uamethod
    async def set_position(self, parent, file_handle, position):
        try:
            if parent in self.open_files:
                self.open_files[parent].seek(position)
                return [ua.Variant(True, ua.VariantType.Boolean)]
            else:
                return [ua.Variant(False, ua.VariantType.Boolean)]
        except Exception as e:
            print(f"Fehler beim Setzen der Position: {e}")
            return [ua.Variant(False, ua.VariantType.Boolean)]


async def main():
    opcua_server = OPCUAServer("opc.tcp://0.0.0.0:48400")
    root_node, namespace_idx = await opcua_server.init_server()

    filesystem = FileSystem(opcua_server.server, root_node, namespace_idx)
    await filesystem.init_filesystem()

    event_handler = FileSystemHandler(filesystem, opcua_server)
    observer = Observer()
    observer.schedule(event_handler, ROOT_DIR, recursive=True)
    observer.start()

    await opcua_server.start()

if __name__ == "__main__":
    asyncio.run(main())
