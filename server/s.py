import time
import socket
import shutil
import os
import threading
import json

def port_finder():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('',0))
    port_no = s.getsockname()[1]
    s.close()
    return port_no

def get_safe_path(client_dir, user_input):
    requested_path = os.path.join(client_dir, user_input.strip('/'))
    actual_path = os.path.abspath(requested_path)
    if not actual_path.startswith(os.path.abspath(client_dir)):
        return "Per_Err"
    return actual_path
    

def service(client_ip,my_new_port):
    open_files = {} 
    fd_counter = 1
    sock1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock1.bind(('', my_new_port))
    except socket.error as e:
        print(f"Error: {e}")
        return
    sock1.listen()
    print(f"\nTCP server is listening on port {my_new_port} for client {client_ip}...")
    
    conn, addr = sock1.accept()
    if addr[0] != client_ip:
        conn.close()
        return

    print(f"\nConnection established with {client_ip}")
    client_dir = f"client_storage_{addr[0].replace('.', '_')}"
    if not os.path.exists(client_dir):
        os.makedirs(client_dir)
        print(f"Created storage directory for client: {client_dir}")
    while True:
        try:
            data = conn.recv(1024*4)
            if not data:
                print("Received data is empty\nExiting!!!")
                break
            
            request = json.loads(data.decode('utf-8'))
            command = request.get('command')
            
            response = {}
            full_path = ""
            full_old_path = ""
            full_new_path = ""
            if command != "RELEASE" and command != "RENAME":
                path = request.get('path', '')
                full_path = get_safe_path(client_dir,path)
            
            elif command == "RENAME":
                old_path = request.get('old_path','')
                new_path = request.get('new_path','')
                full_old_path = get_safe_path(client_dir,old_path)
                full_new_path = get_safe_path(client_dir,new_path)
            
            if full_path == "Per_Err" or full_old_path == "Per_Err" or full_new_path == "Per_Err":
                response['status'] = 'error'
                response['message'] = "Access Denied: Path traversal attempt detected"
                conn.sendall(json.dumps(response).encode('utf-8'))
                continue

