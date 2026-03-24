#!/usr/bin/env python3
import os
import sys
import time

# Ensure Windows terminal processes UTF-8 and ANSI sequences properly
if os.name == 'nt':
    os.system("chcp 65001 >nul")
    os.system("")

# Configuration
REFRESH_INTERVAL = 2  # Seconds between auto-refreshes if no key
VOLUME_STEP = 5

# Modern ANSI Colors & Styles
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
INVERT = "\033[7m"
BG_CYAN = "\033[46m"
FG_BLACK = "\033[30m"
CLEAR_SCREEN = "\033[2J\033[H"
MOVE_HOME = "\033[H"
HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"
CLEAR_LINE = "\033[K"
ENABLE_MOUSE = "\033[?1000h\033[?1015h\033[?1006h"
DISABLE_MOUSE = "\033[?1000l\033[?1015l\033[?1006l"

FILLED_BAR = "█"
EMPTY_BAR = "░"


class Backend:
    """Abstract base class for OS-specific audio controlling logic."""
    def setup(self): pass
    def get_targets(self): return []
    def get_target_info(self, target): return 0, False
    def set_volume_percent(self, target, percent): pass
    def toggle_mute(self, target): pass


class WindowsBackend(Backend):
    def setup(self):
        from comtypes import CoInitialize
        CoInitialize() 

    def get_targets(self):
        from pycaw.pycaw import AudioUtilities
        
        new_targets = []
        try:
            speakers = AudioUtilities.GetSpeakers()
            master_vol = speakers.EndpointVolume
            new_targets.append({
                'type': 'device',
                'id': 'master',
                'name': 'Master Volume',
                'interface': master_vol
            })
        except Exception:
            pass

        try:
            sessions = AudioUtilities.GetAllSessions()
            for session in sessions:
                if session.Process:
                    pid = session.Process.pid
                    name = session.Process.name()
                    new_targets.append({
                        'type': 'session',
                        'id': str(pid),
                        'name': name.replace('.exe', ''),
                        'interface': session.SimpleAudioVolume
                    })
        except Exception:
            pass
        return new_targets

    def get_target_info(self, target):
        try:
            interface = target['interface']
            if target['type'] == 'device':
                vol = int(interface.GetMasterVolumeLevelScalar() * 100)
                muted = interface.GetMute() == 1
            else:
                vol = int(interface.GetMasterVolume() * 100)
                muted = interface.GetMute() == 1
            return vol, muted
        except:
            return 0, False

    def set_volume_percent(self, target, percent):
        try:
            interface = target['interface']
            is_device = target['type'] == 'device'
            vol_float = max(0.0, min(1.0, float(percent) / 100.0))
            if is_device:
                interface.SetMasterVolumeLevelScalar(vol_float, None)
            else:
                interface.SetMasterVolume(vol_float, None)
        except:
            pass
            
    def toggle_mute(self, target):
        try:
            interface = target['interface']
            new_mute = 0 if (interface.GetMute() == 1) else 1
            interface.SetMute(new_mute, None)
        except:
            pass


class LinuxBackend(Backend):
    # TODO: Implement using `pulsectl` for PipeWire/PulseAudio compatibility.
    pass


class MacOSBackend(Backend):
    # TODO: Implement using `osascript -e "set volume output volume X"`
    pass


def get_backend():
    if sys.platform == "win32":
        return WindowsBackend()
    elif sys.platform.startswith("linux"):
        return LinuxBackend()
    elif sys.platform == "darwin":
        return MacOSBackend()
    else:
        return Backend()


