# Sweepy — /vg/'s Uma Musume Bot

This is a fork for Sweepy with a rewrite taken from [waivegames-oss/umamusume-sweepy](https://github.com/waivegames-oss/umamusume-sweepy). I'm not pulling in most upstream Sweepy changes by default since most of the time the changes are broken and untested. Feature parity may be delayed or I may not even pull in some changes made if they're too low quality. Half the time you're better off not updating from the upstream repo.

Turn on auto-use items for MANT or the bot will break. You need to adjust the configurations as well but I don't have any good recommendations. Enable `log_training_data` in `config.yaml` and use `analyze_trainings.py` to see what it's doing.

## Features Not Implemented Yet

- Option to skip races for training still does not take into account the race grade (G1/G2/G3).
- Run state is not saved fully when the bot stops currently. This is implemented upstream (poorly) but I'm going to redo it properly.

## Known Bugs

- URA/Unity are not tested and may not work. This only works for MANT.

## Added Features / Changes

Here's what's changed so far that's worth noting, most of the new bot features have options to toggle them off in the UI:

- Bot now supports retrying specific races in MANT, you can select which races to retry in the UI.
  - It will only retry up to configured clock limit. By default no races are retried, you must enable it yourself.
- Bot will save two T2/T3 megaphones for summer training instead of wasting them on terrible training.
- Bot buys the first T1/T2 megaphone on the first shop turn if available and uses it.
- Bot now checks training **before** using energy items, so it won't waste energy items on bad training (skips training in the bottom 35th percentile).
- Bot now properly goes to race even if there's no energy items in MANT (this was a bug they wouldn't fix).
- Bot now prioritizes buying scrolls/manuals in the shop instead of waiting until the last minute. Notepads are not included in this.
- Bot no longer uses cupcakes to raise mood if it's not going to train and relies on racing first to raise mood (unless it's too low).
- Bot now only uses Royal Kale Juice if it has a cupcake available to use or if mood is already Great without no other energy items available.
- Bot will now buy cupcakes to match the number of Royal Kale Juices it has, up to a maximum of 2.
- Bot will try to race again if it loses the Debut race as soon as it's able to do so.
- Added a feature under `log_training_data` in `config.yaml` to dump all relevant internal turn data into `training_data.jsonl`.
  - You can use `analyze_trainings.py` to do a high-level check of what the bot was doing and if it was making good decisions.
  - Note: Not every turn is recorded on certain paths, so you may miss some information (due to "fast" path logic).
- Reverted some awful code written for template matching that was "faster" but broke randomly because it rejected matches too aggressively.
  - This causes some event handling to slow down sometimes, but it's better than the bot picking the wrong choice.
- Updated the MANT tier defaults because I was tired of updating the tiers and moving items around to make them sane.
- Fixed some bugs with TS Climax races where it tried to go to race early, wouldn't use hammer cleats, and other weirdness.
- Fixed a bug with megaphone turn tracking that was causing it to double decrement and messing up the turn logic.
- Fixed a bug with using too many energy items and amulets because it wasn't checking the new failure rate.
- Safety click checks have been added for Rest and Recreation. This was due to the old code using unsafe areas to click on.
- You can now install the Python dependencies in `venv` and just run `start.bat` without polluting your core Python install.

