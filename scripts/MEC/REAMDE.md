Overview
========

To run the full PyLAD workflow at MEC, the following steps must be taken:

1. Log into `psmeclogin` with a user that has public key authentication to both the Varex computer and s3dfdtn.
2. With this user, run the `varex_relay_server.py` file
3. On the MEC DAQ computer, connect to the Varex computer with RDP
4. Open a command prompt and run `.\run_pylad_client.bat`

After this is complete, the MEC operator can run their scripts that send
the `arm` messages to the Varex computer.

More details about the above steps can be seen below.

Connecting to the Varex computer with RDP
=========================================

From the MEC DAQ computer, first SSH into psmeclogin with graphics forwarding,
like so:

```bash
ssh -Y <username>@psmeclogin
```

After you have signed in using your password, run the following command:

```bash
xfreerdp -f -u mec-varex@172.21.43.22
```

The `-f` is for fullscreen. This should open up a new RDP window on the MEC
DAQ computer that displays the Varex computer. It is through RDP that you
must start up the command prompt and run `.\run_pylad_client.bat` in order
to run the pylad client. Leave the RDP window open, as previews of the
run data will be displayed using `pylad-viewer` each time a run is performed.

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

MEC Interface with PyLAD
========================

The PyLAD library was designed to be completely controlled by the MEC operator.
The internal way in which the MEC operator controls PyLAD is through the
json `arm` message, which looks like this:

```json
{
    "command": "arm",
    "experiment": "mecl1048223",
    "run_name": "261",
    "num_skip_frames": 101,
    "num_background_frames": 50,
    "num_data_frames": 1,
    "includes_shot_frame": false,
    "num_post_background_frames": 0,
    "gain": 1,
    "binning": 1
}
```

Essentially, the MEC operator communicates the run name (which is used
to create the directory where the files will be stored), the number
of skip frames, background frames, data frames, and post background
frames, whether or not the data includes a shot frame (assumed to be the
final data frame), the gain and the binning.

The numbers of each frame type are used only for counting and labeling
purposes. The frames are expected to come in this order:

1. Skip frames
2. Background frames
3. Data frames
4. Post shot background frames

A single trigger to a detector always results in an immediate frame readout.
Thus, there should be a trigger for each of the above frames. There should
always be at least one skip frame, since the first frame is always
invalid.

As the frames come in, they are saved with a suffix indicating their
type. For example, background frames are saved as `*_background.tiff`,
and data frames are saved as `*_data.tiff`. If any background frames
are taken, after all frames are collected, the median of all background
frames is computed, and the result stored in a file. If any data frames
are taken, then a median background subtraction is automatically performed
(for convenience) and the result is saved with a `*_data_ds.tiff` suffix.
If any background frames were taken in the current run, then the median
of those background frames will be used for the subtraction. If no
background frames were taken in the current run, then the last median
background performed (which is saved in `~/.varex`) will be used to
perform the subtraction. It is very important to make sure that if the
`gain` setting is ever switched, that new background frames are taken,
since the last median background will not work with a new gain setting.

PyLAD and the Varex detectors assume nothing about the timing of the
incoming frames. The timing of frames is completely controlled by the
external trigger. Thus the MEC operator can control the rate at which
the frames are produced, as well as whatever happens to the data while
they are being produced.

A typical setup is that each data frame receives one x-ray pulse. When
only a single x-ray pulse is used for a frame, it is important that
the x-ray pulse does not come during the detector readout (which is
a 66.7 millisecond period of time after every trigger).

However, we do not necessarily need to collect one x-ray pulse per frame.
For example, if a user wishes to collect a YAG flatfield by
collecting frames at 1 Hz while exposing the sample to x-rays at 120 Hz,
it is completely do-able, and only the MEC operator needs to define the
setup where 120 x-ray pulses will be coming per second, while triggers to
the detector only come once per second.
