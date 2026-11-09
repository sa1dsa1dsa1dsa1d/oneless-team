import pyaudiowpatch as pyaudio
import numpy as np
import sys
import pygame
import math
import ctypes

# --- Настройки ---
WINDOW_WIDTH = 1366   
WINDOW_HEIGHT = 100  
FPS = 90              
CHUNK = 256           
FFT_SIZE = 2048       
FORMAT = pyaudio.paInt16
CHANNELS = 2

FREQ_MIN = 20
FREQ_MAX = 20000  
BAR_COUNT = 128

# --- ЦВЕТА И ГРАДИЕНТЫ ---
current_theme = 0 

def lerp_color(c1, c2, t):
    r = int(c1[0] + (c2[0] - c1[0]) * t)
    g = int(c1[1] + (c2[1] - c1[1]) * t)
    b = int(c1[2] + (c2[2] - c1[2]) * t)
    r = max(0, min(255, r))
    g = max(0, min(255, g))
    b = max(0, min(255, b))
    return (r, g, b)

def make_spectrum_lut(n=64):
    stops = [
        (0.0, (10, 5, 20)), (0.15, (40, 0, 80)), (0.35, (120, 0, 180)),
        (0.55, (220, 20, 150)), (0.75, (255, 80, 40)), (1.0, (255, 240, 100))
    ]
    lut = []
    for i in range(n):
        t = i / (n - 1)
        for k in range(len(stops) - 1):
            t0, c0 = stops[k]
            t1, c1 = stops[k+1]
            if t0 <= t <= t1:
                f = (t - t0) / (t1 - t0)
                lut.append(lerp_color(c0, c1, f))
                break
    return lut

SPEC_LUT = make_spectrum_lut(64)

def get_colors(theme):
    if theme == 0: # Темная
        return {
            "bg": (5, 5, 8), "grid": (40, 45, 55), "text": (200, 200, 200),
            "waterfall_bg": (10, 10, 15), "wave": (150, 100, 255),
            "osc": (255, 255, 255), "cube": (200, 0, 255),
            "btn": (40, 40, 50), "btn_hover": (80, 80, 100),
            "btn_text": (255, 255, 255), "clip": (160, 80, 255),
            "lufs_bar": (140, 180, 255), "lufs_text": (255, 255, 255), "lufs_bg": (140, 180, 255), "lufs_bg_text": (0, 0, 0),
            "meter": (140, 180, 255),
            "scope_dots": (160, 80, 255),    # Фиолетовые точки
            "bar_bg": (30, 30, 40)           # Темный фон индикаторов
        }
    else: # Светлая
        return {
            "bg": (250, 250, 250), "grid": (180, 180, 180), "text": (50, 50, 50),
            "waterfall_bg": (240, 240, 240), "wave": (100, 50, 200),
            "osc": (0, 0, 0), "cube": (50, 0, 150),
            "btn": (200, 200, 200), "btn_hover": (150, 150, 150),
            "btn_text": (0, 0, 0), "clip": (100, 50, 150),
            "lufs_bar": (100, 50, 200), "lufs_text": (0, 0, 0), "lufs_bg": (100, 50, 200), "lufs_bg_text": (255, 255, 255),
            "meter": (100, 50, 200),
            "scope_dots": (100, 50, 200),    # Темно-фиолетовые
            "bar_bg": (220, 220, 220)
        }

def get_loopback_device(p):
    try:
        wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
    except OSError:
        sys.exit(1)
    default_speakers = p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
    if default_speakers["isLoopbackDevice"]:
        return default_speakers
    for loopback in p.get_loopback_device_info_generator():
        if default_speakers["name"] in loopback["name"]:
            return loopback
    sys.exit(1)

def project_3d_to_2d(x, y, z, center_x, center_y, fov=400):
    if z == 0: z = 0.1
    scale = fov / (z + fov)
    return center_x + x * scale, center_y + y * scale

def rotate_x(angle):
    return np.array([[1, 0, 0], [0, math.cos(angle), -math.sin(angle)], [0, math.sin(angle), math.cos(angle)]])

def rotate_y(angle):
    return np.array([[math.cos(angle), 0, math.sin(angle)], [0, 1, 0], [-math.sin(angle), 0, math.cos(angle)]])

def rotate_z(angle):
    return np.array([[math.cos(angle), -math.sin(angle), 0], [math.sin(angle), math.cos(angle), 0], [0, 0, 1]])

