MEC Files
=========

These were the files used for communication and automatically starting
PyLAD at SLAC MEC 01/28/2025 to 01/31/2025. A short description of
each is present below.

In order to successfully run the detectors and the data transfer, a
user must first run `python varex_relay_server.py` on `psmeclogin`, and
in a command prompt on the Varex computer, run `.\run_pylad_client.bat`.

After each has been started, the Varex computer will have communicated
with the relay server on `psmeclogin`, and both should say
`Waiting to receive message from DAQ...`. When that happens, they are
ready to start.

# varex_relay_server.py

This file is the relay server that ran on `psmeclogin`. This relay
server was necessary because the DAQ and the Varex computer were on
separate networks, and could not directly communicate with each other.
However, they could both communicate with `psmeclogin`, so `psmeclogin`
acted as an intermediary. It does not require any kind of special Python
environment to run, since it only requires dependencies that ship with
Python itself. Just run it on `psmeclogin` using any `python3` executable.

There are a number of variables at the beginning of the file that can
be modified, if needed, including the location of the results
directory for the particular run (for us, the run was `mecl1019923`).

In order for the automatic copying of the data files from the Varex
computer to s3dfdtn to work successfully, this script needs to be ran
by a user that has passwordless (public key) authentication to both
the Varex computer and s3dfdtn. You can test this by starting on
`psmeclogin`. First run `ssh mec-login@172.21.43.22` and verify that
it does not ask for your password. Then return to `psmeclogin` and
verify that `ssh s3dfdtn` does not require a password. If a password
is required, copy your public key (located in `~/.ssh/id_rsa.pub`. If
it is not there, run `ssh-keygen` and use no passphrase), and paste
it as a new row in `~/.ssh/authorized_keys`, both on the Varex computer
and `s3dfdtn`. It should then work successfully.

If, at some point, the network gets changed so that the DAQ and the
Varex computer can communicate directly, the contents of this script
can be copied over to the Varex computer (so that the Varex computer
will act as the server), and instead of sending messages to the Varex
computer, the script will run the contents of `pylad_client.py`
directly. In this case, the automatic data transfer may also need to
be changed, if one can determine a way to `scp` the data over without
a password.

# run_pylad_client.bat

This is a script that simply activates the conda environment which
contains both `pylad` and `pylad-viewer` installed, and runs the
`pylad_client.py` file.

# pylad_client.py

This script is intended to be ran on the Varex computer from within
a conda environment that has `pylad` and `pylad-viewer` already installed
(see `run_pylad_client.bat` above).

It first creates a socket connection with the relay server running on
`psmeclogin`, and then waits to receive the `arm` signal from the DAQ.
The `arm` signal from the DAQ will contain the json config that
instructs how `pylad` (and consequently the Varex detectors) is to
be ran. This includes the number of skip frames (to stabilize the
background), background frames, data frames, and post shot background
frames. It also includes the gain setting, run number, and binning.

If no triggers are received after 15 seconds of initializing, the
acquisition is aborted automatically. This avoids an issue where, after
approximately 20 seconds of no triggers, the detectors automatically
go into "idle" mode where they collect frames at a maximum rate of
15 Hz. If this happens, we would incorrectly identify the frames coming
in at 15 Hz as the frames we were waiting to receive.
