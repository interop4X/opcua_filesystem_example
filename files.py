from asyncua import ua, uamethod
from asyncua.common.instantiate_util import instantiate
import os


class Files:
    def __init__(self, server, namespace_idx,root_node):
        self.server = server
        self.namespace_idx = namespace_idx
        self.open_files = {}
        self.root_node = root_node

    async def add_file_node(self, path, parent_node):
        filetype_node = await self.server.nodes.base_object_type.get_child([
                                                                  "0:FileType"])
        result = await instantiate(parent=parent_node, idx=self.namespace_idx, node_type=filetype_node, bname=ua.QualifiedName(os.path.basename(path), self.namespace_idx), dname=ua.LocalizedText(os.path.basename(path), ""))
        file_node = result[0]
        await self.link_methods_to_file(file_node)

    async def link_methods_to_file(self, file_node):
        await self.link_method_to_node(file_node, "Open", self.open_file)
        await self.link_method_to_node(file_node, "Close", self.close_file)
        await self.link_method_to_node(file_node, "Read", self.read_file)
        await self.link_method_to_node(file_node, "Write", self.write_file)
        await self.link_method_to_node(file_node, "SetPosition", self.set_position)

    async def link_method_to_node(self, node, method_name, method):
        method_node = await node.get_child(f"0:{method_name}")
        self.server.link_method(method_node, method)

    def convert_mode(self, mode):
        modes = {1: "rb", 2: "wb", 3: "ab", 5: "r+b", 6: "w+b", 7: "a+b"}
        return modes.get(mode, "Invalid mode")

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

    async def get_full_path_from_node(self, node_id):
        print(node_id)
        path_elements = []
        current_node = self.server.get_node(node_id)
        while current_node.nodeid != self.root_node.nodeid:
            browse_name = await current_node.read_browse_name()
            path_elements.append(browse_name.Name)
            current_node = await current_node.get_parent()
        path_elements.reverse()
        return os.path.join(*path_elements)
