# OPC UA Filesystem Example

## Project Description

This project provides an example of mapping a filesystem according to [OPC 10000-20 File Transfer](https://reference.opcfoundation.org/Core/Part20/v105/docs/) in OPC UA. It demonstrates how filesystems can be used in machine controls or flat glass companion specifications.


## Open Issues -
 Error messages are not yet represented in the status code
- fileHandle is not session-bound

## Installation

1. **Clone the repository**

 ~
  git clone https://github.com/interop4X/opcua_filesystem_example.git

2. **Install dependencies***

 cd opcua_filesystem_example

 pip install -r requirements.txt

## Usage

* Start the main application**

  python main.py

This starts the OPC UA server application that maps the filesystem. You can now connect to the OPC UA server using a client (e.g., UAExpert).
URL: `opc.tcp://0.0.0.0:48400`
~
## License

This project is licensed under the MIT License. See the [LICENSE](https://github.com/interop4X/opcua_filesystem_example/blob/main/LICENSE)  file for more details.

## Disclaimer

This is a prototype and not a finished product. Use it at your own risk. The maintainers and contributors are not responsible for any damages or losses caused by the use of this software.
