#
# Audio Flora v3: Watercolor Bloom
# ---------------------------------
# This version now features flowers inspired by the provided watercolor image,
# with soft blue petals and delicate leaves, all smoothly syncing with music.
#
# - BASS: Pulses through the trunk and shakes the scene.
# - MIDS: Drive the growth of branches and unfurl the leaves.
# - TREBLE: Makes the watercolor-style blue flowers bloom and emit soft sparkles.
#

import pygame
import numpy as np
import pyaudio
import math
import random
import sys
from numpy.fft import rfft, rfftfreq

# --- Configuration ---
WIDTH, HEIGHT = 1920, 1080
FPS = 60
SAMPLE_RATE = 44100
CHUNK_SIZE = 2048

# --- Frequency Analysis Bands (in Hz) ---
BASS_RANGE = (20, 250)
MIDS_RANGE = (250, 2000)
TREBLE_RANGE = (2000, 8000)

# --- Colors & Style ---
BG_COLOR = (15, 10, 20) # Slightly richer dark background
BRANCH_COLOR = (80, 60, 40)

# Watercolor-inspired blue flower colors
FLOWER_COLOR_LOW = (150, 170, 200) # Muted blue/grey
FLOWER_COLOR_MID = (100, 130, 220) # Core blue from image
FLOWER_COLOR_HIGH = (200, 220, 255) # Lighter edge for bloom

# Muted green leaves
LEAF_COLOR_START = (40, 60, 45)  # Darker, desaturated green
LEAF_COLOR_END = (90, 130, 95)   # Lighter, desaturated green

SPARKLE_COLOR = (240, 245, 255) # Soft white sparkle

# Helper function for smooth value changes (interpolation)
def smooth_value(current, target, factor):
    return current + (target - current) * factor

class Leaf:
    """Represents a delicate leaf that unfurls with the music."""
    def __init__(self, parent_branch, pos_on_branch, angle_offset):
        self.branch = parent_branch
        self.position = pos_on_branch
        self.angle_offset = angle_offset + random.uniform(-10, 10) # Add some natural variance
        self.length = random.uniform(35, 70)
        self.width = random.uniform(8, 18)
        self.growth = 0.0 # 0.0 (furled) to 1.0 (unfurled)
        self.curve_factor = random.uniform(0.3, 0.7) # How much it curves

    def update(self, audio, branch_growth):
        if branch_growth > 0.4:
            target_growth = np.clip(audio['mids'] * 1.5, 0, 1)
            self.growth = smooth_value(self.growth, target_growth, 0.07) # Slightly faster leaf growth
        else:
            self.growth = smooth_value(self.growth, 0, 0.12) # Furl back up smoothly

    def draw(self, surface):
        if self.growth > 0.05:
            branch_vec = self.branch._get_end_pos() - self.branch.start_pos
            start_pos = self.branch.start_pos + branch_vec * self.position
            branch_angle = math.degrees(math.atan2(branch_vec[1], branch_vec[0]))
            
            base_angle = branch_angle + self.angle_offset
            
            points = [start_pos]
            num_segments = 8 # More segments for smoother curve
            
            # Interpolate color based on growth for a subtle watercolor blend
            t = self.growth
            color_r = int((1 - t) * LEAF_COLOR_START[0] + t * LEAF_COLOR_END[0])
            color_g = int((1 - t) * LEAF_COLOR_START[1] + t * LEAF_COLOR_END[1])
            color_b = int((1 - t) * LEAF_COLOR_START[2] + t * LEAF_COLOR_END[2])
            leaf_color = (color_r, color_g, color_b)

            # Generate points for the curved leaf shape
            for i in range(1, num_segments + 1):
                t_segment = i / num_segments
                current_len = t_segment * self.length * self.growth
                
                # Apply curving effect
                curve_offset = math.sin(t_segment * math.pi) * self.width * self.growth * self.curve_factor
                
                rad = math.radians(base_angle)
                
                # Points for one side of the leaf
                points.append((
                    start_pos[0] + math.cos(rad) * current_len - math.sin(rad) * curve_offset,
                    start_pos[1] + math.sin(rad) * current_len + math.cos(rad) * curve_offset
                ))
            
            # Tip of the leaf
            tip_pos = (
                start_pos[0] + math.cos(math.radians(base_angle)) * self.length * self.growth,
                start_pos[1] + math.sin(math.radians(base_angle)) * self.length * self.growth
            )
            points.append(tip_pos)

            # Generate points for the other side of the leaf (mirrored curve)
            for i in range(num_segments -1, 0, -1):
                t_segment = i / num_segments
                current_len = t_segment * self.length * self.growth
                curve_offset = math.sin(t_segment * math.pi) * self.width * self.growth * self.curve_factor
                
                rad = math.radians(base_angle)
                
                points.append((
                    start_pos[0] + math.cos(rad) * current_len + math.sin(rad) * curve_offset, # Opposite curve
                    start_pos[1] + math.sin(rad) * current_len - math.cos(rad) * curve_offset
                ))

            # Draw the leaf shape
            if len(points) > 2:
                pygame.draw.polygon(surface, leaf_color, points)
                # Add a subtle darker line for a vein effect (optional, can be removed)
                pygame.draw.line(surface, (leaf_color[0]*0.7, leaf_color[1]*0.7, leaf_color[2]*0.7), start_pos, tip_pos, 1)

