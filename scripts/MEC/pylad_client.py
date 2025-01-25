import json
from pathlib import Path
import socket
import subprocess
import time

from pylad.config import create_instrument_from_json_file


BUFFER_SIZE = 65536
WRITE_DIR = Path('./Runs')


# Client
host = '172.21.43.21'
port = 5678

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    print('Setting up connection with psmeclogin...')
    s.connect((host, port))
    print('Connected to psmeclogin')
    while True:
        print('Waiting for next json config...')
        json_config = s.recv(BUFFER_SIZE)
        message_received_time = time.time()
        print('Received json config:', json_config)
        try:
            json_config = json_config.decode('utf-8')
            config = json.loads(json_config)
            run_name = config['run_name']

            # Write the json file to the write_dir
            run_dir = WRITE_DIR / run_name
            run_dir.mkdir(parents=True, exist_ok=True)
            json_path = run_dir / 'pylad_config.json'
            with open(json_path, 'w') as wf:
                json.dump(config, wf, indent=4)

        except Exception as e:
            print('Failed to load config:', e)
            s.sendall(b'NOT OK')
            continue

        # Tell the DAQ that it can proceed!
        s.sendall(b'OK')

        # Now proceed to initialize the instrument and start acquisition
        instr = create_instrument_from_json_file(json_path)

        while time.time() - message_received_time < 6:
            print('Waiting....')
            time.sleep(0.25)

        instr.start_acquisition()

        while not instr.acquisition_finished:
            time.sleep(1)
            instr.shutdown_if_time_limit_exceeded()

        if not instr.all_expected_frames_received:
            msg = 'Did not receive all expected frames!'
            print(msg)
            s.sendall(json.dumps({"message": msg}).encode('utf-8'))
            continue

        # Try to initiate a data transfer
        # Need it to be in posix format for it to work correctly.
        dir_path = instr.save_files_path.resolve().as_posix()
        s.sendall(json.dumps({"copy_dir": dir_path}).encode('utf-8'))

        # If we received all expected frames, proceed to open
        # the pylad viewer GUI automatically
        last_data_files = list(instr.last_saved_data_frame_paths.values())
        if False and all(x is not None for x in last_data_files):
            try:
                subprocess.Popen(['pylad-viewer'] + [str(x) for x in last_data_files])
            except Exception as e:
                # It's not the end of the world that it failed
                print('Failed to open "pylad-viewer":', e)