def start_drag_window():
    hwnd = pygame.display.get_wm_info()["window"]
    ctypes.windll.user32.ReleaseCapture()
    ctypes.windll.user32.SendMessageW(hwnd, 0xA1, 0x2, 0)

def get_wave_color(amplitude, theme):
    if theme == 0:
        if amplitude < 0.2: return (60, 20, 100)
        elif amplitude < 0.4: return (100, 50, 200)
        elif amplitude < 0.6: return (150, 100, 255)
        elif amplitude < 0.8: return (200, 150, 255)
        else: return (255, 255, 255)
    else:
        if amplitude < 0.2: return (150, 150, 250)
        elif amplitude < 0.4: return (100, 50, 200)
        elif amplitude < 0.6: return (80, 0, 150)
        elif amplitude < 0.8: return (50, 0, 100)
        else: return (0, 0, 0)

def draw_big_cube(screen, center_x, center_y, rx, ry, rz, theme):
    scale = 25.0
    vertices = np.array([
        [-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1],
        [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1]
    ]) * scale
    
    faces = [
        [0, 1, 2], [0, 2, 3], [4, 5, 6], [4, 6, 7],
        [0, 1, 5], [0, 5, 4], [2, 3, 7], [2, 7, 6],
        [0, 3, 7], [0, 7, 4], [1, 2, 6], [1, 6, 5]
    ]
    
    rot_mat = rotate_x(rx) @ rotate_y(ry) @ rotate_z(rz)
    rotated_verts = vertices @ rot_mat.T
    
    projected = []
    for v in rotated_verts:
        px, py = project_3d_to_2d(v[0], v[1], v[2] + 150, center_x, center_y, fov=200)
        projected.append((int(px), int(py)))
        
    base_color = np.array([60, 0, 150]) if theme == 0 else np.array([150, 100, 255])
    light_dir = np.array([0.3, -0.5, -0.8])
    light_dir = light_dir / np.linalg.norm(light_dir)

    face_depths = []
    for face in faces:
        avg_z = sum(rotated_verts[i][2] for i in face) / 3
        face_depths.append((avg_z, face))
    face_depths.sort(key=lambda x: x[0])

    for avg_z, face in face_depths:
        v1 = rotated_verts[face[1]] - rotated_verts[face[0]]
        v2 = rotated_verts[face[2]] - rotated_verts[face[0]]
        normal = np.cross(v1, v2)
        norm_len = np.linalg.norm(normal)
        if norm_len > 0: normal = normal / norm_len
        
        intensity = max(0.2, min(1.0, np.dot(normal, light_dir) + 0.5))
        color = (int(base_color[0] * intensity), int(base_color[1] * intensity), int(base_color[2] * intensity))
        
        points = [projected[i] for i in face]
        pygame.draw.polygon(screen, color, points)
        pygame.draw.polygon(screen, (0, 0, 0) if theme == 0 else (255, 255, 255), points, 1)