class Sparkle:
    """A short-lived particle emitted by blooming flowers."""
    def __init__(self, pos):
        self.pos = np.array(pos, dtype=float)
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(0.8, 2.5) # Slightly less explosive sparkles
        self.vel = np.array([math.cos(angle) * speed, math.sin(angle) * speed])
        self.life = random.uniform(0.6, 1.2) # Longer sparkle life
        self.max_life = self.life
        self.size = random.uniform(1, 3)

    def update(self):
        self.pos += self.vel
        self.vel *= 0.93 # Slower deceleration
        self.life -= 1 / FPS

    def draw(self, surface):
        if self.life > 0:
            current_size = self.size * (self.life / self.max_life) # Fade out size
            alpha = int(255 * (self.life / self.max_life))
            
            # Use a separate surface for alpha transparency
            s = pygame.Surface((int(current_size * 2), int(current_size * 2)), pygame.SRCALPHA)
            pygame.draw.circle(s, (*SPARKLE_COLOR, alpha), (int(current_size), int(current_size)), int(current_size))
            surface.blit(s, self.pos - int(current_size))

class Branch:
    """Represents a branch that grows recursively and reacts to audio."""
    def __init__(self, start_pos, angle, max_length, thickness, depth=0):
        self.start_pos = np.array(start_pos, dtype=float)
        self.angle = angle
        self.max_length = max_length
        self.thickness = thickness
        self.depth = depth
        self.growth = 0.0
        self.pulse = 1.0

        self.children = []
        self.flowers = []
        self.leaves = []

        if self.depth < 7: # Allows for a bit more detail
            self._create_children()

    def _get_end_pos(self):
        rad_angle = math.radians(self.angle)
        length = self.max_length * self.growth
        return self.start_pos + np.array([math.cos(rad_angle) * length, math.sin(rad_angle) * length])

    def _create_children(self):
        end_pos_fully_grown = self.start_pos + np.array([
            math.cos(math.radians(self.angle)) * self.max_length,
            math.sin(math.radians(self.angle)) * self.max_length
        ])
        
        # Deeper branches get flowers
        if self.depth >= 4 and random.random() < 0.7: # Higher chance for flowers
            self.flowers.append(Flower(self, random.uniform(0.5, 1.0)))
        
        # Mid-level branches get leaves
        if 2 <= self.depth <= 5 and random.random() < 0.8: # Higher chance for leaves
            self.leaves.append(Leaf(self, random.uniform(0.2, 0.8), random.choice([-55, 55]))) # Wider angle for leaves
        
        # Create more branches
        if self.depth < 6:
            num_branches = random.randint(1, 3) # More branches for fuller look
            for _ in range(num_branches):
                self.children.append(Branch(
                    end_pos_fully_grown,
                    self.angle + random.uniform(-35, 35), # Wider branching angles
                    self.max_length * random.uniform(0.6, 0.9), # More varied branch lengths
                    max(1, self.thickness * 0.7),
                    self.depth + 1
                ))

    def update(self, audio, sparkles_list):
        target_growth = np.clip(audio['mids'] * 1.2, 0, 1)
        self.growth = smooth_value(self.growth, target_growth, 0.06)
        self.pulse = 1.0 + audio['bass'] * 0.1 * max(0, 4 - self.depth)

        current_end_pos = self._get_end_pos()
        if self.growth > 0.05:
            for child in self.children:
                child.start_pos = current_end_pos
                child.update(audio, sparkles_list)
        
        for flower in self.flowers: flower.update(audio, self.growth, sparkles_list)
        for leaf in self.leaves: leaf.update(audio, self.growth)

    def draw(self, surface):
        if self.growth > 0.01:
            end_pos = self._get_end_pos()
            thickness = max(1, int(self.thickness * self.growth * self.pulse))
            pygame.draw.line(surface, BRANCH_COLOR, self.start_pos, end_pos, thickness)
            
            for leaf in self.leaves: leaf.draw(surface)
            for child in self.children: child.draw(surface)
            for flower in self.flowers: flower.draw(surface)

