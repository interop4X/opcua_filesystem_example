from asyncua import ua, uamethod
from asyncua.common.instantiate_util import instantiate
import os


class File:

    def __init__(self, server, namespace_idx,root_node):
        self.server = server
        self.namespace_idx = namespace_idx
        self.open_files = {}
        self.root_node = root_node

    async def add_file_node(self, path, parent_node):
        print(parent_node)
        filetype_node = await self.server.nodes.base_object_type.get_child([
                                                                     "0:FileType"])
        result = await instantiate(parent=parent_node, idx=self.namespace_idx, node_type=filetype_node, bname=ua.QualifiedName(os.path.basename(path), self.namespace_idx), dname=ua.LocalizedText(os.path.basename(path), ""))
        file_node = result[0]
        # Initialisierung der Dateigröße
        self.file_size_node = await file_node.get_child(f"0:Size")
        await self.file_size_node.write_value(ua.UInt64(os.path.getsize(path)))
        await self.link_methods_to_file(file_node)
