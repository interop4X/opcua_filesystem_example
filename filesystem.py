import os
from asyncua import ua, uamethod
from asyncua.common.instantiate_util import instantiate
from files import Files


class FileSystem:
    def __init__(self, server, root_node, namespace_idx):
        self.server = server
        self.root_node = root_node
        self.namespace_idx = namespace_idx
        self.root_dir = "root"

    async def init_filesystem(self):
        self.file_type = await self.server.nodes.base_object_type.get_child(["0:FileType"])
        self.folder_type = await self.server.nodes.base_object_type.get_child(["0:FolderType", "0:FileDirectoryType"])
        await self.add_filesystem_nodes(self.root_dir, self.root_node)

    async def add_filesystem_nodes(self, path, parent_node):
        if os.path.isdir(path):
            result = await instantiate(parent=parent_node, idx=self.namespace_idx, node_type=self.folder_type, bname=ua.QualifiedName(os.path.basename(path), self.namespace_idx), instantiate_optional=False, dname=ua.LocalizedText(os.path.basename(path), ""))
            folder_node = result[0]
            await self.link_methods_to_folder(folder_node)
            for item in os.listdir(path):
                item_path = os.path.join(path, item)
                await self.add_filesystem_nodes(item_path, folder_node)
        elif os.path.isfile(path):
            files = Files(self.server, self.namespace_idx, self.root_node)
            await files.add_file_node(path, parent_node)

    async def link_methods_to_folder(self, folder_node):
        await self.link_method_to_node(folder_node, "CreateDirectory", self.create_directory)
        await self.link_method_to_node(folder_node, "CreateFile", self.create_file)
        await self.link_method_to_node(folder_node, "Delete", self.delete_node)
        await self.link_method_to_node(folder_node, "MoveOrCopy", self.move_or_copy)

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
            files = Files(self.server, self.namespace_idx)
            await files.add_file_node(full_path, self.server.get_node(parent))
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