class Flower:
    """Represents a watercolor-style flower that blooms blue and emits sparkles."""
    def __init__(self, parent_branch, pos_on_branch):
        self.branch = parent_branch
        self.position = pos_on_branch
        self.bloom = 0.0
        self.size = random.uniform(15, 28) # Slightly larger flowers
        self.rotation = random.uniform(0, 360)
        self.num_petals = random.randint(6, 8) # More petals for fuller look
        self.last_bloom = 0.0

    def update(self, audio, branch_growth, sparkles_list):
        if branch_growth > 0.7:
            target_bloom = np.clip(audio['treble'] * 1.5, 0, 1)
            self.bloom = smooth_value(self.bloom, target_bloom, 0.1) # Faster bloom
        else:
            self.bloom = smooth_value(self.bloom, 0, 0.1)
        
        if self.bloom > 0.5 and self.bloom > self.last_bloom + 0.05:
            pos_vec = self.branch.start_pos + (self.branch._get_end_pos() - self.branch.start_pos) * self.position
            for _ in range(random.randint(1, 3)): # More sparkles
                sparkles_list.append(Sparkle(pos_vec))
        self.last_bloom = self.bloom
        
        self.rotation += audio['treble'] * 20 # Treble makes flowers subtly rotate

    def draw(self, surface):
        if self.bloom > 0.05:
            pos = self.branch.start_pos + (self.branch._get_end_pos() - self.branch.start_pos) * self.position
            current_size = self.size * self.bloom
            
            # --- Watercolor effect for petals ---
            # Draw multiple translucent circles for each petal to create a layered, blended look
            # Mimicking the image's softer edges and color variations
            
            base_color = FLOWER_COLOR_MID
            highlight_color = FLOWER_COLOR_HIGH
            shadow_color = FLOWER_COLOR_LOW
            
            for i in range(self.num_petals):
                angle_rad = math.radians(self.rotation + i * (360 / self.num_petals))
                petal_base_pos = pos + np.array([math.cos(angle_rad), math.sin(angle_rad)]) * current_size * 0.4
                
                # Draw main petal (middle tone)
                petal_surface = pygame.Surface((int(current_size * 1.5), int(current_size * 1.5)), pygame.SRCALPHA)
                pygame.draw.circle(petal_surface, (*base_color, 150), (int(current_size*0.75), int(current_size*0.75)), int(current_size * 0.5))
                surface.blit(petal_surface, petal_base_pos - int(current_size*0.75))

                # Draw highlight (lighter tone, smaller, more transparent)
                if self.bloom > 0.3:
                    highlight_surface = pygame.Surface((int(current_size * 1.2), int(current_size * 1.2)), pygame.SRCALPHA)
                    pygame.draw.circle(highlight_surface, (*highlight_color, 100), (int(current_size*0.6), int(current_size*0.6)), int(current_size * 0.3))
                    offset_angle = angle_rad + math.radians(10) # Slightly offset highlight
                    highlight_offset = np.array([math.cos(offset_angle), math.sin(offset_angle)]) * current_size * 0.1
                    surface.blit(highlight_surface, petal_base_pos - int(current_size*0.6) + highlight_offset)

            # Draw center (yellowish-white dot)
            pygame.draw.circle(surface, (255, 255, 200), pos.astype(int), int(current_size * 0.15))


