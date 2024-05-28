import asyncio
from asyncua import ua, Server
from watchdog.observers import Observer
from filesystem import FileSystem
from filesystem_handler import FileSystemHandler


async def main():
    opcua_server = OPCUAServer("opc.tcp://0.0.0.0:48400")
    root_node, namespace_idx = await opcua_server.init_server()

    filesystem = FileSystem(opcua_server.server, root_node, namespace_idx)
    await filesystem.init_filesystem()

    event_handler = FileSystemHandler(filesystem, opcua_server)
    observer = Observer()
    observer.schedule(event_handler, filesystem.root_dir, recursive=True)
    observer.start()

    await opcua_server.start()


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


if __name__ == "__main__":
    asyncio.run(main())