#-----------------------Actual Commands Handling-----------------------------------------------------------

            if command == "LS":
                if os.path.isdir(full_path):
                    files = os.listdir(full_path)
                    response['status'] = 'success'
                    response['files'] = files
                else:
                    response['status'] = 'error'
                    response['message'] = 'Directory not found'
            
            elif command == "GETATTR":
                if os.path.exists(full_path):
                    stats = os.stat(full_path)
                    response['status'] = 'success'
                    response['st_mode'] = stats.st_mode
                    response['st_nlink'] = stats.st_nlink
                    response['st_size'] = stats.st_size
                    response['st_ctime'] = stats.st_ctime
                    response['st_mtime'] = stats.st_mtime
                    response['st_atime'] = stats.st_atime
                else:
                    response['status'] = 'error'
                    response['message'] = 'File or directory not found'
            
            elif command == "TRUNCATE":
                length = request.get('length',0)
                try:
                    os.truncate(full_path,length)
                    response['status'] = 'success'
                except OSError as e:
                    response['status'] = 'error'
                    response['message'] = str(e)
            
            elif command == "OPEN":
                flags = request.get('flags',0)
                is_write_attempt = flags & os.O_WRONLY or flags & os.O_RDWR
                try:
                    if not os.path.isfile(full_path):
                        if not (flags & os.O_CREATE):
                            response['status'] = 'error'
                            response['message'] = 'file or directory not found'
                        else:
                            response['status'] = 'success'
                    else:
                        if is_write_attempt and not os.access(full_path,os.W_OK):
                            response['status'] = 'error'
                            response['message'] = 'Permission denied'
                            conn.sendall(json.dumps({'status':'error','message':'Permission denied'}).encode('utf-8'))
                            continue
                            
                        f_obj = open(full_path, 'rb+')
                        fd = fd_counter
                        open_files[fd] = f_obj
                        fd_counter += 1
        
                        response['status'] = 'success'
                        response['fh'] = fd
                except Exception as e:
                    response['status'] = 'error'
                    response['message'] = str(e)
            
            elif command == "READ":
                fh = request.get('fh')
                offset = request.get('offset', 0)
                size = request.get('size', 0)
                if fh in open_files:
                    f = open_files[fh]
                    f.seek(offset)
                    data = f.read(size)
                    actual_read_size = len(data)
                    header = {'status': 'success','bytes_sent': actual_read_size}
                    header_bytes = json.dumps(header).encode('utf-8')
                    conn.sendall(f"{len(header_bytes):<10}".encode('utf-8') + header_bytes)
                    #print("header sent to client")
                    if actual_read_size > 0:
                        conn.sendall(data)
                    continue
                else :
                    res = json.dumps({'status': 'error', 'message': 'Invalid handle'}).encode('utf-8')
                    conn.sendall(f"{len(res):<10}".encode('utf-8') + res)
            
            elif command == "RENAME":
                try:
                    os.rename(full_old_path,full_new_path)
                    response['status'] = 'success'
                except OSError as e:
                    response['status'] = 'error'
                    response['message'] = str(e)
                except Exception as e:
                    response['status'] = 'error'
                    response['message'] = str(e)
            
            elif command == "WRITE":
                offset = request.get('offset', 0)
                size = request.get('length',0)
                try:
                    with open(full_path, 'rb+') as f:
                        f.seek(offset)
                        response['status'] = 'success'
                        conn.sendall(json.dumps(response).encode('utf-8'))
                        received_data = b""
                        while len(received_data)<size:
                            chunk = conn.recv(min(size-len(received_data), 4096))
                            if not chunk:
                                break
                            received_data += chunk
                        f.write(received_data)
                        response['status'] = 'data_written'
                        conn.sendall(json.dumps(response).encode('utf-8'))
                        
                except Exception as e:
                    response['status'] = 'error'
                    response['message'] = str(e)
                    conn.sendall(json.dumps(response).encode('utf-8'))
                
                continue
            
            elif command == "CREATE":
                try:
                    f_obj = os.open(full_path, os.O_CREAT | os.O_WRONLY,0o666)
                    os.close(f_obj)
                    response['status'] = 'success'
                except Exception as e:
                    response['status'] = 'error'
                    response['message'] = str(e)
            
            elif command == "UNLINK":
                try:
                    os.unlink(full_path)
                    response['status'] = 'success'
                except OSError as e:
                    response['status'] = 'error'
                    response['message'] = str(e)

            elif command == "MKDIR":
                try:
                    os.mkdir(full_path,0o777)
                    response['status'] = 'success'
                except OSError as e:
                    response['status'] = 'error'
                    response['message'] = str(e)

            elif command == "RMDIR":
                try:
                    shutil.rmtree(full_path)    #deletes an entire directory tree recursively
                    response['status'] = 'success'
                except OSError as e:
                    response['status'] = 'error'
                    response['message'] = str(e)
                except Exception as e:
                    response['status'] = 'error'
                    response['message'] = str(e)
            
            elif command == "RELEASE":      #release a file (only acknowledge it)
                fh = request.get('fh')
                if fh in open_files:
                    open_files[fh].close()
                    del open_files[fh]
                    response['status'] = 'success'
                    response['message'] = 'File released'
                else:
                    response['status'] = 'error'
                    response['message'] = 'Unknown release command'
            
            elif command == "STATFS":
                try:
                    total, used, free = shutil.disk_usage(client_dir)
                    response['status'] = 'success'
                    response['bsize'] = 4096
                    response['blocks'] = total
                    response['bfree'] = free
                    response['bavail'] = free
                except Exception as e:
                    response['status'] = 'error'
                    response['message'] = str(e)
            
            conn.sendall(json.dumps(response).encode('utf-8'))

        except Exception as e:
            print(f"Error processing command: {e}")
            break
    
    print(f"Thread completed its task for client {client_ip}")
    conn.close()
    print("-" * 30)

def main_process():
    total_disk_space, used_space, avail_space = shutil.disk_usage('/')
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    HOST = ''
    DEFAULT_PORT_FOR_BROADCAST = 4444
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    
    try:
        sock.bind((HOST, DEFAULT_PORT_FOR_BROADCAST))
        print(f"\n\t\t\tUDP server is listening on port: {DEFAULT_PORT_FOR_BROADCAST}.....")
    except OSError as e:
        print(f"Could not bind to port {DEFAULT_PORT_FOR_BROADCAST}. Error: {e}")
        sock.close()
        return

    while True:
        print("waiting for client : \n")
        data, addr = sock.recvfrom(1024)
        response = json.loads(data.decode('utf-8'))
        client_ip = addr[0]
        client_port = addr[1]
        service_  = response['service']
        if service_ != 'storage':
            continue
        requested_space = response['size_needed']
        print(f"\nReceived address is {client_ip}:{client_port}")
        print(f"\nRequested storage size is: {requested_space} GB")
        
        avail_gb = round(avail_space / (1024**3), 2)
        
        if avail_gb > requested_space:
            my_new_port = port_finder()
            
            new_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            reply = {'flag':'Green', 'new_port':my_new_port}
            new_sock.sendto(json.dumps(reply).encode('utf-8'), (client_ip, client_port))
            new_sock.close()
            
            thread = threading.Thread(target=service, args=(client_ip,my_new_port))
            thread.daemon = True
            thread.start()

if __name__ == "__main__":
    main_process()
