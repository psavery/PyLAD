PyLAD
=====

Python for Large Area Detectors.

High-level Python interface for the XISL library, used by Varex detectors.

![pylad-viewer-example](https://github.com/user-attachments/assets/3195246d-6adb-4031-82a5-a303b601bb09)

*Image taken using [PyLAD-Viewer](https://github.com/psavery/pylad-viewer)*

This software was used at SLAC National Accelerator Laboratory at MEC during experiments in early 2025.

## Description

PyLAD is a Python interface for interacting with the XISL C library. It was designed to be able to control
multiple Varex detectors simultaneously, including arming, collecting images, identifying image types (dark,
ambient, data, etc.), and writing them out to appropriately named files. PyLAD was designed to automate as much
as possible so that users could collect as many shots as possible during beamtime.

The software was designed such that an [Instrument](https://github.com/psavery/PyLAD/blob/main/pylad/instrument/instrument.py)
initializes all detectors, maintains references to them, and provides API for interacting with all detectors,
and a [Detector](https://github.com/psavery/PyLAD/blob/main/pylad/instrument/detector.py)
provides API for interacting with an individual detector. 

Four main types of images were defined, in this specific order: skip frames (a number of frames to skip in order to ensure the detector
is fully equilibrated before data collection), dark images (no x-rays), data images (with x-rays), and post-shot
dark images (no x-rays). Trigger counting is used to determine the type of each image, and how to handle it.
Dark background subtracted files are automatically created either using the median of all dark files from the
current run, or the median of all dark files from the most recent run.

Because the Varex detectors go into idle mode after about ~20 seconds of inactivity, it is very important
to appropriately time the arming of the detectors so that the x-rays come during that window. Automating
the timing is significantly easier than manually doing so. Details of how we automated the timing at
MEC can be found [here](https://github.com/psavery/PyLAD/blob/main/scripts/MEC/REAMDE.md).

During the MEC experiments, we used the [PyLAD-Viewer](https://github.com/psavery/pylad-viewer) to
automatically and quickly display the results of each x-ray event, in order to enable quick decision-making
for users during beamtime.

### Config File

A config file in json format may be utilized to define all details of the run.
An example is as follows:

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

## Installing

This software must be installed from source. The repository must first by either
downloaded or cloned as follows:

```bash
git clone https://github.com/psavery/pylad
```

The code will be present in the `pylad` directory.

### Conda

We recommend creating and activating a conda environment to use with this
software. If you will also use [PyLAD-Viewer](https://github.com/psavery/pylad-viewer), you
should install `pylad-viewer` in the same conda environment.

After setting up the conda environment, all dependencies must be installed, like so:

```bash
conda install -c conda-forge numpy pillow
```

Next, `pylad` must be installed as follows:

```bash
pip install --no-build-isolation --no-deps -U -e pylad
```

This environment can then be used with the `pylad-client`, as detailed in the
[MEC Documentation](https://github.com/psavery/PyLAD/blob/main/scripts/MEC/REAMDE.md).

If you wish to run `pylad` manually, you may run `pylad <json_config>`, where
`<json_config>` is a json config file, which may appear as detailed in the
[Config File](#config-file) section.

The output files will be written to the same directory as the json config file.

## PyLAD Client and Relay Server

During the first experiments, we set up a relay server to relay messages between
the DAQ and the Varex computer. The relay server also automatically copied the files
from the Varex computer to their final destination on the data server.

We also set up a pylad client to automatically set up the Varex detectors, collect
and save images, and display the resulting output when an `arm` signal was received
by the DAQ. Details of this setup may be found [here](https://github.com/psavery/PyLAD/blob/main/scripts/MEC/REAMDE.md).