class TerminalInput:
    """Cross-platform non-blocking unbuffered terminal input."""
    def __init__(self):
        self.old_settings = None
        if os.name != 'nt':
            import termios
            import tty
            self.fd = sys.stdin.fileno()
            self.old_settings = termios.tcgetattr(self.fd)
            tty.setraw(self.fd)
        else:
            import ctypes
            self.hStdin = ctypes.windll.kernel32.GetStdHandle(-10)
            self.old_mode = ctypes.c_uint32()
            ctypes.windll.kernel32.GetConsoleMode(self.hStdin, ctypes.byref(self.old_mode))
            new_mode = self.old_mode.value | 0x0200 | 0x0010 | 0x0080
            new_mode &= ~0x0040
            ctypes.windll.kernel32.SetConsoleMode(self.hStdin, new_mode)

    def cleanup(self):
        if self.old_settings is not None:
            import termios
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old_settings)
        elif os.name == 'nt':
            import ctypes
            ctypes.windll.kernel32.SetConsoleMode(self.hStdin, self.old_mode.value)

    def getch(self):
        if os.name == 'nt':
            import msvcrt
            if msvcrt.kbhit():
                key = msvcrt.getch()
                if key in (b'\x00', b'\xe0'):
                    return msvcrt.getch(), True
                if key == b'\x1b':
                    import time
                    time.sleep(0.01)
                    seq = b''
                    while msvcrt.kbhit():
                        seq += msvcrt.getch()
                    if not seq:
                        return b'\x1b', False
                    return b'\x1b' + seq, False
                return key, False
            return None, False
        else:
            import select
            if select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], []):
                key = sys.stdin.read(1).encode('utf-8')
                if key == b'\x1b':
                    import time
                    time.sleep(0.01)
                    seq = b''
                    while select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], []):
                        seq += sys.stdin.read(1).encode('utf-8')
                    if not seq:
                        return b'\x1b', False
                    return b'\x1b' + seq, False
                return key, False
            return None, False


