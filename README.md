# 🔊 vmix - Native Terminal Volume Mixer

`vmix` is a beautifully lightweight, ultra-fast Python Terminal User Interface (TUI) for actively managing your operating system's audio volume—both your Master Output and individual application sessions concurrently.

By securely hooking into core OS audio frameworks directly via memory interfaces, `vmix` achieves **flicker-free rendering**, flawless alignment, and **zero-latency volume increments**, avoiding the overhead or bug hazards of external command-line `.exe` dependencies. 

![vmix Example Dashboard](https://github.com/placeholder-demo/vmix/raw/main/screenshots/demo.png)

## ✨ Features
- **Ultra-Fast Backend:** Bypasses console wrappers entirely to map straight to the COM audio backend.
- **Real-Time Synchronous Meters:** Live audio statuses exist for every process dynamically running on your system, not just the selected track. 
- **Pure Terminal Interface:** Draws directly with standard ANSI escapes using non-blocking terminal polling.
- **Cross-Platform Foundation:** Built to support an abstracted Backend pipeline ready for Windows, Linux (PulseAudio/PipeWire), and macOS.

## 🚀 Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/vmix.git
   cd vmix
   ```

2. **Install core dependencies:**
   ```bash
   pip install psutil
   ```

3. **Install OS-Specific Modules:**
   - **For Windows:** Requires Python Core Audio setup.
     ```bash
     pip install pycaw comtypes
     ```
   - **For Linux:** *(Backend integration planned via `pulsectl`)*
   - **For macOS:** *(Backend integration planned via `pyobjc` / Native Osascript)*

## 🎮 Usage 

Run the tool right from your console:
```bash
python vmix.py
```

### Controls:
- `Up / Down` (↑/↓): Navigate sessions
- `Left / Right` (←/→) or `, / .`: Decrease/Increase volume by 5%
- `M`: Toggle mute
- `R`: Force refresh the target list manually
- `Q` or `Esc`: Quit out of the application

## 🛠 Project Structure & Contributing
The project is decoupled securely to welcome open-source contributions. 
- **`vmix.py`** contains the master `VolumeMixer` TUI class.
- The **`Backend`** parent interface enforces OS abstraction APIs natively. Developers can create new modules inheriting `Backend` (e.g., `LinuxBackend`) to push feature parity across operating systems. 

## ⚖️ License
This project is open-sourced under the MIT License.