def main():
    global current_theme
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.NOFRAME)
    pygame.display.set_window_position((0, 0))
    clock = pygame.time.Clock()
    
    font = pygame.font.SysFont("consolas", 8)
    font_btn = pygame.font.SysFont("consolas", 12, bold=True)
    font_lufs_num = pygame.font.SysFont("consolas", 12, bold=True)
    font_lufs_val = pygame.font.SysFont("consolas", 18, bold=True)

    p = pyaudio.PyAudio()
    dev = get_loopback_device(p)
    rate = int(dev["defaultSampleRate"])
    
    stream = p.open(
        format=FORMAT, channels=CHANNELS, rate=rate,
        input=True, input_device_index=dev["index"], frames_per_buffer=CHUNK
    )

    w_meter = 150                 
    w_waterfall = 150  
    w_cube = 200                  
    
    btn_w, btn_h = 25, 20
    btn_close_rect = pygame.Rect(WINDOW_WIDTH - btn_w - 5, 5, btn_w, btn_h)
    btn_min_rect = pygame.Rect(WINDOW_WIDTH - btn_w*2 - 10, 5, btn_w, btn_h)
    theme_btn_rect = pygame.Rect(135, 8, 20, 12)

    w_remaining = WINDOW_WIDTH - 35 - w_meter - w_waterfall - w_cube
    w_each = w_remaining // 4
    
    w_wave, w_osc, w_scope, w_spec = w_each, w_each, w_each, w_each

    spec_x_start = w_wave + w_osc + w_scope + 30
    spec_rect = pygame.Rect(spec_x_start, 5, w_spec, WINDOW_HEIGHT - 10)
    
    cube_x = WINDOW_WIDTH - w_cube - 5
    cube_rect = pygame.Rect(cube_x, 5, w_cube, WINDOW_HEIGHT - 10)
    
    wave_rect = pygame.Rect(5, 5, w_wave, WINDOW_HEIGHT - 10)
    
    osc_x_start = 10 + w_wave
    osc_rect = pygame.Rect(osc_x_start, 5, w_osc, WINDOW_HEIGHT - 10)
    
    waterfall_rect = pygame.Rect(0, 0, w_waterfall, WINDOW_HEIGHT - 10)

    is_log_scale = True 
    wave_mode = 0 
    osc_mode = 1      # Зафиксирован TRIGGER
    waterfall_mode = 0 

    SPECTRUM_BARS = 128 
    freqs = np.fft.rfftfreq(FFT_SIZE, 1.0 / rate) 
    
    smooth_spectrum = np.zeros(SPECTRUM_BARS)
    peak_hold = np.zeros(SPECTRUM_BARS)
    fft_buffer = np.zeros(FFT_SIZE) 
    
    waterfall_surface = pygame.Surface((w_waterfall, WINDOW_HEIGHT - 10))
    waterfall_surface.fill(get_colors(current_theme)["waterfall_bg"])
    
    wave_surface = pygame.Surface((w_wave, WINDOW_HEIGHT - 10))
    wave_surface.fill(get_colors(current_theme)["bg"])
    
    osc_buffer = np.zeros(4096)
    agc_gain = 1.0

    rx, ry, rz = 0.0, 0.0, 0.0
    is_active = False

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT: running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE: running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    if btn_close_rect.collidepoint(event.pos):
                        running = False
                    elif btn_min_rect.collidepoint(event.pos):
                        pygame.display.iconify() 
                    elif theme_btn_rect.collidepoint(event.pos):
                        current_theme = 1 if current_theme == 0 else 0
                        C_new = get_colors(current_theme)
                        wave_surface.fill(C_new["bg"])
                        waterfall_surface.fill(C_new["waterfall_bg"])
                    elif wave_rect.collidepoint(event.pos):
                        wave_mode = 1 if wave_mode == 0 else 0
                    elif waterfall_rect.collidepoint(event.pos):
                        waterfall_mode = 1 if waterfall_mode == 0 else 0
                    else:
                        start_drag_window()

        C = get_colors(current_theme)
        
        try:
            data = stream.read(CHUNK, exception_on_overflow=False)
            audio_data = np.frombuffer(data, dtype=np.int16)
            
            if CHANNELS == 2:
                left_channel = audio_data[::2].astype(np.float32)
                right_channel = audio_data[1::2].astype(np.float32)
                mono_data = (left_channel + right_channel) / 2.0
            else:
                mono_data = audio_data.astype(np.float32)
                left_channel = right_channel = mono_data

            peak_amplitude = np.max(np.abs(mono_data)) / 32768.0 * 100.0
            rms = np.sqrt(np.mean(mono_data**2))
            rms_db = 20 * np.log10(rms / 32768.0 + 1e-10)
            
            is_active = rms_db > -50
            
            current_peak = np.max(np.abs(mono_data)) / 32768.0
            if current_peak > 0.01:
                agc_gain = 1.0 / current_peak
                agc_gain = min(agc_gain, 10.0)
            else:
                agc_gain = 1.0
                
            osc_buffer = np.roll(osc_buffer, -len(mono_data))
            osc_buffer[-len(mono_data):] = mono_data

            fft_buffer = np.roll(fft_buffer, -len(mono_data))
            fft_buffer[-len(mono_data):] = mono_data
                
            if is_active:
                window_fn = np.hanning(FFT_SIZE)
                fft_result = np.fft.rfft(fft_buffer * window_fn)
                fft_magnitude = np.abs(fft_result)

                ref = 32768.0 * FFT_SIZE / 4.0
                mag_db = 20 * np.log10(fft_magnitude / ref + 1e-10)

                peak_idx = np.argmax(fft_magnitude)
                peak_freq = freqs[peak_idx]
                peak_db = max(-99.0, mag_db[peak_idx])

                bar_centers = np.logspace(np.log10(FREQ_MIN), np.log10(FREQ_MAX), SPECTRUM_BARS)
                bar_centers = np.clip(bar_centers, freqs[1], freqs[-1])

                spectrum_db = np.zeros(SPECTRUM_BARS)
                for i in range(SPECTRUM_BARS):
                    lo = bar_centers[i-1] * 0.9 if i > 0 else FREQ_MIN
                    hi = bar_centers[i+1] * 1.1 if i < SPECTRUM_BARS - 1 else FREQ_MAX
                    idx = np.where((freqs >= lo) & (freqs < hi))[0]
                    if len(idx) > 0:
                        power = np.mean(fft_magnitude[idx] ** 2)
                        spectrum_db[i] = 10 * np.log10(power / ref**2 + 1e-10)
                    else:
                        spectrum_db[i] = -120.0

                spectrum = np.clip((spectrum_db + 70) / 60, 0, 1)

                attack_mask = spectrum > smooth_spectrum
                smooth_spectrum[attack_mask] = smooth_spectrum[attack_mask] * 0.3 + spectrum[attack_mask] * 0.7
                smooth_spectrum[~attack_mask] = smooth_spectrum[~attack_mask] * 0.85 + spectrum[~attack_mask] * 0.15

                if SPECTRUM_BARS > 2:
                    smoothed = smooth_spectrum.copy()
                    smoothed[1:-1] = (smooth_spectrum[:-2] + smooth_spectrum[1:-1] + smooth_spectrum[2:]) / 3.0
                    smooth_spectrum = smoothed

                peak_hold = np.maximum(peak_hold - 0.005, smooth_spectrum)

        except Exception:
            pass
            
        # ================= ВОЛНА =================
        shift_x = 2
        wave_surface.scroll(-shift_x, 0)
        pygame.draw.rect(wave_surface, C["bg"], (w_wave - shift_x, 0, shift_x, WINDOW_HEIGHT - 10))
        
        if 'mono_data' in locals() and len(mono_data) > 0:
            if wave_mode == 0:
                for i in range(shift_x):
                    idx = len(mono_data) - shift_x + i
                    if idx < len(mono_data):
                        val = (mono_data[idx] / 32768.0) * agc_gain
                        val = max(-1.0, min(1.0, val))
                        amp = abs(val)
                        wave_color = get_wave_color(amp, current_theme)
                        
                        y_center = (WINDOW_HEIGHT - 10) // 2
                        y_amp = int(val * ((WINDOW_HEIGHT - 10) // 2 - 5))
                        pygame.draw.line(wave_surface, wave_color, 
                                         (w_wave - shift_x + i, y_center - y_amp), 
                                         (w_wave - shift_x + i, y_center + y_amp), 1)
            else:
                for i in range(shift_x):
                    idx = len(mono_data) - shift_x + i
                    if idx < len(mono_data):
                        l_val = (left_channel[idx] / 32768.0) * agc_gain
                        r_val = (right_channel[idx] / 32768.0) * agc_gain
                        l_val = max(-1.0, min(1.0, l_val))
                        r_val = max(-1.0, min(1.0, r_val))
                        
                        l_center = (WINDOW_HEIGHT - 10) // 4
                        l_amp = int(l_val * ((WINDOW_HEIGHT - 10) // 4 - 5))
                        pygame.draw.line(wave_surface, get_wave_color(abs(l_val), current_theme), 
                                         (w_wave - shift_x + i, l_center - l_amp), 
                                         (w_wave - shift_x + i, l_center + l_amp), 1)
                        
                        r_center = 3 * (WINDOW_HEIGHT - 10) // 4
                        r_amp = int(r_val * ((WINDOW_HEIGHT - 10) // 4 - 5))
                        pygame.draw.line(wave_surface, (200, 200, 200) if current_theme == 0 else (100, 100, 100), 
                                         (w_wave - shift_x + i, r_center - r_amp), 
                                         (w_wave - shift_x + i, r_center + r_amp), 1)

        rx += 0.03
        ry += 0.05
        rz += 0.02

        if not is_active:
            smooth_spectrum = smooth_spectrum * 0.95 

        # ================= ВОДОПАД =================
        if waterfall_mode == 0:
            shift_y = 1
            waterfall_surface.scroll(0, -shift_y) 
            y_pos = waterfall_surface.get_height() - 1
            waterfall_surface.set_clip(pygame.Rect(0, 0, w_waterfall, WINDOW_HEIGHT - 10))
            
            if is_active:
                for i in range(SPECTRUM_BARS - 1):
                    val = smooth_spectrum[i]
                    if i > 0: val = (smooth_spectrum[i-1] + smooth_spectrum[i] + smooth_spectrum[i+1]) / 3.0
                    
                    if val < 0.05: color = (10, 10, 20) if current_theme == 0 else (200, 200, 200)
                    elif val < 0.2: color = (30, 0, 80) if current_theme == 0 else (150, 150, 255)
                    elif val < 0.4: color = (100, 0, 150) if current_theme == 0 else (200, 100, 255)
                    elif val < 0.6: color = (200, 0, 100) if current_theme == 0 else (255, 100, 150)
                    elif val < 0.8: color = (255, 100, 0) if current_theme == 0 else (255, 150, 100)
                    else: color = (255, 255, 150) if current_theme == 0 else (255, 255, 100)
                    
                    x_start = int(i / (SPECTRUM_BARS-1) * w_waterfall)
                    x_end = int((i+1) / (SPECTRUM_BARS-1) * w_waterfall)
                    pygame.draw.line(waterfall_surface, color, (x_start, y_pos), (x_end, y_pos), shift_y)
            else:
                pygame.draw.line(waterfall_surface, C["waterfall_bg"], (0, y_pos), (w_waterfall, y_pos), shift_y)
            waterfall_surface.set_clip(None)
        else:
            darken_color = (235, 235, 235)
            waterfall_surface.fill(darken_color, special_flags=pygame.BLEND_RGB_MULT)
            if is_active:
                for i in range(0, SPECTRUM_BARS - 1, 2):
                    val = smooth_spectrum[i]
                    if val > 0.05:
                        h = int(val * (WINDOW_HEIGHT - 10))
                        if val < 0.2: color = (30, 0, 80) if current_theme == 0 else (150, 150, 255)
                        elif val < 0.4: color = (100, 0, 150) if current_theme == 0 else (200, 100, 255)
                        elif val < 0.6: color = (200, 0, 100) if current_theme == 0 else (255, 100, 150)
                        elif val < 0.8: color = (255, 100, 0) if current_theme == 0 else (255, 150, 100)
                        else: color = (255, 255, 150) if current_theme == 0 else (255, 255, 100)
                        
                        x_start = int(i / (SPECTRUM_BARS-1) * w_waterfall)
                        x_end = int((i+2) / (SPECTRUM_BARS-1) * w_waterfall)
                        rect = pygame.Rect(x_start, WINDOW_HEIGHT - 10 - h, x_end - x_start, h)
                        pygame.draw.rect(waterfall_surface, color, rect)

        # ================= ОТРИСОВКА =================
        screen.fill(C["bg"])

        pygame.draw.rect(screen, C["grid"], wave_rect, 1)
        screen.blit(wave_surface, (5, 5))
        
        mode_label = font.render("MONO" if wave_mode == 0 else "STEREO", True, C["btn_text"])
        mode_bg = pygame.Rect(8, 8, 35, 12)
        pygame.draw.rect(screen, C["btn"], mode_bg)
        screen.blit(mode_label, (mode_bg.x + 2, mode_bg.y + 1))
        
        if 'peak_amplitude' in locals():
            wave_info_bg = pygame.Rect(50, 8, 60, 12)
            pygame.draw.rect(screen, C["btn"], wave_info_bg)
            wave_info_text = font.render(f"PK: {peak_amplitude:.0f}%", True, C["btn_text"])
            screen.blit(wave_info_text, (52, 9))

        # ================= ОСЦИЛЛОГРАФ (ЦЕНТРИРОВАН) =================
        pygame.draw.rect(screen, C["grid"], osc_rect, 1)
        for i in range(1, 4):
            pygame.draw.line(screen, C["grid"], (osc_x_start, 5 + i * (WINDOW_HEIGHT - 10) // 4), (osc_x_start + w_osc, 5 + i * (WINDOW_HEIGHT - 10) // 4))
            pygame.draw.line(screen, C["grid"], (osc_x_start + i * w_osc // 4, 5), (osc_x_start + i * w_osc // 4, WINDOW_HEIGHT - 5))
        
        if len(osc_buffer) > 0:
            osc_points = []
            display_length = min(len(osc_buffer), w_osc * 10)
            
            search_start = max(0, len(osc_buffer) - display_length * 2)
            search_end = len(osc_buffer) - display_length
            start_idx = search_start
            for i in range(search_start + 1, search_end):
                if osc_buffer[i-1] < 0 and osc_buffer[i] >= 0:
                    start_idx = i
                    break
            if start_idx == search_start:
                start_idx = max(0, len(osc_buffer) - display_length)
            
            step = display_length / w_osc
            for x in range(w_osc):
                idx_float = start_idx + x * step
                idx1 = int(idx_float)
                idx2 = min(idx1 + 1, len(osc_buffer) - 1)
                frac = idx_float - idx1
                val1 = osc_buffer[idx1] / 32768.0
                val2 = osc_buffer[idx2] / 32768.0
                val = val1 * (1 - frac) + val2 * frac
                val = val * agc_gain
                val = max(-1.0, min(1.0, val))
                y = (WINDOW_HEIGHT // 2) - int(val * (WINDOW_HEIGHT // 2 - 10))
                osc_points.append((osc_x_start + x, max(5, min(WINDOW_HEIGHT - 5, y))))
            if len(osc_points) > 1:
                pygame.draw.lines(screen, C["osc"], False, osc_points, 1)
        
        if 'peak_amplitude' in locals():
            volts = (peak_amplitude / 100.0) * 5.0
            fps = int(clock.get_fps())
            osc_info_bg = pygame.Rect(osc_x_start + 3, 8, 70, 12)
            pygame.draw.rect(screen, C["btn"], osc_info_bg)
            osc_info_text = font.render(f"{volts:.1f}V | {fps}FPS", True, C["btn_text"])
            screen.blit(osc_info_text, (osc_x_start + 5, 9))

        # ================= СТЕРЕОМЕТР (СЕРЫЙ РОМБ, ФИОЛЕТОВЫЕ ТОЧКИ) =================
        scope_x = osc_x_start + w_osc + 5
        scope_y = WINDOW_HEIGHT // 2
        radius = min(w_scope // 2, WINDOW_HEIGHT // 2) - 5
        center_x = scope_x + w_scope // 2
        
        # Сетка ромба (возвращена к стандартному серому)
        pygame.draw.circle(screen, C["grid"], (center_x, scope_y), radius, 1)
        pygame.draw.polygon(screen, C["grid"], [
            (center_x, scope_y - radius), (center_x + radius, scope_y), 
            (center_x, scope_y + radius), (center_x - radius, scope_y)
        ], 1)
        pygame.draw.line(screen, C["grid"], (center_x, scope_y - radius), (center_x, scope_y + radius))
        pygame.draw.line(screen, C["grid"], (center_x - radius, scope_y), (center_x + radius, scope_y))

        # Подписи (стандартный цвет)
        lbl_L = font.render("L", True, C["text"])
        lbl_R = font.render("R", True, C["text"])
        lbl_M = font.render("M", True, C["text"])
        lbl_S = font.render("S", True, C["text"])
        screen.blit(lbl_L, (int(center_x - radius - 10), int(scope_y - 6)))
        screen.blit(lbl_R, (int(center_x + radius + 4), int(scope_y - 6)))
        screen.blit(lbl_M, (int(center_x - 4), int(scope_y + radius + 2)))
        screen.blit(lbl_S, (int(center_x - 4), int(scope_y - radius - 10)))

        corr = 0.0
        if 'left_channel' in locals() and len(left_channel) > 0:
            l_arr = left_channel / 32768.0
            r_arr = right_channel / 32768.0
            if np.std(l_arr) > 0.001 and np.std(r_arr) > 0.001:
                corr = np.corrcoef(l_arr, r_arr)[0, 1] * 100

        corr_bg = pygame.Rect(scope_x + 5, 10, 55, 12)
        pygame.draw.rect(screen, C["btn"], corr_bg)
        corr_text = font.render(f"C: {corr:.0f}%", True, C["btn_text"])
        screen.blit(corr_text, (corr_bg.x + 4, corr_bg.y + 1))

        # Фиолетовые точки (амплитуда уменьшена)
        if 'left_channel' in locals() and is_active:
            step = max(1, len(left_channel) // 100)
            for i in range(0, len(left_channel), step):
                l_val = (left_channel[i] / 32768.0) * agc_gain / 1.5
                r_val = (right_channel[i] / 32768.0) * agc_gain / 1.5
                
                raw_x = (r_val - l_val)
                raw_y = (r_val + l_val)
                
                sum_abs = abs(raw_x) + abs(raw_y)
                if sum_abs > 1.0:
                    raw_x /= sum_abs
                    raw_y /= sum_abs
                
                # Цвет точки - фиолетовый с легким градиентом от громкости
                color = C["scope_dots"]
                if sum_abs > 0.9: color = (255, 200, 255) 
                elif sum_abs > 0.6: color = (200, 100, 255)
                
                x = center_x + int(raw_x * radius)
                y = scope_y - int(raw_y * radius)
                pygame.draw.circle(screen, color, (x, y), 1)

        # ================= ИНДИКАТОРЫ L/R (ФИОЛЕТОВЫЕ ПОЛОСКИ) =================
        bar_x = scope_x + w_scope - 10
        bar_w = 4
        bar_h = WINDOW_HEIGHT - 20 
        
        l_level = (np.max(np.abs(left_channel)) / 32768.0) * agc_gain if 'left_channel' in locals() and len(left_channel) > 0 else 0
        r_level = (np.max(np.abs(right_channel)) / 32768.0) * agc_gain if 'right_channel' in locals() and len(right_channel) > 0 else 0
        
        l_level = max(0.0, min(1.0, l_level / 1.5))
        r_level = max(0.0, min(1.0, r_level / 1.5))
        
        bar_h_l = int(l_level * bar_h)
        bar_h_r = int(r_level * bar_h)
        
        # Темный фон полоски
        pygame.draw.rect(screen, C["bar_bg"], (bar_x, 10, bar_w, bar_h))
        pygame.draw.rect(screen, C["bar_bg"], (bar_x + bar_w + 2, 10, bar_w, bar_h))
        
        # Заливка фиолетовым
        pygame.draw.rect(screen, C["scope_dots"], (bar_x, 10 + bar_h - bar_h_l, bar_w, bar_h_l))
        pygame.draw.rect(screen, C["scope_dots"], (bar_x + bar_w + 2, 10 + bar_h - bar_h_r, bar_w, bar_h_r))

        # ================= СПЕКТР =================
        pygame.draw.rect(screen, C["grid"], spec_rect, 1)
        for i in range(1, 4):
            x_grid = spec_x_start + i * w_spec // 4
            pygame.draw.line(screen, C["grid"], (x_grid, 5), (x_grid, WINDOW_HEIGHT - 5))
        
        if len(smooth_spectrum) > 1:
            x_pixels = np.arange(w_spec)
            curve = np.interp(x_pixels, np.linspace(0, w_spec - 1, SPECTRUM_BARS), smooth_spectrum)
            peak_curve = np.interp(x_pixels, np.linspace(0, w_spec - 1, SPECTRUM_BARS), peak_hold)

            y_bottom = WINDOW_HEIGHT - 5
            y_top = 5

            for x in range(0, w_spec, 2):
                y = y_bottom - int(curve[x] * (WINDOW_HEIGHT - 10))
                h_norm = (y_bottom - y) / max(1, (y_bottom - y_top))
                color_idx = min(63, int(h_norm * 63))
                color = SPEC_LUT[color_idx]
                pygame.draw.rect(screen, color, (spec_x_start + x, y, 2, y_bottom - y))

            points = [(spec_x_start + x, max(y_top, y_bottom - int(curve[x] * (WINDOW_HEIGHT - 10))))
                      for x in range(w_spec)]
            pygame.draw.lines(screen, (220, 200, 255), False, points, 1)

            peak_points = [(spec_x_start + x, max(y_top, y_bottom - int(peak_curve[x] * (WINDOW_HEIGHT - 10))))
                           for x in range(w_spec)]
            pygame.draw.lines(screen, (160, 160, 220), False, peak_points, 1)

        if 'peak_db' in locals():
            info_bg = pygame.Rect(spec_x_start + 5, 10, 70, 15)
            pygame.draw.rect(screen, C["btn"], info_bg)
            info_text = font.render(f"{peak_db:.1f}dB | {int(peak_freq)}Hz", True, C["btn_text"])
            screen.blit(info_text, (spec_x_start + 8, 12))
            
        for i, label in zip([30, 60, 90], ["100", "1k", "10k"]):
            x_label = spec_x_start + int(i / (SPECTRUM_BARS-1) * w_spec)
            text = font.render(f"{label}Hz", True, C["text"])
            screen.blit(text, (x_label - 10, 5))

        # ================= LUFS =================
        meter_x = spec_x_start + w_spec + 5
        pygame.draw.rect(screen, C["bg"], (meter_x, 5, w_meter, WINDOW_HEIGHT - 10)) 
        
        scale_vals = [0, -6, -12, -24, -36, -50]
        for val in scale_vals:
            y_grid = 5 + int((abs(val) / 60) * (WINDOW_HEIGHT - 10))
            text = font_lufs_num.render(f"{val}", True, C["lufs_text"])
            screen.blit(text, (meter_x + 5, y_grid - 8))
            if val != -50:
                pygame.draw.line(screen, C["lufs_text"], (meter_x + 30, y_grid), (meter_x + 50, y_grid), 1)

        if 'rms_db' in locals():
            norm_rms = np.clip((rms_db + 60) / 60, 0, 1)
            fill_h = int(norm_rms * (WINDOW_HEIGHT - 10))
            bar_w = 6
            pygame.draw.rect(screen, C["lufs_bar"], (meter_x + 60, WINDOW_HEIGHT - 5 - fill_h, bar_w, fill_h))
            pygame.draw.rect(screen, C["lufs_bar"], (meter_x + 75, WINDOW_HEIGHT - 5 - fill_h, bar_w, fill_h))

            lufs_bg = pygame.Rect(meter_x + 90, 30, 55, 20)
            pygame.draw.rect(screen, C["lufs_bg"], lufs_bg)
            
            lufs_text = font_lufs_val.render(f"{rms_db:.1f}", True, C["lufs_bg_text"])
            screen.blit(lufs_text, (lufs_bg.x + 5, lufs_bg.y + 1))

        # ================= ВОДОПАД =================
        waterfall_x_pos = meter_x + w_meter + 5
        waterfall_rect = pygame.Rect(waterfall_x_pos, 5, w_waterfall, WINDOW_HEIGHT - 10)
        
        screen.blit(waterfall_surface, (waterfall_x_pos, 5))
        pygame.draw.rect(screen, C["grid"], waterfall_rect, 1)
        
        wf_mode_text = font.render("SHIFT" if waterfall_mode == 0 else "LAYER", True, C["btn_text"])
        wf_mode_bg = pygame.Rect(waterfall_x_pos + w_waterfall - 45, 10, 35, 12)
        pygame.draw.rect(screen, C["btn"], wf_mode_bg)
        screen.blit(wf_mode_text, (wf_mode_bg.x + 2, wf_mode_bg.y + 1))

        for val, y_offset in [(10000, 10), (1000, 50), (100, 90)]:
            text = font.render(f"{val}", True, C["text"])
            screen.blit(text, (waterfall_x_pos + 2, y_offset))

        # ================= 3D КУБ =================
        pygame.draw.rect(screen, C["grid"], cube_rect, 1)
        cube_center_x = cube_rect.x + w_cube // 2
        cube_center_y = (WINDOW_HEIGHT - 10) // 2
        draw_big_cube(screen, cube_center_x, cube_center_y, rx, ry, rz, current_theme)

        # ================= КНОПКИ =================
        mouse_pos = pygame.mouse.get_pos()
        
        if btn_close_rect.collidepoint(mouse_pos):
            pygame.draw.rect(screen, C["btn_hover"], btn_close_rect)
        else:
            pygame.draw.rect(screen, C["btn"], btn_close_rect)
        pygame.draw.rect(screen, C["grid"], btn_close_rect, 1)
        text_x = font_btn.render("X", True, C["btn_text"])
        screen.blit(text_x, (btn_close_rect.x + 7, btn_close_rect.y + 2))
        
        if btn_min_rect.collidepoint(mouse_pos):
            pygame.draw.rect(screen, C["btn_hover"], btn_min_rect)
        else:
            pygame.draw.rect(screen, C["btn"], btn_min_rect)
        pygame.draw.rect(screen, C["grid"], btn_min_rect, 1)
        text_min = font_btn.render("_", True, C["btn_text"])
        screen.blit(text_min, (btn_min_rect.x + 7, btn_min_rect.y - 2))
        
        if theme_btn_rect.collidepoint(mouse_pos):
            pygame.draw.rect(screen, C["btn_hover"], theme_btn_rect)
        else:
            pygame.draw.rect(screen, C["btn"], theme_btn_rect)
        pygame.draw.rect(screen, C["grid"], theme_btn_rect, 1)
        theme_text = font.render("T", True, C["btn_text"])
        screen.blit(theme_text, (theme_btn_rect.x + 6, theme_btn_rect.y + 2))

        pygame.display.flip()
        clock.tick(FPS)

    stream.stop_stream()
    stream.close()
    p.terminate()
    pygame.quit()

if __name__ == "__main__":
    main()