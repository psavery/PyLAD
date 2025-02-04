import json
from pathlib import Path
import shutil
import socket
import subprocess
import time

from pylad.config import create_instrument_from_json_file


BUFFER_SIZE = 65536
WRITE_DIR = Path('./MECVarexData')
RUN_PYLAD_VIEWER = True

# Client
host = '172.21.43.21'
port = 5678

pylad_viewer_process = None

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    print('Setting up connection with psmeclogin...')
    s.connect((host, port))
    print('Connected to psmeclogin')
    while True:
        print('Waiting for "arm" signal from DAQ...')
        json_config = s.recv(BUFFER_SIZE)
        message_received_time = time.time()
        print('Received json config:', json_config)
        try:
            json_config = json_config.decode('utf-8')
            config = json.loads(json_config)
            run_name = config['run_name']
            experiment_name = config['experiment']

            # Write the json file to the write_dir
            run_dir = WRITE_DIR / experiment_name / f'run{run_name}'
            run_dir.mkdir(parents=True, exist_ok=True)
            json_path = run_dir / 'pylad_config.json'
            with open(json_path, 'w') as wf:
                json.dump(config, wf, indent=4)

        except Exception as e:
            print('Failed to load config:', e)
            s.sendall(b'NOT OK')
            continue

        # Compute disk usage
        # If we don't have enough disk space left for a run,
        # then abort!
        total, used, free = shutil.disk_usage('C:/')
        free_gb = free / (2**30)
        if free_gb < 5:
            print(
                'The Varex computer is almost out of memory! '
                f'Only {free_gb} GB remain! Please delete runs from '
                f'the run directory at {WRITE_DIR} before running again. '
                'Verify these runs are saved on s3dftn before deleting.'
            )
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

        # Now try to free up some memory from the previous acquisition
        instr.resource_cleanup()

        # If we received all expected frames, proceed to open
        # the pylad viewer GUI automatically
        data_paths_to_visualize = list(instr.data_paths_to_visualize.values())
        if (
            RUN_PYLAD_VIEWER and
            all(x is not None for x in data_paths_to_visualize)
        ):
            try:
                paths = [str(x) for x in data_paths_to_visualize]
                if (
                    pylad_viewer_process is None or
                    # If "poll()" returns None, it means the process
                    # was terminated, and we need to start a new one.
                    pylad_viewer_process.poll() is not None
                ):
                    pylad_viewer_process = subprocess.Popen(
                        ['pylad-viewer'] + paths,
                        stdin=subprocess.PIPE,
                    )
                else:
                    # Tell the process to open a new set of files
                    message = ', '.join(paths) + '\n'
                    pylad_viewer_process.stdin.write(message.encode())
                    pylad_viewer_process.stdin.flush()

            except Exception as e:
                # It's not the end of the world that it failed
                print('Failed to run/update "pylad-viewer":', e)