class AudioFloraVisualizer:
    """Main class to handle audio, rendering, and the main loop."""
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Audio Flora v3 - Watercolor Bloom")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("Arial", 18)
        self.running = True
        
        self.audio_levels = {'volume': 0.0, 'bass': 0.0, 'mids': 0.0, 'treble': 0.0}
        self.peak_levels = {k: 1e-5 for k in self.audio_levels}
        
        self.plant = Branch((WIDTH / 2, HEIGHT + 20), -90, HEIGHT / 3.5, 25)
        self.sparkles = []
        self.camera_shake = 0.0

        self.p_audio = pyaudio.PyAudio()
        self.stream = self._setup_audio_stream()
        self.fft_freqs = rfftfreq(CHUNK_SIZE, 1/SAMPLE_RATE)
        
    def _setup_audio_stream(self):
        print("Searching for audio devices...")
        try:
            default_device_info = self.p_audio.get_default_input_device_info()
            print(f"Attempting to use default device: {default_device_info['name']}")
            stream = self.p_audio.open(
                format=pyaudio.paInt16, channels=1, rate=SAMPLE_RATE, input=True,
                frames_per_buffer=CHUNK_SIZE, input_device_index=default_device_info['index']
            )
            print("Audio stream opened successfully.")
            return stream
        except Exception as e:
            print(f"\n--- AUDIO ERROR ---")
            print(f"Could not open audio stream: {e}")
            print("The visualizer will run with simulated audio.")
            print("Please check your audio settings (e.g., enable 'Stereo Mix' on Windows, 'BlackHole' on macOS).")
            return None

    def _process_audio(self):
        if self.stream is None:
            t = pygame.time.get_ticks() / 1000.0
            return {'volume': (math.sin(t*2)+1)/2*15000,'bass':(math.sin(t*2+math.pi)+1)/2*1e6,'mids':(math.sin(t*4)+1)/2*1e5,'treble':(math.sin(t*8)+1)/2*1e4}
        try:
            data = self.stream.read(CHUNK_SIZE, exception_on_overflow=False)
            audio_data = np.frombuffer(data, dtype=np.int16)
            if not audio_data.any(): return {k: 0 for k in self.audio_levels}
            rms = np.sqrt(np.mean(audio_data.astype(np.float64)**2))
            fft_mag = np.abs(rfft(audio_data))
            return {
                'volume': rms,
                'bass': np.mean(fft_mag[(self.fft_freqs >= BASS_RANGE[0]) & (self.fft_freqs < BASS_RANGE[1])]),
                'mids': np.mean(fft_mag[(self.fft_freqs >= MIDS_RANGE[0]) & (self.fft_freqs < MIDS_RANGE[1])]),
                'treble': np.mean(fft_mag[(self.fft_freqs >= TREBLE_RANGE[0]) & (self.fft_freqs < TREBLE_RANGE[1])])
            }
        except (IOError, TypeError): return {k: 0 for k in self.audio_levels}

    def _update_audio_levels(self):
        raw_levels = self._process_audio()
        for key in self.audio_levels.keys():
            raw_val = raw_levels.get(key, 0)
            if np.isnan(raw_val): raw_val = 0
            self.peak_levels[key] = max(self.peak_levels[key], raw_val)
            normalized = raw_val / self.peak_levels[key]
            self.audio_levels[key] = smooth_value(self.audio_levels[key], normalized, 0.35)
            self.peak_levels[key] *= 0.999

    def _draw_debug_info(self):
        y_pos = 10
        for name, value in self.audio_levels.items():
            text_surf = self.font.render(f"{name.upper()}: {value:.2f}", True, (200,200,200))
            self.screen.blit(text_surf, (10, y_pos))
            pygame.draw.rect(self.screen, (60,60,60), (100, y_pos+4, 200, 10))
            pygame.draw.rect(self.screen, (150,255,150), (100, y_pos+4, value*200, 10))
            y_pos += 25

    def run(self):
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                    self.running = False
            
            # --- Update ---
            self._update_audio_levels()
            self.plant.update(self.audio_levels, self.sparkles)
            
            for s in self.sparkles: s.update()
            self.sparkles = [s for s in self.sparkles if s.life > 0]
            
            self.camera_shake = self.audio_levels['bass'] * 8

            # --- Draw ---
            self.screen.fill(BG_COLOR)
            scene_surface = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            
            self.plant.draw(scene_surface)
            for s in self.sparkles: s.draw(scene_surface)
            
            offset_x = random.uniform(-1, 1) * self.camera_shake
            offset_y = random.uniform(-1, 1) * self.camera_shake
            self.screen.blit(scene_surface, (offset_x, offset_y))
            
            self._draw_debug_info()
            
            pygame.display.flip()
            self.clock.tick(FPS)
            
        # --- Cleanup ---
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        self.p_audio.terminate()
        pygame.quit()
        sys.exit()

if __name__ == "__main__":
    visualizer = AudioFloraVisualizer()
    visualizer.run()