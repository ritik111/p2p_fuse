import socket
import os
import time
import fuse
import stat
from stat import S_IFDIR, S_IFREG
import errno
import json
import threading
import random


class FuseClient(fuse.Operations):
    def __init__(self, server_ip, server_port):
        self.server_ip = server_ip
        self.server_port = server_port
        time.sleep(1)
        self.connection = self.connect_to_server()
        self.cache = {}
        if not self.connection:
            raise Exception("Failed to connect to the server.")
        
        if os.path.isfile(f"{self.server_ip.replace('.','_')}_key.txt"):
            with open(f"{self.server_ip.replace('.','_')}_key.txt", "r") as key_file:
                str_key = key_file.read()
                self.key = str_key.encode('utf-8')
        else :
            int_key = random.randint(11111, 99999)
            str_key = str(int_key)
            with open(f"{self.server_ip.replace('.','_')}_key.txt", "w") as key_file:
                  key_file.write(str_key)
            self.key = str_key.encode('utf-8')
       
    def xor_cipher(self, input_data, key, offset=0):
        if isinstance(key, str):
            key = key.encode()
        return bytes(b ^ key[(i + offset) % len(key)] for i, b in enumerate(input_data))
    
    def connect_to_server(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.connect((self.server_ip, self.server_port))
            print(f"\nConnected to server {self.server_ip}:{self.server_port}\n")
            return sock
        except Exception as e:
            print(f"Connection error: {e}")
            return None

    def _send_command(self, command, **kwargs):
        if not self.connection:
            print("No connection to server.")
            return {'status': 'error', 'message': 'No connection'}
        
        request = {'command': command, **kwargs}
        try:
            self.connection.sendall(json.dumps(request).encode('utf-8'))
            response_data = self.connection.recv(1024*8)
            return json.loads(response_data.decode('utf-8'))
        except Exception as e:
            print(f"Network error: {e}")
            self.connection.close()
            return {'status': 'error', 'message': str(e)}

#---------------------FUSE METHODS------------------------------------------------------

    def readdir(self, path, fh):                #LS
        response = self._send_command('LS', path=path)
        if response['status'] == 'success':
            for item in ['.', '..'] + response['files']:
                yield item
        else:
            print(f"Server error: {response['message']}")
            raise fuse.FuseOSError(errno.EIO)

    def getattr(self, path, fh=None):
        if path in self.cache:
            st_data = self.cache[path]
            return st_data
        
        response = self._send_command('GETATTR', path=path)
        if response['status'] == 'success':
            st = {}
            st["st_nlink"] = response.get('st_nlink',0)
            st["st_mode"] = response.get('st_mode', 0)
            st["st_size"] = response.get('st_size', 0)
            st["st_ctime"] = response.get('st_ctime', 0)
            st["st_mtime"] = response.get('st_mtime', 0)
            st["st_atime"] = response.get('st_atime', 0)
            self.cache[path] = st
            return st
        else:
            if response['status'] == 'error':               #file not found
                raise fuse.FuseOSError(errno.ENOENT)
            else:
                raise fuse.FuseOSError(errno.EIO)

    def statfs(self,path):
        response = self._send_command('STATFS', path=path)
        #if response.get('status') == 'success':            #we are not using server's disk info
        return {
                'f_bsize' : 4096,
                'f_frsize' : 4096,
                'f_blocks' : 1024*1024,
                'f_bfree' : 1024*1024,
                'f_bavail' : 1024*1024,
                'f_files' : 1000000,
                'f_ffree' : 1000000,
                'f_favail' : 1000000,
                'f_namemax' : 255,
            }
    
    def truncate(self,path,length,fh=None):
        self.cache.pop(path, None)
        response = self._send_command('TRUNCATE',path=path,length=length)
        if response.get('status') == 'success':
            return 0
        else:
            print(f"server error on truncate : {response.get('message')}")
            raise fuse.FuseOSError(errno.EIO)
    
    def open(self, path, flags):
        self.cache.pop(path, None)
        response = self._send_command('OPEN',path=path,flags=flags)
        if(response.get('status') == 'success'):
            return response['fh']
        elif response.get('message') == 'file or directory not found':
            raise fuse.FuseOSError(errno.ENOENT)
        elif response.get('message') == 'Permission denied':
            raise fuse.FuseOSError(errno.EACCES)
        else:
            print(f"Server error on open : {response.get('message')}")
            raise fuse.FuseOSError(errno.EIO)
        return 0
       
    def read(self, path, size, offset, fh):
        self.cache.pop(path, None)
        request = {}
        request['command'] = 'READ'
        request['path'] = path
        request['fh'] = fh
        request['size'] = size
        request['offset'] = offset
        self.connection.sendall(json.dumps(request).encode('utf-8'))
        raw_header = self.connection.recv(10, socket.MSG_WAITALL)      #MSG_WAITALL says -: Hey OS don't return from this until i have exactly 10B" 
        if not raw_header:
            raise Exception("Connection closed")
        res_header_len = int(raw_header.decode('utf-8').strip())
        res_json = json.loads(self.connection.recv(res_header_len, socket.MSG_WAITALL).decode('utf-8'))
        if res_json['status'] == 'success':
            bytes_to_get = res_json['bytes_sent']
            if bytes_to_get == 0:
                return b""
            data = bytearray()
            curr_offset = offset
            while len(data) < bytes_to_get:
                packet = self.connection.recv(bytes_to_get - len(data))
                if not packet:
                    return b""
                decrypted_packet = self.xor_cipher(packet,self.key,curr_offset)
                data.extend(decrypted_packet)
                curr_offset += len(packet)
            return bytes(data)
        else:
            raise fuse.FuseOSError(errno.EIO)
        
    def rename(self,old,new,flags=0):
        self.cache.pop(old, None)
        response = self._send_command('RENAME',old_path=old,new_path=new)
        if response.get('status') == 'success':
            return 0;
        elif (response.get('message') == 'Permission denied'):
            raise fuse.FuseOSError(errno.EACCES)
        else:
            print("Server error on rename : {response.get('message')}")
            raise fuse.FuseOSError(errno.EIO)
    
    def write(self, path, data, offset, fh):
        self.cache.pop(path, None)
        response = self._send_command('WRITE', path=path, offset=offset,length=len(data))
        if(response['status'] == 'success') :
            encrypted_data = self.xor_cipher(data,self.key,offset)
            self.connection.sendall(encrypted_data)
            response_data = self.connection.recv(1024)
            response = json.loads(response_data.decode('utf-8'))
            if(response['status'] == 'data_written'):
                return len(data)
            else :
                print("error happens while writing data at server side ")
                return 0
        elif (response['status'] == 'error'):
            print(f"error : {response['message']}")
            return 0
        else :
            print("file operation error at server side ")
            return 0
        
    def create(self, path, mode, fi=None):
        self.cache.pop(path, None)
        response = self._send_command('CREATE', path=path)
        if response['status'] == 'success':
            return 0
        else:
            print(f"Server error: {response['message']}")
            raise fuse.FuseOSError(errno.EIO)

    def release(self, path, fh):                    #Closes a file (placeholder)
        response = self._send_command('RELEASE', path=path, fh=fh)
        if response['status'] == 'success':
            return 0
        else:
            raise fuse.FuseOSError(errno.EIO)       #server error on release

    def unlink(self, path):                         #Deletes a file
        self.cache.pop(path, None)
        response = self._send_command('UNLINK', path=path)
        if response['status'] == 'success':
            return 0
        else:
            print(f"Server error: {response['message']}")
            raise fuse.FuseOSError(errno.EIO)

    def mkdir(self, path, mode):                    #Creates a directory
        self.cache.pop(path, None)
        response = self._send_command('MKDIR', path=path)
        if response['status'] == 'success':
            return 0
        else:
            print(f"Server error: {response['message']}")
            raise fuse.FuseOSError(errno.EIO)

    def rmdir(self, path):                          #Removes a directory
        self.cache.pop(path, None)
        response = self._send_command('RMDIR', path=path)
        if response['status'] == 'success':
            return 0
        else:
            print(f"Server error: {response['message']}")
            raise fuse.FuseOSError(errno.EIO)


#--------------------------------Main function------------------------------------------------------------------

def start_client() :
    DEFAULT_PORT_FOR_BROADCAST = 4444
    storage_size = 5 # Requesting 5 GB
    request = {'service' : 'storage','size_needed' : storage_size}
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.bind(('', 0))
    sock.sendto(f"{json.dumps(request)}".encode('utf-8'), ('255.255.255.255', DEFAULT_PORT_FOR_BROADCAST))
    print("\nRequest sent. Waiting for a reply...")
    
    sock.settimeout(10.0)
    server_ip = None
    server_port = 0

    try:
        data, addr = sock.recvfrom(1024)
        reply = json.loads(data.decode('utf-8'))
        print(f"Got reply from {addr[0]}:{addr[1]} \n")
        if reply['flag'] == "Green":
            server_ip = addr[0]
            server_port = reply['new_port']
    except socket.timeout:
        print("\nNo Device found!!! Program terminated.\n")
        return

    sock.close()

    if server_ip:
        print(f"\nDevice found at {server_ip}:{server_port}")
        mount_point = "p2p_storage"
        if not os.path.exists(mount_point):
            os.makedirs(mount_point)
            print(f"Created mount point: {mount_point}")
        
        print(f"\nMounting FUSE filesystem at {mount_point}...")
        fuse.FUSE(FuseClient(server_ip, server_port), mount_point, nothreads=True, foreground=True)
    print("Program Terminated!!!")

if __name__ == "__main__":
    start_client()