class VolumeMixer:
    def __init__(self):
        self.backend = get_backend()
        self.backend.setup()
        
        self.targets = []
        self.selected_index = 0
        self.view_offset = 0
        self.running = True
        self.startup = True
        self.term_input = None

    def draw_bar(self, volume, muted, width=20):
        if muted:
            bar = DIM + RED + (EMPTY_BAR * width) + RESET
            return f"[{bar}] {RED} MUTED{RESET}"
            
        filled = int(volume / 100 * width)
        
        if volume > 80:
            color = RED
        elif volume > 50:
            color = YELLOW
        else:
            color = GREEN
            
        bar_text = color + (FILLED_BAR * filled) + DIM + (EMPTY_BAR * (width - filled)) + RESET
        percent = f"{volume}%".rjust(4)
        return f"[{bar_text}] {BOLD}{color}{percent}{RESET}"

    def render(self):
        import shutil
        terminal_size = shutil.get_terminal_size((80, 24))
        term_width = max(55, terminal_size.columns)
        term_height = terminal_size.lines
        
        if self.startup:
            sys.stdout.write(CLEAR_SCREEN)
            self.startup = False
        else:
            sys.stdout.write(MOVE_HOME)

        output = []
        
        # Header
        output.append(f" {BOLD}{CYAN}🔊 vmix{RESET} {DIM}— {len(self.targets)} sessions{RESET}{CLEAR_LINE}")
        #output.append(" " + ("━" * (term_width - 2)) + CLEAR_LINE)
        
        # Calculate list height (leave 4 lines for header/footer)
        list_height = max(3, term_height - 5)

        if not self.targets:
            msg = "No audio sessions or devices found."
            output.append(f" {RED}{msg}{RESET}{CLEAR_LINE}")
        else:
            # Paging logic
            if self.selected_index < self.view_offset:
                self.view_offset = self.selected_index
            elif self.selected_index >= self.view_offset + list_height:
                self.view_offset = self.selected_index - list_height + 1
            
            max_offset = max(0, len(self.targets) - list_height)
            self.view_offset = max(0, min(self.view_offset, max_offset))

            name_width = max(22, int(term_width * 0.35))
            bar_width = max(10, term_width - name_width - 18)
            
            end_idx = min(len(self.targets), self.view_offset + list_height)
            
            for i in range(self.view_offset, end_idx):
                target = self.targets[i]
                device_type = "🎧" if target["type"] == "device" else "🔊"
                
                raw_name = f"{device_type} {target['name']}"
                if len(raw_name) > name_width:
                    raw_name = raw_name[:name_width-2] + ".."
                name_cell = raw_name.ljust(name_width)
                
                vol, muted = self.backend.get_target_info(target)
                bar = self.draw_bar(vol, muted, width=bar_width)
                
                # Scrollbar character logic
                scroll_char = " "
                if len(self.targets) > list_height:
                    # Simple scrollbar column
                    total = len(self.targets)
                    sb_start = int((self.view_offset / total) * list_height)
                    sb_end = int(((self.view_offset + list_height) / total) * list_height)
                    if sb_start <= (i - self.view_offset) < sb_end:
                        scroll_char = "┃"
                    else:
                        scroll_char = "│"

                if i == self.selected_index:
                    row_body = f"{CYAN} > {RESET}{BG_CYAN}{FG_BLACK}{BOLD}{name_cell}{RESET} {bar} {DIM}{scroll_char}{RESET}{CLEAR_LINE}"
                    output.append(row_body)
                else:
                    row_body = f"   {DIM}{name_cell}{RESET} {bar} {DIM}{scroll_char}{RESET}{CLEAR_LINE}"
                    output.append(row_body)

        # Footer / Info line
        #output.append(" " + ("━" * (term_width - 2)) + CLEAR_LINE)
        paging_info = ""
        if self.targets:
            paging_info = f" {DIM}[{self.selected_index + 1}/{len(self.targets)}]{RESET}"
        
        nav_text = f" {BOLD}↑/↓/🖱️{RESET} Nav {DIM}|{RESET} {BOLD}←/→{RESET} Vol {DIM}|{RESET} {BOLD}M{RESET} Mute {DIM}|{RESET} {BOLD}Q{RESET} Quit{paging_info}"
        output.append(CLEAR_LINE)
        output.append(nav_text + CLEAR_LINE)
            
        sys.stdout.write("\n".join(output) + "\033[J")
        sys.stdout.flush()

    def handle_input(self):
        start_time = time.time()
        key = None
        extended = False
        
        while time.time() - start_time < REFRESH_INTERVAL:
            key, extended = self.term_input.getch()
            if key is not None:
                break
            time.sleep(0.05)
            
        if not key:
            self.targets = self.backend.get_targets()
            return
            
        target = self.targets[self.selected_index] if self.targets else None

        if key in (b'q', b'Q', b'\x1b'):
            self.running = False
        elif isinstance(key, bytes) and key.startswith(b'\x1b[<'):
            # Mouse handling
            parts = key[3:].split(b';')
            if len(parts) >= 1:
                event_type = parts[0]
                if event_type == b'64':
                    self.selected_index = max(0, self.selected_index - 1)
                elif event_type == b'65':
                    self.selected_index = min(len(self.targets) - 1, self.selected_index + 1)
        elif key in (b'\x1b[A', b'A') or (extended and key == b'H'): # Up Arrow
            self.selected_index = (self.selected_index - 1) % len(self.targets)
        elif key in (b'\x1b[B', b'B') or (extended and key == b'P'): # Down Arrow
            self.selected_index = (self.selected_index + 1) % len(self.targets)
        elif key in (b'\x1b[C', b'C') or (extended and key == b'M') or key in (b'.', b'>'): # Right Arrow / Volume Up
            if target:
                vol, _ = self.backend.get_target_info(target)
                self.backend.set_volume_percent(target, vol + VOLUME_STEP)
        elif key in (b'\x1b[D', b'D') or (extended and key == b'K') or key in (b',', b'<'): # Left Arrow / Volume Down
            if target:
                vol, _ = self.backend.get_target_info(target)
                self.backend.set_volume_percent(target, vol - VOLUME_STEP)
        elif not extended and key in (b'm', b'M'): 
            if target:
                self.backend.toggle_mute(target)
        elif not extended and key in (b'r', b'R'):
            self.targets = self.backend.get_targets()

    def start(self):
        sys.stdout.write(HIDE_CURSOR + ENABLE_MOUSE)
        sys.stdout.flush()
        self.targets = self.backend.get_targets()
        self.term_input = TerminalInput()
        try:
            while self.running:
                self.render()
                self.handle_input()
        finally:
            self.term_input.cleanup()
            sys.stdout.write(SHOW_CURSOR + DISABLE_MOUSE)
            
            if self.targets:
                import shutil
                terminal_size = shutil.get_terminal_size((80, 24))
                list_height = max(3, terminal_size.lines - 5)
                drawn_lines = min(len(self.targets), list_height) + 5
                sys.stdout.write(f"\033[{drawn_lines}B")
            sys.stdout.write("\n")
            sys.stdout.flush()


if __name__ == "__main__":
    mixer = VolumeMixer()
    mixer.start()
