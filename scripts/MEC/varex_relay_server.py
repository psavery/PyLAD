import json
import socket
import subprocess

BUFFER_SIZE = 65536

RUN_DESTINATION_DIR = 's3dfdtn:/sdf/scratch/lcls/ds/mec/mecl1019923/scratch/'

# Server
host = '0.0.0.0'
daq_port = 8089
varex_port = 5678

socket_args = [socket.AF_INET, socket.SOCK_STREAM]

with socket.socket(*socket_args) as daq_s, \
     socket.socket(*socket_args) as varex_s:
    daq_s.bind((host, daq_port))
    daq_s.listen(1)
    print(f'Listening for DAQ on {host}:{daq_port}')

    varex_s.bind((host, varex_port))
    varex_s.listen(1)
    print(f'Listening for Varex on {host}:{varex_port}')

    # Now relay this message to the varex socket
    varex_conn, varex_addr = varex_s.accept()
    print('Connected by varex:', varex_addr)
    with varex_conn:
        while True:
            print('Waiting for "arm" signal from DAQ...')
            daq_conn, daq_addr = daq_s.accept()
            with daq_conn:
                print('Connected by', daq_addr)

                print('Waiting to receive message from DAQ...')
                data = daq_conn.recv(BUFFER_SIZE)
                print('Received:', data.decode())

                varex_conn.sendall(data)
                print('Sent data to Varex')

                varex_return = varex_conn.recv(BUFFER_SIZE)
                print('Received from varex:', varex_return)
                print('Relaying message back to DAQ')
                daq_conn.sendall(varex_return)
                print('Varex message relayed back to DAQ')

                if varex_return != b'OK':
                    # Don't proceed if there was some issue
                    continue

                # Now see if varex instructs us to copy a directory over
                varex_return = varex_conn.recv(BUFFER_SIZE)
                try:
                    command = json.loads(varex_return.decode())
                    if 'copy_dir' in command:
                        copy_dir = command['copy_dir']
                        subprocess.run([
                            'scp',
                            '-r',
                            f'mec-varex@172.21.43.22:{copy_dir}',
                            RUN_DESTINATION_DIR,
                        ], check=True)
                except Exception as e:
                    print('Failed to copy run directory over:', e)