This list does not include the changes from [waivegames-oss/umamusume-sweepy](https://github.com/waivegames-oss/umamusume-sweepy) which were primarily fixes for event handling and the MANT shop.

### A Umamusume bot that handles all aspects of gameplay including training, races, events, skill purchasing, and starting runs. 

MANT support is a work in progress. It works but it's still mainly putting out S ranks. The bot is still just terrible at picking the proper trainings and I haven't demystified the meaning of stat limits or how to get it to properly pick the best trainings. I think it's overcomplicated and probably needs to be made simpler but I'm avoiding touching that for now.

![Uma Musume Auto Trainer](docs/main.png)

---

## Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Emulator Setup](#emulator-setup)
- [Configuration](#configuration)
- [Stat Caps Guide](#stat-caps-guide)
- [GPU Acceleration](#gpu-acceleration)
- [Troubleshooting](#troubleshooting)
- [Changelog](#changelog)
- [Credits](#credits)

---

## Features

### Fully Automated Training
- Completely hands-off operation for days of continuous training
- Automatic TP recovery and run initialization
- Handles disconnections, crashes, and game updates automatically
- Background play support via mobile emulators
- Able to generate over a dozen 3* parents a week if left to run

### Scenario Support
- URA Finals scenario
- Unity Cup (Aoharu)
- partial Mant

### Comprehensive Customization
- Literally everything that can be detected is detected and used for customization.
- Skill hint levels, Energy Changes, Stat gains....
- Hundreds of settings for you to tune the bot to your liking.
- This allows gimick cards like Fuku with energy cost reduction/training effectiveness to be utilized fully


---

## Requirements

- Python 3.10
- Visual C++ Redistributable ([Download](https://aka.ms/vs/17/release/vc_redist.x64.exe))
- Android emulator (MuMu Player recommended) bluestacks sucks dont use it it will break screenshots for reasons i dont understand

---

## Installation

### Step 1: Clone the Repository

```bash
git clone https://github.com/SweepTosher/umamusume-sweepy
cd umamusume-sweepy
```

### Step 2: Install Python 3.10 And VC++

```bash
winget install -e --id Python.Python.3.10
Visual C++ Redistributable: https://aka.ms/vs/17/release/vc_redist.x64.exe
```

### Step 3: Set up the venv

```bash
python -m venv venv
./venv/Scripts/python -m pip install --upgrade pip
```

If you screw up dependencies, you can `rm -rf venv/` and do this again.

### Step 4: Run the Bot via start.bat

```bash
call start.bat
```

You can also just run it directly from the Windows UI. Do **NOT** run this as admin; there is no need for it and its unsafe for you.

---

## Emulator Setup

### Display Settings
- **Resolution**: 720 x 1280 (Portrait mode)
- **DPI**: 180
- **FPS**: 30 or higher (do not set below 30)

### Graphics Settings
- **Rendering**: Standard (not Simple/Basic)
- **ADB**: Must be enabled in emulator settings

### Supported Emulators
- MuMu Player (try not to use anything else)
---

## Configuration

1. Set graphics to `Standard` in-game (not `Basic`).    
2. Manually select your Uma Musume, Legacy Uma, and Support Cards before starting.    
3. Edit your runtime in main.py (default is 20 hours a day).     
---

## Stat Caps Guide

Stat caps control how the bot prioritizes training based on current stat values.

### Default Configuration
For normal operation, set large values for all stat caps to always select the optimal training:

![Default Stat Caps](docs/statCaps.png)

### Custom Caps for Specific Builds
If a stat maxes out too early (e.g., 1000+ speed before second summer), adjust caps accordingly:

![Speed Cap Example](docs/capSpeed.png)

### How Stat Caps Work
- **Soft Cap**: At 70%, 80%, 90% of target, applies -10%, -20%, -30% score penalty respectively
- **Hard Cap**: At 95% or higher, score becomes 0 (indicates deck optimization needed)

Adjusting your deck composition is recommended over relying on artificial stat caps.

---

## GPU Acceleration

Optional NVIDIA GPU acceleration for improved performance.

### Prerequisites
1. NVIDIA GPU with current drivers
2. CUDA Toolkit 11.8 ([Download](https://developer.nvidia.com/cuda-11-8-0-download-archive))
3. cuDNN v8.6.0 for CUDA 11.x ([Download](https://developer.nvidia.com/rdp/cudnn-archive))

### Installation Steps

1. Extract cuDNN and copy contents to CUDA installation folders:
   ```
   cudnn-windows-x86_64-8.6.0.163_cuda11-archive\bin
   -> C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v11.8\bin
   ```
   Repeat for all cuDNN folders (bin, include, lib).

2. Add to system PATH:
   - `C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v11.8\bin`
   - `C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v11.8\libnvvp`
   - `C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v11.8`

3. Copy and rename zlib:
   ```
   C:\Program Files\NVIDIA Corporation\Nsight Systems 2022.4.2\host-windows-x64\zlib.dll
   -> C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v11.8\bin\zlibwapi.dll
   ```

4. Install GPU version of PaddlePaddle:
   ```bash
   pip uninstall paddlepaddle
   pip install paddlepaddle-gpu==2.6.2 -i https://pypi.tuna.tsinghua.edu.cn/simple
   ```

5. Update `requirements.txt` line 71:
   ```
   paddlepaddle-gpu==2.6.2
   ```

6. Reboot system.

---

## Troubleshooting

### Bot Stuck in Menu
Disable "Keep alive in background" in emulator settings.

### ADB Connection Fails
Restart your machine

### Stats Not Showing in Scoring
Install or reinstall Visual C++ Redistributable:
- [Download vc_redist.x64.exe](https://aka.ms/vs/17/release/vc_redist.x64.exe)

![Stats Display](https://github.com/user-attachments/assets/1f68af35-cf9d-41ce-9392-c26ecf83cc70)

---

## Credits

- **Original Repository**: [UmamusumeAutoTrainer](https://github.com/shiokaze/UmamusumeAutoTrainer) by [Shiokaze](https://github.com/shiokaze)
- **Global Server Port**: [UmamusumeAutoTrainer-Global](https://github.com/BrayAlter/UAT-Global-Server) by [BrayAlter](https://github.com/BrayAlter)

---

![Uma Musume](docs/umabike.gif)
![Uma Musume](docs/flower.gif)
<img width="190" height="140" alt="image" src="https://github.com/user-attachments/assets/a376b9e0-832e-45ea-add4-499a9f76a284" />
<img width="190" height="158" alt="image" src="https://github.com/user-attachments/assets/428a7704-0729-4dc3-890f-246fb0a94774" />
<img width="190" height="140" alt="image" src="https://github.com/user-attachments/assets/65edac1a-91c0-4559-8393-7432418afa18" />
<img width="190" height="140" alt="image" src="https://github.com/user-attachments/assets/3193d3ce-2a3a-4a77-9ed6-c04702083b60" />
<img width="190" height="140" alt="image" src="https://github.com/user-attachments/assets/d58f6376-76c7-455e-a16d-9bb9d92db969" />
<img width="190" height="140" alt="image" src="https://github.com/user-attachments/assets/d097751f-966f-4f3f-ba5b-3608cac6bdbe" />
<img width="190" height="140" alt="image" src="https://github.com/user-attachments/assets/671eb304-cb0b-4f02-9023-ea313df2f987" />
<img width="190" height="140" alt="image" src="https://github.com/user-attachments/assets/f1ecf7d6-1e18-45d6-8143-66b877d9c786" />
<img width="190" height="140" alt="image" src="https://github.com/user-attachments/assets/94ea9609-54db-4322-a0f3-9168a70932e0" />
<img width="190" height="140" alt="image" src="https://github.com/user-attachments/assets/d64d2197-217f-40c5-a57e-3ccd5c868e2d" />
<img width="190" height="140" alt="image" src="https://github.com/user-attachments/assets/cacd2cf3-b880-4b1e-8818-af33a30bcf38" />
<img width="190" height="140" alt="image" src="https://github.com/user-attachments/assets/3bdd80ec-cb77-4637-9f61-e3f8fab8d85d" />
<img width="235" height="226" alt="image" src="https://github.com/user-attachments/assets/ffb9960a-347d-4d7f-8c0d-57ff96f72b6a" />
<img width="317" height="317" alt="image" src="https://github.com/user-attachments/assets/61c4c0dd-85bc-4517-84c1-021fcf5d47fa" />
<img width="428" height="605" alt="image" src="https://github.com/user-attachments/assets/07ca8a7f-3f89-4667-a5c6-d50ab5b10fe3" />

