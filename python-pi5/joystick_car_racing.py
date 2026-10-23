#!/usr/bin/env python3
"""
SUNSET RUSH  -  an open-road arcade racer for Raspberry Pi
==========================================================
Race through sunny meadows, red canyons, pine forests and a neon city while
day turns into night (and sometimes rain!). Beat the clock, pass traffic and
chain together flashy SKILLS to score big.

  Checkpoints ........ add time to the clock - keep going!
  DRIFT .............. hold the button while steering through a corner
                       (let go after a long drift for a speed boost)
  NEAR MISS .......... squeeze past a car without touching it
  SLIPSTREAM ......... tuck in right behind a car
  SPEED TRAP ......... blast through the camera gates at 150+ km/h
  RIVAL PASS ......... overtake the gold racing cars
  Each different skill in a chain raises your multiplier (x2, x3 ...). The
  chain banks when you stay clean for 3 seconds - crash and you lose it!

Controls
  Joystick LEFT / RIGHT .......... steer
  Joystick DOWN .................. brake         (the car accelerates by itself)
  Joystick UP .................... NITRO         (fill the bar with skills)
  Joystick button (HOLD) ......... handbrake drift
  Menu: LEFT/RIGHT picks a car, button starts.   Esc quits.
  Keyboard works too: arrows or WASD, Space = drift.

Run:   python3 sunset_rush.py
Needs: pygame  ->  sudo apt install python3-pygame
Put this file in the same folder as ADC0834.py (raphael-kit/python-pi5),
or keep raphael-kit in your home folder - the game will find it.
Keep your hand off the joystick while the game starts (it measures the center).
"""
import array
import math
import os
import random
import sys
import time

import pygame


def game_folder():
    """Folder this game lives in (works even when __file__ isn't set,
    e.g. when the code is pasted into a runner or started with exec())."""
    try:
        return os.path.dirname(os.path.abspath(__file__))
    except NameError:
        if sys.argv and sys.argv[0] and sys.argv[0] not in ("-c", "-"):
            return os.path.dirname(os.path.abspath(sys.argv[0]))
        return os.getcwd()


# =====================================================================
# SETTINGS  -  tweak these to match your setup
# =====================================================================
WIDTH, HEIGHT = 800, 600
FULLSCREEN = False          # True = fill the whole screen (scaled)
FPS = 60
DEADZONE = 0.25             # ignore small stick wobble near the center
INVERT_X = False            # flip if left/right feel backwards
INVERT_Y = False            # flip if up/down feel backwards
SWAP_XY = False             # True if pushing up moves you sideways

# SunFounder joystick on the ADC0834 chip (same wiring as 2.1.9_joystick_zero.py)
JOY_X_CHANNEL = 0           # ADC0834.getResult(0)
JOY_Y_CHANNEL = 1           # ADC0834.getResult(1)
JOY_BUTTON_PIN = 22         # Button(22)

# Where to look for ADC0834.py if it isn't in the same folder as this game
ADC0834_FOLDERS = ["~/raphael-kit/python-pi5", "~/raphael-kit/python"]


# =====================================================================
# JOYSTICK INPUT  -  reads the ADC0834 joystick + GPIO22 button.
# A USB gamepad and the keyboard (arrows / WASD / Space) also work,
# so you can test the game on any computer.
# =====================================================================
import threading


class Controls:
    def __init__(self):
        self.mode = "keyboard"
        self.pad = None
        self.adc = None
        self.raw_x = self.raw_y = 128      # latest stick readings (0-255)
        self.cx = self.cy = 128            # resting center, measured at startup
        self.button = None
        self._was_down = False

        pygame.joystick.init()
        self._setup_adc0834()
        if self.adc is None and pygame.joystick.get_count() > 0:
            self.attach_pad(0)

    # ---------- ADC0834 joystick ----------
    def _setup_adc0834(self):
        here = game_folder()
        for folder in [here] + [os.path.expanduser(f) for f in ADC0834_FOLDERS]:
            if folder not in sys.path:
                sys.path.append(folder)
        try:
            import ADC0834
            from gpiozero import Button
            ADC0834.setup()
            self.adc = ADC0834
            self.button = Button(JOY_BUTTON_PIN)
        except Exception as e:
            print("ADC0834 joystick not available (" + str(e) + ") - using keyboard/gamepad")
            self.adc = None
            return

        # Measure the stick's resting position (don't touch it while the game starts!)
        xs, ys = [], []
        for _ in range(10):
            xs.append(self.adc.getResult(JOY_X_CHANNEL))
            ys.append(self.adc.getResult(JOY_Y_CHANNEL))
            time.sleep(0.01)
        xs.sort(), ys.sort()
        self.cx, self.cy = xs[5], ys[5]    # median ignores glitchy reads
        self.raw_x, self.raw_y = self.cx, self.cy
        self.mode = "joystick (ADC0834)"

        # Reading the chip is slow-ish, so do it in the background.
        # That keeps the game running smoothly at full speed.
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self):
        zeros = {JOY_X_CHANNEL: 0, JOY_Y_CHANNEL: 0}
        while True:
            for ch in (JOY_X_CHANNEL, JOY_Y_CHANNEL):
                try:
                    v = self.adc.getResult(ch)
                except Exception:
                    continue
                # ADC0834.getResult() returns 0 when a read glitches. Only trust a 0
                # if it shows up twice in a row (a real "pushed all the way" reading).
                if v == 0:
                    zeros[ch] += 1
                    if zeros[ch] < 2:
                        continue
                else:
                    zeros[ch] = 0
                if ch == JOY_X_CHANNEL:
                    self.raw_x = v
                else:
                    self.raw_y = v
            time.sleep(0.004)

    @staticmethod
    def _scale(value, center):
        """Turn a 0-255 reading into -1..1, using the measured center."""
        if value >= center:
            return (value - center) / max(1, 255 - center)
        return (value - center) / max(1, center)

    # ---------- USB gamepad (optional) ----------
    def attach_pad(self, index):
        self.pad = pygame.joystick.Joystick(index)
        self.pad.init()
        if self.adc is None:
            self.mode = "gamepad: " + self.pad.get_name()

    def axes(self):
        """Returns (x, y), each from -1 to 1. Right and down are positive."""
        x = y = 0.0
        if self.adc:
            x = self._scale(self.raw_x, self.cx)
            y = self._scale(self.raw_y, self.cy)
            if SWAP_XY:
                x, y = y, x
            if INVERT_X:
                x = -x
            if INVERT_Y:
                y = -y
        elif self.pad:
            if self.pad.get_numaxes() >= 2:
                x, y = self.pad.get_axis(0), self.pad.get_axis(1)
            if self.pad.get_numhats() > 0:
                hx, hy = self.pad.get_hat(0)
                if hx or hy:
                    x, y = hx, -hy

        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            x = -1
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            x = 1
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            y = -1
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            y = 1

        if abs(x) < DEADZONE:
            x = 0
        if abs(y) < DEADZONE:
            y = 0
        mag = math.hypot(x, y)
        if mag > 1:                      # diagonals shouldn't be faster
            x, y = x / mag, y / mag
        return x, y

    def button_down(self):
        down = False
        if self.button is not None and self.button.is_pressed:
            down = True
        if self.pad:
            down = down or any(self.pad.get_button(i) for i in range(self.pad.get_numbuttons()))
        keys = pygame.key.get_pressed()
        if keys[pygame.K_SPACE] or keys[pygame.K_RETURN]:
            down = True
        return down

    def button_pressed(self):
        """True only at the moment the button goes down. Call once per frame."""
        down = self.button_down()
        pressed = down and not self._was_down
        self._was_down = down
        return pressed


# =====================================================================
# GAME SETTINGS
# =====================================================================
RENDER_SCALE = 0.8          # draw smaller, then stretch (lower = faster on the Pi)
DRAW_MAX = 130              # how far ahead the road is drawn (lowers itself if the Pi is slow)
DRAW_MIN = 55
CYCLE_SECONDS = 150         # length of one full day / night cycle
START_TIME = 45             # seconds on the clock at the start
CHECKPOINT_BONUS = 22       # seconds added at every checkpoint
TRAP_MIN_KMH = 150          # speed needed to score at a speed trap

RW, RH = int(WIDTH * RENDER_SCALE), int(HEIGHT * RENDER_SCALE)
HIGH_SCORE_FILE = os.path.join(game_folder(), "sunset_rush_highscore.txt")

# ---- road geometry (you shouldn't need to change these) ----
SEG = 200                   # length of one road piece
ROAD_W = 2000               # half the road width
CAM_H = 1000
CAM_DEPTH = 1.0 / math.tan(math.radians(100 / 2))
PLAYER_Z = CAM_H * CAM_DEPTH
RUMBLE_LEN = 3
TRACK_TARGET = 3200
CAR_W = 560                 # car width in road units
KMH = 1.0 / 40              # speed units -> km/h

CARS = [
    dict(name="SPRINTER", color=(40, 120, 255), speed=10000, acc=1.0, steer=1.0, grip=1.0, drift=1.0, bars=(3, 3, 3)),
    dict(name="DRIFTER", color=(255, 140, 30), speed=9200, acc=1.1, steer=1.2, grip=0.8, drift=1.4, bars=(2, 4, 5)),
    dict(name="ROCKET", color=(235, 45, 60), speed=11200, acc=0.9, steer=0.85, grip=1.15, drift=0.9, bars=(5, 2, 2)),
]

# lane offset, speed, min gap, max gap, is_rival
LANES_CFG = [
    (-0.69, 6900, 26000, 44000, True),
    (-0.23, 4300, 7000, 14000, False),
    (0.23, 3500, 7000, 14000, False),
    (0.69, 2800, 6500, 13000, False),
]
TRAFFIC_COLORS = [(200, 200, 205), (70, 160, 90), (230, 200, 60), (150, 90, 180), (60, 170, 190),
                  (220, 110, 150), (90, 90, 100), (240, 240, 240)]

BIOMES = [
    dict(name="SUNNY MEADOWS", grass=((16, 154, 43), (0, 129, 58)), road=((107, 107, 107), (105, 105, 105)),
         rumble=((255, 255, 255), (205, 40, 40)), lane=(210, 210, 210), mtn=((130, 160, 205), (80, 125, 95)),
         near=["tree", "tree", "bush", "billboard", "tree"], far=["tree", "tree", "bush", "tree", "rock"]),
    dict(name="RED CANYON", grass=((232, 196, 124), (222, 184, 110)), road=((122, 112, 104), (118, 108, 100)),
         rumble=((255, 255, 255), (205, 40, 40)), lane=(235, 225, 200), mtn=((205, 140, 105), (160, 100, 72)),
         near=["cactus", "rock", "rock", "billboard"], far=["cactus", "rock", "rock", "bush", "cactus"]),
    dict(name="PINE FOREST", grass=((24, 104, 52), (16, 88, 42)), road=((92, 96, 102), (88, 92, 98)),
         rumble=((255, 255, 255), (205, 40, 40)), lane=(205, 210, 215), mtn=((95, 125, 150), (45, 85, 75)),
         near=["pine", "pine", "pine", "billboard"], far=["pine", "pine", "pine", "pine", "bush"]),
    dict(name="NEON CITY", grass=((70, 72, 86), (62, 64, 78)), road=((50, 50, 58), (46, 46, 54)),
         rumble=((240, 240, 255), (60, 180, 255)), lane=(240, 240, 120), mtn=((70, 80, 125), (45, 50, 90)),
         near=["lamp", "billboard", "lamp"], far=["building", "building", "building", "building", "lamp"]),
]

# time of day:  (when, sky top, sky bottom, light tint)
SKY = [
    (0.00, (70, 140, 235), (185, 220, 250), (1.0, 1.0, 1.0)),
    (0.40, (70, 140, 235), (185, 220, 250), (1.0, 1.0, 1.0)),
    (0.52, (85, 70, 150), (255, 160, 100), (1.0, 0.86, 0.80)),
    (0.64, (10, 12, 40), (40, 45, 95), (0.50, 0.56, 0.88)),
    (0.84, (10, 12, 40), (40, 45, 95), (0.50, 0.56, 0.88)),
    (0.93, (110, 110, 190), (255, 190, 140), (0.95, 0.88, 0.85)),
    (1.00, (70, 140, 235), (185, 220, 250), (1.0, 1.0, 1.0)),
]

SOLID_HALF = {"tree": 0.11, "pine": 0.11, "cactus": 0.09, "rock": 0.17, "billboard": 0.2, "lamp": 0.06}
_fonts = {}


# =====================================================================
# SMALL HELPERS
# =====================================================================
def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def lerp(a, b, t):
    return a + (b - a) * t


def lerp_col(a, b, t):
    return (int(a[0] + (b[0] - a[0]) * t), int(a[1] + (b[1] - a[1]) * t), int(a[2] + (b[2] - a[2]) * t))


def ease_in(a, b, p):
    return a + (b - a) * p * p


def ease_io(a, b, p):
    return a + (b - a) * (-math.cos(p * math.pi) / 2 + 0.5)


def wrap_dist(d, total):
    d %= total
    return d - total if d > total / 2 else d


def load_high_score():
    try:
        with open(HIGH_SCORE_FILE) as f:
            return int(f.read().strip())
    except Exception:
        return 0


def save_high_score(value):
    try:
        with open(HIGH_SCORE_FILE, "w") as f:
            f.write(str(value))
    except Exception:
        pass


def draw_text(surf, text, size, color, center=None, topleft=None, topright=None, midleft=None, shadow=True):
    if size not in _fonts:
        _fonts[size] = pygame.font.Font(None, size)
    font = _fonts[size]
    img = font.render(text, True, color)
    rect = img.get_rect()
    if center:
        rect.center = center
    elif topleft:
        rect.topleft = topleft
    elif topright:
        rect.topright = topright
    elif midleft:
        rect.midleft = midleft
    if shadow:
        sh = font.render(text, True, (0, 0, 0))
        surf.blit(sh, (rect.x + 2, rect.y + 2))
    surf.blit(img, rect)


class Sounds:
    """Little beeps made in code - no sound files needed. Silent if there's no audio."""
    def __init__(self):
        self.ok = False
        self.sfx = {}
        try:
            pygame.mixer.init(frequency=22050, size=-16, channels=1)
            self.sfx["bank"] = self._seq([(880, 0.06), (1320, 0.10)])
            self.sfx["check"] = self._seq([(660, 0.08), (880, 0.08), (1175, 0.16)])
            self.sfx["near"] = self._seq([(1000, 0.04)], vol=0.2)
            self.sfx["crash"] = self._noise(0.35)
            self.sfx["level"] = self._seq([(523, 0.08), (659, 0.08), (784, 0.08), (1047, 0.2)])
            self.sfx["trap"] = self._seq([(1500, 0.05), (1900, 0.1)], vol=0.25)
            self.sfx["boost"] = self._seq([(300, 0.05), (450, 0.05), (700, 0.1)], vol=0.25)
            self.sfx["count"] = self._seq([(440, 0.15)])
            self.sfx["go"] = self._seq([(880, 0.35)])
            self.sfx["over"] = self._seq([(440, 0.15), (330, 0.15), (220, 0.35)])
            self.ok = True
        except Exception:
            pass

    @staticmethod
    def _wave(freq, seconds, vol):
        rate = 22050
        n = int(rate * seconds)
        return [int(32767 * vol * math.sin(2 * math.pi * freq * i / rate) * (1 - 0.6 * i / n)) for i in range(n)]

    def _seq(self, notes, vol=0.3):
        data = []
        for f, d in notes:
            data += self._wave(f, d, vol)
        return pygame.mixer.Sound(buffer=array.array("h", data).tobytes())

    def _noise(self, seconds, vol=0.35):
        n = int(22050 * seconds)
        data = [int(32767 * vol * random.uniform(-1, 1) * (1 - i / n) ** 2) for i in range(n)]
        return pygame.mixer.Sound(buffer=array.array("h", data).tobytes())

    def play(self, name):
        if self.ok and name in self.sfx:
            self.sfx[name].play()


# =====================================================================
# THE TRACK
# =====================================================================
class Seg:
    __slots__ = ("index", "y1", "curve", "dark", "biome", "sprites")

    def __init__(self, index, y1, curve):
        self.index = index
        self.y1 = y1
        self.curve = curve
        self.dark = False
        self.biome = 0
        self.sprites = []


def build_track():
    rng = random.Random(7)
    segs = []
    state = {"y": 0.0}

    def add(curve, y):
        segs.append(Seg(len(segs), y, curve))

    def road(enter, hold, leave, curve, hill):
        sy = state["y"]
        ey = sy + hill * SEG
        total = enter + hold + leave
        n = 0
        for i in range(enter):
            add(ease_in(0, curve, i / enter), ease_io(sy, ey, n / total))
            n += 1
        for i in range(hold):
            add(curve, ease_io(sy, ey, n / total))
            n += 1
        for i in range(leave):
            add(ease_io(curve, 0, i / leave), ease_io(sy, ey, n / total))
            n += 1
        state["y"] = ey

    road(30, 40, 30, 0, 0)
    while len(segs) < TRACK_TARGET - 220:
        r = rng.random()
        sgn = rng.choice((-1, 1))
        cy = state["y"]
        hsign = -1 if cy > 5000 else (1 if cy < -2000 else rng.choice((-1, 1)))
        if r < 0.18:
            road(25, rng.randint(40, 120), 25, 0, 0)
        elif r < 0.38:
            road(40, rng.randint(40, 90), 40, sgn * rng.choice((2, 3)), 0)
        elif r < 0.60:
            road(30, rng.randint(30, 60), 30, sgn * rng.choice((5, 6)), 0)
        elif r < 0.72:
            road(30, 40, 30, sgn * 3, 0)
            road(30, 40, 30, -sgn * 4, 0)
        elif r < 0.88:
            road(40, rng.randint(20, 50), 40, 0, hsign * rng.choice((20, 40, 60)))
        else:
            road(50, 40, 50, sgn * rng.choice((2, 4)), hsign * rng.choice((20, 40)))
    road(30, 30, 30, 0, -state["y"] / SEG)       # come back down to ground level
    road(20, 20, 20, 0, 0)

    n_total = len(segs)
    quarter = n_total // 4
    events = {}
    for b in range(4):
        events[b * quarter] = ("biome", b)
        events[b * quarter + quarter - 45] = ("cp",)
        events[b * quarter + int(quarter * 0.30)] = ("trap",)
        events[b * quarter + int(quarter * 0.62)] = ("trap",)

    srng = random.Random(21)
    for i, sg in enumerate(segs):
        b = min(3, i // quarter)
        sg.biome = b
        sg.dark = (i // RUMBLE_LEN) % 2 == 1
        B = BIOMES[b]
        far_p = 0.15 if b == 3 else 0.11
        for side in (-1, 1):
            if srng.random() < far_p:
                sg.sprites.append((srng.choice(B["far"]), side * srng.uniform(2.6, 6.5), srng.uniform(0.8, 1.4)))
        if srng.random() < 0.024:
            kind = srng.choice(B["near"])
            sg.sprites.append((kind, srng.choice((-1, 1)) * srng.uniform(1.3, 1.9), srng.uniform(0.9, 1.2)))
        if b == 3 and i % 12 == 0:
            sg.sprites.append(("lamp", (1 if (i // 12) % 2 else -1) * 1.22, 1.0))
        if abs(sg.curve) >= 4 and i % 10 == 0:
            d = 1 if sg.curve > 0 else -1
            sg.sprites.append(("arrow", -d * 1.45, d))
        ev = events.get(i)
        if ev and ev[0] == "cp":
            sg.sprites.append(("gate_cp", 0.0, 1.0))
        elif ev and ev[0] == "trap":
            sg.sprites.append(("gate_trap", 0.0, 1.0))
    return segs, events


# =====================================================================
# DRAWING THE SCENERY  (everything is drawn with shapes - no image files)
# =====================================================================
def spr_tree(g, s, x, y, k, v, bi):
    if k * 900 < 2:
        return
    L = g.L
    tw = max(1, int(220 * k))
    th = int(1000 * k * v)
    pygame.draw.rect(s, L((105, 72, 42)), (x - tw // 2, y - th, tw, th))
    r = max(2, int(720 * k * v))
    pygame.draw.circle(s, L((30, 135, 50)), (int(x), int(y - th - r * 0.55)), r)
    pygame.draw.circle(s, L((55, 170, 75)), (int(x - r * 0.3), int(y - th - r * 0.85)), max(1, int(r * 0.6)))


def spr_pine(g, s, x, y, k, v, bi):
    if k * 900 < 2:
        return
    L = g.L
    th = int(500 * k * v)
    tw = max(1, int(170 * k))
    pygame.draw.rect(s, L((90, 62, 38)), (x - tw // 2, y - th, tw, th))
    for i in range(3):
        bw = (1700 - i * 380) * k * v
        yb = y - th - i * 800 * k * v
        yt = yb - 1500 * k * v
        pygame.draw.polygon(s, L((18 + i * 8, 90 + i * 14, 48 + i * 6)), [(x - bw / 2, yb), (x + bw / 2, yb), (x, yt)])


def spr_cactus(g, s, x, y, k, v, bi):
    if k * 900 < 2:
        return
    c = g.L((60, 140, 70))
    bw = max(2, int(300 * k))
    bh = int(2100 * k * v)
    pygame.draw.rect(s, c, (x - bw // 2, y - bh, bw, bh), border_radius=max(1, bw // 2))
    aw = max(1, int(220 * k))
    pygame.draw.rect(s, c, (x - bw // 2 - int(380 * k), y - int(1300 * k * v), int(380 * k) + bw // 2, aw))
    pygame.draw.rect(s, c, (x - bw // 2 - int(380 * k), y - int(1900 * k * v), aw, int(640 * k * v)))
    pygame.draw.rect(s, c, (x, y - int(1000 * k * v), int(380 * k), aw))
    pygame.draw.rect(s, c, (x + int(380 * k) - aw // 2 + 1, y - int(1700 * k * v), aw, int(740 * k * v)))


def spr_rock(g, s, x, y, k, v, bi):
    if k * 700 < 2:
        return
    w = 1100 * k * v
    h = 750 * k * v
    pygame.draw.polygon(s, g.L((125, 115, 108)), [(x - w / 2, y), (x - w * 0.35, y - h * 0.8), (x, y - h),
                                                  (x + w * 0.4, y - h * 0.7), (x + w / 2, y)])
    pygame.draw.polygon(s, g.L((95, 88, 82)), [(x, y - h), (x + w * 0.4, y - h * 0.7), (x + w / 2, y), (x + w * 0.1, y)])


def spr_bush(g, s, x, y, k, v, bi):
    r = int(480 * k * v)
    if r < 1:
        return
    c = g.L(BIOMES[bi]["grass"][1])
    c = (min(255, c[0] + 10), min(255, c[1] + 22), min(255, c[2] + 6))
    pygame.draw.circle(s, c, (int(x - r * 0.6), int(y - r * 0.6)), r)
    pygame.draw.circle(s, c, (int(x + r * 0.6), int(y - r * 0.6)), r)
    pygame.draw.circle(s, g.L((40, 120, 60)) if bi != 1 else g.L((150, 130, 70)), (int(x), int(y - r)), r)


def spr_building(g, s, x, y, k, v, bi):
    bw = int(1800 * k)
    bh = int((6000 + 5000 * v) * k)
    if bh < 4:
        return
    pygame.draw.rect(s, g.L((58, 62, 96)), (x - bw // 2, y - bh, bw, bh))
    pygame.draw.rect(s, g.L((40, 44, 74)), (x - bw // 2, y - bh, max(1, bw // 6), bh))
    if bh > 14:
        on = g.night > 0.3
        step = max(4, int(700 * k))
        col = (255, 215, 120) if on else g.L((90, 110, 150))
        for wy in range(int(y - bh) + step // 2, int(y) - step // 2, step):
            for wx in (x - bw // 4, x, x + bw // 4):
                pygame.draw.rect(s, col, (wx - step // 4, wy, max(1, step // 2), max(1, step // 2)))


def spr_lamp(g, s, x, y, k, v, bi):
    h = int(3300 * k)
    if h < 3:
        return
    pw = max(1, int(110 * k))
    pygame.draw.rect(s, g.L((120, 120, 130)), (x - pw // 2, y - h, pw, h))
    hw = int(520 * k)
    pygame.draw.rect(s, g.L((120, 120, 130)), (x - hw // 2, y - h, hw, max(1, pw)))
    on = g.night > 0.25 or g.rain_amt > 0.6
    pygame.draw.circle(s, (255, 240, 170) if on else g.L((200, 200, 190)), (int(x - hw // 2), int(y - h + pw)),
                       max(1, int(190 * k)))


BILLBOARDS = [((235, 70, 70), (255, 230, 90)), ((60, 120, 235), (255, 255, 255)),
              ((70, 180, 100), (255, 255, 255)), ((250, 160, 40), (60, 40, 20))]


def spr_billboard(g, s, x, y, k, v, bi):
    h = int(2900 * k)
    if h < 4:
        return
    L = g.L
    pw = max(1, int(130 * k))
    for dx in (-int(700 * k), int(700 * k)):
        pygame.draw.rect(s, L((90, 90, 95)), (x + dx - pw // 2, y - int(2200 * k), pw, int(2200 * k)))
    pw_, ph_ = int(2000 * k), int(1000 * k)
    a, b = BILLBOARDS[int(v * 1000) % len(BILLBOARDS)]
    top = y - h
    pygame.draw.rect(s, L(a), (x - pw_ // 2, top, pw_, ph_))
    pygame.draw.rect(s, b, (x - pw_ // 2 + pw_ // 10, top + ph_ // 4, pw_ * 6 // 10, max(1, ph_ // 5)))
    pygame.draw.circle(s, b, (int(x + pw_ * 0.32), int(top + ph_ // 2)), max(1, ph_ // 4))
    pygame.draw.rect(s, L((40, 40, 45)), (x - pw_ // 2, top, pw_, ph_), 1)


def spr_arrow(g, s, x, y, k, v, bi):
    h = int(1900 * k)
    if h < 4:
        return
    pw = max(1, int(110 * k))
    pygame.draw.rect(s, g.L((120, 120, 125)), (x - pw // 2, y - int(1100 * k), pw, int(1100 * k)))
    bsz = int(1000 * k)
    top = y - h
    pygame.draw.rect(s, g.L((250, 210, 40)), (x - bsz // 2, top, bsz, bsz))
    d = v
    pts = [(x - d * bsz * 0.18, top + bsz * 0.2), (x + d * bsz * 0.18, top + bsz * 0.5), (x - d * bsz * 0.18, top + bsz * 0.8)]
    pygame.draw.lines(s, (30, 30, 30), False, pts, max(1, int(bsz * 0.12)))


def spr_gate_cp(g, s, x, y, k, v, bi):
    half = int(1.12 * ROAD_W * k)
    h = int(3500 * k)
    if h < 4:
        return
    pw = max(2, int(260 * k))
    for sx in (x - half, x + half):
        pygame.draw.rect(s, g.L((230, 230, 240)), (sx - pw // 2, y - h, pw, h))
    bh = max(2, int(700 * k))
    n = 16
    cw = (half * 2) / n
    for i in range(n):
        for j in range(2):
            c = (255, 255, 255) if (i + j) % 2 == 0 else (30, 30, 30)
            pygame.draw.rect(s, g.L(c), (x - half + i * cw, y - h + j * bh / 2, cw + 1, bh / 2 + 1))
    pygame.draw.rect(s, (60, 200, 255), (x - half, y - h + bh, half * 2, max(1, bh // 4)))


def spr_gate_trap(g, s, x, y, k, v, bi):
    half = int(1.1 * ROAD_W * k)
    h = int(3300 * k)
    if h < 4:
        return
    pw = max(2, int(230 * k))
    for sx in (x - half, x + half):
        pygame.draw.rect(s, g.L((90, 90, 100)), (sx - pw // 2, y - h, pw, h))
    bh = max(2, int(520 * k))
    n = 14
    cw = (half * 2) / n
    for i in range(n):
        pygame.draw.rect(s, (255, 150, 30) if i % 2 == 0 else (25, 25, 25), (x - half + i * cw, y - h, cw + 1, bh))
    bw = int(900 * k)
    pygame.draw.rect(s, g.L((70, 70, 80)), (x - bw // 2, y - h + bh, bw, int(520 * k)))
    pygame.draw.circle(s, (255, 40, 40), (int(x), int(y - h + bh + 260 * k)), max(1, int(170 * k)))


SPRITE_FN = {"tree": spr_tree, "pine": spr_pine, "cactus": spr_cactus, "rock": spr_rock, "bush": spr_bush,
             "building": spr_building, "lamp": spr_lamp, "billboard": spr_billboard, "arrow": spr_arrow,
             "gate_cp": spr_gate_cp, "gate_trap": spr_gate_trap}


def draw_car(s, cx, by, w, body, L, brake=False, skew=0.0, boost=0.0, spoiler=False, light=None):
    """Rear view of a car. cx = centre, by = ground line, w = width in pixels."""
    def P(px, py):
        return (cx + px * w + skew * py * w, by - py * w)

    pygame.draw.ellipse(s, L((15, 15, 18)), (cx - w * 0.56, by - w * 0.08, w * 1.12, w * 0.17))
    wheel = (24, 24, 28)
    pygame.draw.polygon(s, wheel, [P(-0.50, 0), P(-0.36, 0), P(-0.36, 0.2), P(-0.50, 0.2)])
    pygame.draw.polygon(s, wheel, [P(0.36, 0), P(0.50, 0), P(0.50, 0.2), P(0.36, 0.2)])
    bc = L(body)
    pygame.draw.polygon(s, bc, [P(-0.48, 0.08), P(0.48, 0.08), P(0.46, 0.36), P(-0.46, 0.36)])
    dark = L((int(body[0] * 0.55), int(body[1] * 0.55), int(body[2] * 0.55)))
    pygame.draw.polygon(s, dark, [P(-0.47, 0.08), P(0.47, 0.08), P(0.47, 0.16), P(-0.47, 0.16)])
    cab = L((int(body[0] * 0.8), int(body[1] * 0.8), int(body[2] * 0.8)))
    pygame.draw.polygon(s, cab, [P(-0.34, 0.36), P(0.34, 0.36), P(0.26, 0.57), P(-0.26, 0.57)])
    pygame.draw.polygon(s, L((38, 50, 78)), [P(-0.29, 0.39), P(0.29, 0.39), P(0.22, 0.54), P(-0.22, 0.54)])
    tl = (255, 70, 70) if brake else (190, 25, 35)
    pygame.draw.polygon(s, tl, [P(-0.46, 0.22), P(-0.28, 0.22), P(-0.28, 0.32), P(-0.46, 0.32)])
    pygame.draw.polygon(s, tl, [P(0.28, 0.22), P(0.46, 0.22), P(0.46, 0.32), P(0.28, 0.32)])
    if spoiler:
        pygame.draw.polygon(s, dark, [P(-0.44, 0.40), P(0.44, 0.40), P(0.44, 0.45), P(-0.44, 0.45)])
        pygame.draw.polygon(s, dark, [P(-0.40, 0.36), P(-0.36, 0.36), P(-0.36, 0.42), P(-0.40, 0.42)])
        pygame.draw.polygon(s, dark, [P(0.36, 0.36), P(0.40, 0.36), P(0.40, 0.42), P(0.36, 0.42)])
    if light:
        pygame.draw.polygon(s, light, [P(-0.12, 0.57), P(0.12, 0.57), P(0.10, 0.62), P(-0.10, 0.62)])
    if boost > 0:
        r = max(2, int(w * (0.05 + 0.04 * boost)))
        for px in (-0.2, 0.2):
            x, y = P(px, 0.1)
            pygame.draw.circle(s, (255, 150, 40), (int(x), int(y + w * 0.05)), r)
            pygame.draw.circle(s, (255, 245, 170), (int(x), int(y + w * 0.05)), max(1, r // 2))


# =====================================================================
# THE GAME
# =====================================================================
class Car:
    __slots__ = ("z", "off", "speed", "color", "rival", "rel")

    def __init__(self, z, off, speed, color, rival):
        self.z = z
        self.off = off
        self.speed = speed
        self.color = color
        self.rival = rival
        self.rel = 99999.0


class Game:
    def __init__(self, screen, controls):
        self.screen = screen
        self.controls = controls
        self.surf = pygame.Surface((RW, RH))
        self.dim = pygame.Surface((RW, RH))
        self.dim.fill((0, 0, 0))
        self.dim.set_alpha(150)
        self.panel = pygame.Surface((440, 270))
        self.panel.fill((0, 0, 20))
        self.panel.set_alpha(120)
        self.sounds = Sounds()
        self.segs, self.events = build_track()
        self.N = len(self.segs)
        self.track_len = self.N * SEG
        self.high = load_high_score()
        self.t = 0.0
        self.state = "title"
        self.car_idx = 0
        self.menu_cd = 0.0
        self.draw_n = DRAW_MAX
        self.ft_avg = 1 / 60
        self.q_count = 0
        rng = random.Random(5)
        self.stars = [(rng.randint(0, RW), rng.randint(0, RH // 2), rng.choice((1, 1, 2))) for _ in range(70)]
        self.mtn = self.make_mountains()
        self.bg_off = [0.0, 0.0]
        self.tod = 0.0
        self.rain = False
        self.rain_amt = 0.0
        self.rain_t = 45.0
        self.drops = [[random.uniform(0, RW), random.uniform(0, RH)] for _ in range(70)]
        self.pal = {}
        self.pal_key = None
        self.L = lambda c: c
        self.E = lambda c: c
        self.night = 0.0
        self.sky_top = self.sky_bot = self.fog = (0, 0, 0)
        self.tint = (1, 1, 1)
        self.cur_biome = 0
        self.reset_run()
        self.update_lighting()

    # ------------------------------------------------------------ setup
    def make_mountains(self):
        rng = random.Random(3)
        layers = []
        for amp, base, par, step in ((46, 24, 0.03, 16), (30, 10, 0.07, 12)):
            m = (RW * 3) // step
            ph = [rng.uniform(0, 6.28) for _ in range(3)]
            hs = []
            for i in range(m):
                a = i / m * 2 * math.pi
                h = base + amp * (0.5 + 0.3 * math.sin(a * 3 + ph[0]) + 0.15 * math.sin(a * 7 + ph[1])
                                  + 0.05 * math.sin(a * 13 + ph[2]))
                hs.append(h * RH / 480)
            layers.append((hs, step, par))
        return layers

    def reset_run(self):
        self.car = CARS[self.car_idx]
        self.pos = 0.0
        self.x = 0.0
        self.speed = 0.0
        self.steer_s = 0.0
        self.drift_t = 0.0
        self.drift_grace = 0.0
        self.drift_vis = 0.0
        self.boost_t = 0.0
        self.nitro = 30.0
        self.crash_t = 0.0
        self.invuln = 0.0
        self.flash = 0.0
        self.time_left = float(START_TIME)
        self.total = 0
        self.xp = 0
        self.level = 1
        self.chain_pts = 0.0
        self.chain_kinds = set()
        self.chain_timer = 0.0
        self.popups = []
        self.banner = None
        self.particles = []
        self.dist = 0.0
        self.lap = 1
        self.draft_t = 0.0
        self.top_speed = 0
        self.longest_drift = 0.0
        self.best_chain = 0
        self.near_count = 0
        self.crashes = 0
        self.finish_t = 0.0
        self.in_brake = self.in_nitro = False
        self.new_record = False
        self.cd = 3.4
        self.last_count = 4
        self.spawn_traffic()

    def spawn_traffic(self):
        rng = random.Random(11)
        self.cars = []
        for off, spd, gmin, gmax, rival in LANES_CFG:
            z = rng.uniform(7500, 9500)
            while z < self.track_len - 2500:
                col = (255, 200, 40) if rival else rng.choice(TRAFFIC_COLORS)
                self.cars.append(Car(z, off, spd, col, rival))
                z += rng.uniform(gmin, gmax)

    # ------------------------------------------------------------ helpers
    def popup(self, text, color=(255, 255, 255)):
        self.popups.insert(0, [text, color, 2.6])
        del self.popups[5:]

    def show_banner(self, text, sub="", color=(255, 220, 80)):
        self.banner = [text, sub, color, 2.4]

    def add_skill(self, kind, pts, label=None, color=(255, 230, 120)):
        self.chain_kinds.add(kind)
        self.chain_pts += pts
        self.chain_timer = 3.0
        if label:
            self.popup(label, color)

    def bank_chain(self):
        mult = len(self.chain_kinds)
        pts = int(self.chain_pts * mult)
        if pts > 0:
            self.add_total(pts)
            self.best_chain = max(self.best_chain, pts)
            self.popup("+%d BANKED  x%d" % (pts, mult), (120, 255, 150))
            self.sounds.play("bank")
        self.chain_pts = 0.0
        self.chain_kinds = set()
        self.chain_timer = 0.0

    def add_total(self, pts):
        self.total += pts
        self.xp += pts
        need = 800 * self.level
        while self.xp >= need:
            self.xp -= need
            self.level += 1
            need = 800 * self.level
            self.time_left += 8
            self.nitro = 100.0
            self.show_banner("LEVEL UP!  LV %d" % self.level, "+8 seconds, nitro refilled", (255, 120, 220))
            self.sounds.play("level")

    def crash(self, label, new_speed):
        self.speed = new_speed
        self.crash_t = 1.0
        self.invuln = 1.2
        self.flash = 0.35
        self.crashes += 1
        self.draft_t = 0.0
        if self.chain_pts > 0:
            self.popup("CHAIN LOST!", (255, 90, 90))
        self.chain_pts = 0.0
        self.chain_kinds = set()
        self.chain_timer = 0.0
        self.popup(label, (255, 120, 90))
        self.sounds.play("crash")
        for _ in range(26):
            self.particles.append([RW / 2 + random.uniform(-70, 70), RH - 50, random.uniform(-180, 180),
                                   random.uniform(-260, -40), random.uniform(0.4, 0.9), (255, 190, 80), 4])

    def seg_at(self, z):
        return self.segs[int(z // SEG) % self.N]

    # ------------------------------------------------------------ lighting / weather
    def update_lighting(self):
        tod = self.tod
        top, bot, tint = SKY[0][1], SKY[0][2], SKY[0][3]
        for i in range(len(SKY) - 1):
            a, b = SKY[i], SKY[i + 1]
            if a[0] <= tod <= b[0]:
                t = (tod - a[0]) / (b[0] - a[0]) if b[0] > a[0] else 0.0
                top = lerp_col(a[1], b[1], t)
                bot = lerp_col(a[2], b[2], t)
                tint = tuple(lerp(a[3][j], b[3][j], t) for j in range(3))
                break
        ra = self.rain_amt
        if ra > 0:
            top = lerp_col(top, (95, 100, 115), 0.55 * ra)
            bot = lerp_col(bot, (130, 135, 148), 0.55 * ra)
            tint = tuple(c * (1 - 0.16 * ra) for c in tint)
        self.sky_top, self.sky_bot, self.tint = top, bot, tint
        self.fog = bot
        self.night = clamp((1.0 - tint[0]) * 2.0, 0.0, 1.0)
        key = (int(tod * 150), int(ra * 8))
        if key != self.pal_key:
            self.pal.clear()
            self.pal_key = key
        tr, tg, tb = tint
        self.L = lambda c: (int(c[0] * tr), int(c[1] * tg), int(c[2] * tb))
        er, eg, eb = max(tr, 0.82), max(tg, 0.82), max(tb, 0.88)
        self.E = lambda c: (int(c[0] * er), int(c[1] * eg), int(c[2] * eb))

    def make_pal(self, biome, dark, bucket):
        B = BIOMES[biome]
        i = 1 if dark else 0
        f = bucket / 8.0 * 0.9
        fog = self.fog
        L, E = self.L, self.E
        pal = (lerp_col(L(B["grass"][i]), fog, f), lerp_col(L(B["road"][i]), fog, f),
               lerp_col(E(B["rumble"][i]), fog, f), lerp_col(E(B["lane"]), fog, f))
        self.pal[(biome, dark, bucket)] = pal
        return pal

    def world_tick(self, dt, curve, pct):
        self.tod = (self.tod + dt / CYCLE_SECONDS) % 1.0
        self.rain_t -= dt
        if self.rain_t <= 0:
            if self.rain:
                self.rain = False
                self.rain_t = random.uniform(35, 70)
            elif random.random() < 0.6:
                self.rain = True
                self.rain_t = random.uniform(22, 40)
            else:
                self.rain_t = random.uniform(15, 30)
        target = 1.0 if self.rain else 0.0
        self.rain_amt += clamp(target - self.rain_amt, -dt / 3, dt / 3)
        for li in range(2):
            self.bg_off[li] += curve * pct * dt * (40 + li * 45)
        if self.rain_amt > 0.02:
            for d in self.drops:
                d[1] += 700 * dt
                d[0] -= 120 * dt
                if d[1] > RH:
                    d[0], d[1] = random.uniform(0, RW + 60), random.uniform(-30, 0)
        self.update_lighting()

    def move_traffic(self, dt):
        L = self.track_len
        for c in self.cars:
            c.z = (c.z + c.speed * dt) % L

    # ------------------------------------------------------------ update
    def update(self, dt):
        self.t += dt
        ax, ay = self.controls.axes()
        pressed = self.controls.button_pressed()
        held = self.controls.button_down()
        self.ft_avg = self.ft_avg * 0.93 + dt * 0.07
        self.q_count += 1
        if self.q_count >= 12:
            self.q_count = 0
            if self.ft_avg > 1 / 50 and self.draw_n > DRAW_MIN:
                self.draw_n = max(DRAW_MIN, self.draw_n - 6)
            elif self.ft_avg < 1 / 58 and self.draw_n < DRAW_MAX:
                self.draw_n = min(DRAW_MAX, self.draw_n + 2)

        for p in self.particles:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[4] -= dt
        self.particles = [p for p in self.particles if p[4] > 0]
        for p in self.popups:
            p[2] -= dt
        self.popups = [p for p in self.popups if p[2] > 0]
        if self.banner:
            self.banner[3] -= dt
            if self.banner[3] <= 0:
                self.banner = None
        self.flash = max(0.0, self.flash - dt)

        if self.state == "title":
            self.update_title(dt, ax, pressed)
        elif self.state == "countdown":
            self.update_countdown(dt)
        elif self.state == "playing":
            self.update_play(dt, ax, ay, held)
        elif self.state == "finish":
            self.update_finish(dt, pressed)

    def update_title(self, dt, ax, pressed):
        self.menu_cd = max(0.0, self.menu_cd - dt)
        if ax != 0 and self.menu_cd == 0:
            self.car_idx = (self.car_idx + (1 if ax > 0 else -1)) % len(CARS)
            self.menu_cd = 0.3
            self.sounds.play("count")
        self.car = CARS[self.car_idx]
        # the road drives itself in the background
        self.speed = 5200.0
        self.pos = (self.pos + self.speed * dt) % self.track_len
        self.x = 0.3 * math.sin(self.t * 0.6)
        self.move_traffic(dt)
        seg = self.seg_at(self.pos + PLAYER_Z)
        self.cur_biome = seg.biome
        self.world_tick(dt, seg.curve, 0.5)
        if pressed:
            self.reset_run()
            self.state = "countdown"

    def update_countdown(self, dt):
        self.cd -= dt
        n = int(math.ceil(self.cd))
        if n < self.last_count and n >= 1:
            self.last_count = n
            self.sounds.play("count")
        self.world_tick(dt, 0, 0)
        if self.cd <= 0:
            self.state = "playing"
            self.sounds.play("go")
            self.show_banner("GO!", "", (120, 255, 150))
            self.banner[3] = 1.0

    def update_play(self, dt, ax, ay, held):
        C = self.car
        max_v = C["speed"]
        total_len = self.track_len
        self.time_left -= dt
        steer = clamp(ax * 1.25, -1.0, 1.0)
        self.steer_s += (steer - self.steer_s) * min(1.0, dt * 9)
        brake = ay > 0.45
        nitro_in = ay < -0.45
        self.in_brake, self.in_nitro = brake, nitro_in
        sp = self.speed
        pct = sp / max_v
        prev_ppos = self.pos + PLAYER_Z
        seg = self.seg_at(prev_ppos)
        self.cur_biome = seg.biome
        self.invuln = max(0.0, self.invuln - dt)
        self.crash_t = max(0.0, self.crash_t - dt)

        # ---- drifting ----
        want = held and sp > 0.40 * max_v and abs(self.steer_s) > 0.18 and self.crash_t <= 0
        if want:
            if self.drift_t == 0:
                self.popup("DRIFT!", (255, 200, 60))
            self.drift_t += dt
            self.drift_grace = 0.25
            self.longest_drift = max(self.longest_drift, self.drift_t)
            self.add_skill("drift", 120 * pct * (1 + 0.5 * self.drift_t) * C["drift"] * dt)
            self.nitro = min(100.0, self.nitro + 9 * dt * C["drift"])
            sp -= max_v * 0.07 * dt
            sgn = 1 if self.steer_s > 0 else -1
            self.drift_vis += (sgn - self.drift_vis) * min(1.0, dt * 8)
            if random.random() < 0.7:
                for sx in (-0.42, 0.42):
                    self.particles.append([RW / 2 + sx * 190 + self.drift_vis * 30, RH - 20,
                                           -sgn * random.uniform(20, 90), random.uniform(-70, -10),
                                           random.uniform(0.4, 0.8), (225, 225, 230), 5])
        else:
            self.drift_vis -= self.drift_vis * min(1.0, dt * 6)
            if self.drift_t > 0:
                self.drift_grace -= dt
                if self.drift_grace <= 0:
                    if self.drift_t > 0.9:
                        self.boost_t = min(1.8, 0.5 + 0.3 * self.drift_t)
                        self.popup("DRIFT BOOST!", (90, 220, 255))
                        self.sounds.play("boost")
                    self.drift_t = 0.0

        # ---- steering and corners ----
        dxs = dt * 2 * pct * C["steer"] * (1.7 if want else 1.0)
        self.x += dxs * self.steer_s
        cent = 0.3 * C["grip"] * (0.25 if want else 1.0)
        self.x -= dt * 2 * pct * pct * seg.curve * cent

        # ---- speed ----
        boost_on = self.boost_t > 0 or (nitro_in and self.nitro > 0)
        if nitro_in and self.nitro > 0:
            self.nitro = max(0.0, self.nitro - 30 * dt)
        if self.boost_t > 0:
            self.boost_t -= dt
        cap = max_v * (1.32 if boost_on else 1.0)
        if brake:
            sp = max(0.0, sp - max_v * 1.3 * dt)
        elif sp < cap:
            sp = min(cap, sp + (max_v / 1.6 if boost_on else max_v / 4.5 * C["acc"]) * dt)
        else:
            sp = max(cap, sp - 0.6 * max_v * dt)
        off_road = abs(self.x) > 1.0
        if off_road and sp > 0.28 * max_v:
            sp -= 0.65 * max_v * dt
            if random.random() < 0.8:
                self.particles.append([RW / 2 + random.uniform(-90, 90), RH - 20, random.uniform(-60, 60),
                                       random.uniform(-120, -30), random.uniform(0.3, 0.6), (150, 120, 80), 4])
        self.x = clamp(self.x, -2.0, 2.0)
        self.speed = sp
        self.pos = (self.pos + sp * dt) % total_len
        self.dist += sp * dt
        self.top_speed = max(self.top_speed, int(sp * KMH))
        ppos = self.pos + PLAYER_Z

        # ---- things we drive past: checkpoints, traps, scenery ----
        pi = int(prev_ppos // SEG)
        ni = int(ppos // SEG)
        steps = (ni - pi) % self.N
        if steps > 40:
            steps = 0
        for i in range(1, steps + 1):
            idx = (pi + i) % self.N
            ev = self.events.get(idx)
            if ev:
                self.handle_event(ev, sp)
            if self.invuln <= 0:
                for kind, off, _v in self.segs[idx].sprites:
                    half = SOLID_HALF.get(kind)
                    if half and abs(off) < 2.3 and abs(self.x - off) < half + 0.14:
                        self.x += -0.25 if off > 0 else 0.25
                        self.crash("CRASH!", 0.18 * max_v)
                        break

        # ---- traffic ----
        draft = False
        for c in self.cars:
            c.z = (c.z + c.speed * dt) % total_len
            rel = wrap_dist(c.z - ppos, total_len)
            prev = c.rel
            c.rel = rel
            if abs(rel) > 2500 and abs(prev) > 2500:
                continue
            lat = abs(self.x - c.off)
            if self.invuln <= 0 and self.speed > c.speed and prev >= -60 and rel <= 200 and lat < 0.30:
                self.pos = (c.z - 260 - PLAYER_Z) % total_len
                self.crash("CRASH!", c.speed * 0.8)
                continue
            if prev >= 0 and rel < 0 and self.speed > c.speed + 1200:
                if c.rival:
                    self.add_skill("rival", 250, "RIVAL PASSED  +250", (255, 215, 80))
                    self.nitro = min(100.0, self.nitro + 12)
                    self.sounds.play("near")
                elif lat < 0.55:
                    pts = 100 * max(0.4, pct)
                    self.near_count += 1
                    self.add_skill("near", pts, "NEAR MISS  +%d" % pts, (255, 255, 255))
                    self.nitro = min(100.0, self.nitro + 8)
                    self.sounds.play("near")
            if 150 < rel < 1300 and lat < 0.25 and self.speed > c.speed * 1.1:
                draft = True
        if draft and self.crash_t <= 0:
            if self.draft_t == 0:
                self.popup("SLIPSTREAM!", (150, 220, 255))
            self.draft_t += dt
            self.add_skill("draft", 70 * dt)
            self.nitro = min(100.0, self.nitro + 12 * dt)
        else:
            self.draft_t = 0.0

        # ---- skill chain ----
        if self.chain_kinds:
            self.chain_timer -= dt
            if self.chain_timer <= 0:
                self.bank_chain()

        self.world_tick(dt, seg.curve, pct)
        if self.time_left <= 0:
            self.time_left = 0.0
            self.end_run()

    def handle_event(self, ev, sp):
        kind = ev[0]
        if kind == "cp":
            self.time_left += CHECKPOINT_BONUS
            self.add_total(300)
            self.show_banner("CHECKPOINT!", "+%d seconds" % CHECKPOINT_BONUS, (90, 220, 255))
            self.sounds.play("check")
        elif kind == "trap":
            kmh = int(sp * KMH)
            if kmh >= TRAP_MIN_KMH:
                pts = 200 + (kmh - TRAP_MIN_KMH) * 5
                self.add_skill("trap", pts, "SPEED TRAP  %d KM/H  +%d" % (kmh, pts), (255, 170, 60))
                self.nitro = min(100.0, self.nitro + 20)
                self.sounds.play("trap")
            else:
                self.popup("SPEED TRAP  %d km/h - too slow" % kmh, (170, 170, 180))
        elif kind == "biome":
            b = ev[1]
            if b == 0 and self.dist > 100000:
                self.lap += 1
            self.show_banner(BIOMES[b]["name"], "LAP %d" % self.lap, (255, 255, 255))

    def end_run(self):
        if self.chain_kinds:
            self.bank_chain()
        self.state = "finish"
        self.finish_t = 0.0
        self.sounds.play("over")
        if self.total > self.high:
            self.high = self.total
            self.new_record = True
            save_high_score(self.total)

    def update_finish(self, dt, pressed):
        self.finish_t += dt
        sp = max(0.0, self.speed - self.car["speed"] * 0.5 * dt)
        self.speed = sp
        self.pos = (self.pos + sp * dt) % self.track_len
        self.x -= self.x * min(1.0, dt * 0.8)
        self.move_traffic(dt)
        seg = self.seg_at(self.pos + PLAYER_Z)
        self.world_tick(dt, seg.curve, sp / self.car["speed"])
        if self.finish_t > 3.0 and pressed:
            self.state = "title"
            self.pos = 0.0

    # ------------------------------------------------------------ drawing
    def render_scene(self):
        s = self.surf
        hz = RH // 2
        L = self.L
        top, bot = self.sky_top, self.sky_bot
        bands = 14
        bh = hz // bands + 1
        for i in range(bands):
            s.fill(lerp_col(top, bot, i / (bands - 1)), (0, i * bh, RW, bh))
        if self.night > 0.12:
            c = int(255 * self.night)
            for x, y, r in self.stars:
                s.fill((c, c, c), (x, y, r, r))
        self.draw_sky_bodies(s, hz)
        B = BIOMES[self.cur_biome]
        for li, (hs, step, par) in enumerate(self.mtn):
            m = len(hs)
            off = self.bg_off[li]
            start = int(off // step) % m
            sub = int(off % step)
            n = RW // step + 3
            pts = [(-sub - step, hz + 2)]
            pts += [(-sub + i * step, hz - hs[(start + i) % m]) for i in range(n)]
            pts.append((-sub + n * step, hz + 2))
            col = lerp_col(L(B["mtn"][li]), self.fog, 0.45 if li == 0 else 0.2)
            pygame.draw.polygon(s, col, pts)
        s.fill(self.fog, (0, hz, RW, RH - hz))
        self.render_road()

    def draw_sky_bodies(self, s, hz):
        tod = self.tod
        scale = RH / 480.0
        h = None
        if tod <= 0.58:
            h = 150 * (1 - tod / 0.58)
        elif tod >= 0.9:
            h = 150 * (tod - 0.9) / 0.1
        if h is not None:
            col = lerp_col((255, 120, 60), (255, 246, 200), clamp(h / 80, 0, 1))
            pygame.draw.circle(s, col, (int(RW * 0.68), int(hz - 6 - h * scale)), int(26 * scale))
        if 0.56 <= tod <= 0.94:
            t = (tod - 0.56) / 0.38
            mh = 150 * math.sin(math.pi * t)
            mx, my = int(RW * 0.3), int(hz - 6 - mh * scale)
            pygame.draw.circle(s, (235, 235, 250), (mx, my), int(17 * scale))
            pygame.draw.circle(s, self.sky_top, (mx + 6, my - 3), int(15 * scale))

    def render_road(self):
        s = self.surf
        segs = self.segs
        N = self.N
        nb = self.draw_n
        pos = self.pos
        base_idx = int(pos // SEG)
        frac = pos - base_idx * SEG
        base = segs[base_idx % N]
        ppos = pos + PLAYER_Z
        pi = int(ppos // SEG)
        pa, pb = segs[pi % N], segs[(pi + 1) % N]
        player_y = pa.y1 + (pb.y1 - pa.y1) * ((ppos - pi * SEG) / SEG)
        cam_y = player_y + CAM_H
        cam_x = self.x * ROAD_W
        hw, hh = RW / 2, RH / 2

        bx = [0.0] * (nb + 2)
        by = [0.0] * (nb + 2)
        bw = [0.0] * (nb + 2)
        bs = [0.0] * (nb + 2)
        bz = [0.0] * (nb + 2)
        xo = 0.0
        dx = -(base.curve * frac / SEG)
        for b in range(nb + 1):
            si = base_idx + b
            sg = segs[si % N]
            z = si * SEG - pos
            bz[b] = z
            if z > 150:
                sc = CAM_DEPTH / z
                bs[b] = sc
                bx[b] = hw + sc * (xo - cam_x) * hw
                by[b] = hh - sc * (sg.y1 - cam_y) * hh
                bw[b] = sc * ROAD_W * hw
            xo += dx
            dx += sg.curve

        maxy = RH
        clips = [RH] * (nb + 1)
        pal_cache = self.pal
        poly = pygame.draw.polygon
        rumble_far = int(nb * 0.7)
        lane_far = int(nb * 0.5)
        for b in range(nb):
            clips[b] = maxy
            if bs[b] <= 0 or bs[b + 1] <= 0:
                continue
            y1 = by[b]
            y2 = by[b + 1]
            if y2 >= y1 or y2 >= maxy:
                continue
            sg = segs[(base_idx + b) % N]
            bucket = min(7, int((b / nb) ** 1.6 * 8))
            pal = pal_cache.get((sg.biome, sg.dark, bucket)) or self.make_pal(sg.biome, sg.dark, bucket)
            x1, x2, w1, w2 = bx[b], bx[b + 1], bw[b], bw[b + 1]
            iy2 = int(y2)
            s.fill(pal[0], (0, iy2, RW, int(y1) - iy2 + 1))
            if b < rumble_far:
                r1, r2 = w1 / 6, w2 / 6
                poly(s, pal[2], [(x1 - w1 - r1, y1), (x1 - w1, y1), (x2 - w2, y2), (x2 - w2 - r2, y2)])
                poly(s, pal[2], [(x1 + w1 + r1, y1), (x1 + w1, y1), (x2 + w2, y2), (x2 + w2 + r2, y2)])
            poly(s, pal[1], [(x1 - w1, y1), (x1 + w1, y1), (x2 + w2, y2), (x2 - w2, y2)])
            if not sg.dark and b < lane_far:
                l1, l2 = w1 / 32, w2 / 32
                for ln in (1, 2, 3):
                    f = ln / 4.0
                    cx1 = x1 - w1 + 2 * w1 * f
                    cx2 = x2 - w2 + 2 * w2 * f
                    poly(s, pal[3], [(cx1 - l1, y1), (cx1 + l1, y1), (cx2 + l2, y2), (cx2 - l2, y2)])
            maxy = y2

        # ---- scenery and cars, far to near ----
        cars_at = {}
        reach = (nb - 2) * SEG
        tl = self.track_len
        for c in self.cars:
            d = (c.z - pos) % tl
            if d < reach:
                cars_at.setdefault(int((d + frac) // SEG), []).append((d, c))
        L = self.L
        t = self.t
        for b in range(nb - 1, 0, -1):
            sc = bs[b]
            if sc <= 0:
                continue
            sg = segs[(base_idx + b) % N]
            clip = clips[b]
            sy = by[b]
            k = sc * hw
            need_clip = clip < sy
            if need_clip:
                s.set_clip(pygame.Rect(0, 0, RW, max(0, int(clip))))
            for kind, off, v in sg.sprites:
                x = bx[b] + sc * off * ROAD_W * hw
                if -400 < x < RW + 400:
                    SPRITE_FN[kind](self, s, x, sy, k, v, sg.biome)
            if need_clip:
                s.set_clip(None)
            lst = cars_at.get(b)
            if lst:
                for d, c in lst:
                    p = ((d + frac) % SEG) / SEG
                    sc2 = bs[b] + (bs[b + 1] - bs[b]) * p
                    cx = bx[b] + (bx[b + 1] - bx[b]) * p + sc2 * c.off * ROAD_W * hw
                    cy = by[b] + (by[b + 1] - by[b]) * p
                    w = CAR_W * sc2 * hw
                    if w < 3 or not (-100 < cx < RW + 100):
                        continue
                    if cy > clip:
                        s.set_clip(pygame.Rect(0, 0, RW, max(0, int(clip))))
                        need = True
                    else:
                        need = False
                    light = None
                    if c.rival:
                        light = (255, 40, 40) if int(t * 6) % 2 else (60, 90, 255)
                    draw_car(s, cx, cy, w, c.color, L, light=light)
                    if need:
                        s.set_clip(None)

        if self.state in ("playing", "finish", "countdown"):
            self.draw_player(s)
        self.draw_effects(s)

    def draw_player(self, s):
        C = self.car
        w = CAR_W * (CAM_DEPTH / PLAYER_Z) * RW / 2
        by = RH - 16
        bounce = 0
        if abs(self.x) > 1.0 and self.speed > 1000:
            bounce = random.randint(-3, 0)
        elif self.speed > 500:
            bounce = int(math.sin(self.t * 40) * 0.8)
        skew = self.drift_vis * 0.22
        if self.crash_t > 0:
            skew = math.sin(self.crash_t * 22) * 0.35 * min(1.0, self.crash_t * 2)
        if self.crash_t > 0 and self.invuln > 0 and int(self.t * 14) % 2 == 0:
            return
        braking = self.state != "playing" or self.in_brake
        boost_on = self.boost_t > 0 or (self.state == "playing" and self.in_nitro and self.nitro > 0)
        cx = RW / 2 + self.steer_s * 6
        draw_car(s, cx, by + bounce, w, C["color"], self.L, brake=braking, skew=skew,
                 boost=(1.0 + math.sin(self.t * 30) * 0.4) if boost_on else 0.0, spoiler=True)

    def draw_effects(self, s):
        for x, y, vx, vy, life, col, size in self.particles:
            r = max(1, int(size * (1.6 - life)))
            pygame.draw.circle(s, self.L(col) if col != (255, 190, 80) else col, (int(x), int(y)), r)
        boosting = self.state == "playing" and (self.boost_t > 0 or (self.in_nitro and self.nitro > 0))
        if boosting or self.speed > self.car["speed"] * 0.97:
            f = clamp(self.speed / (self.car["speed"] * 1.3), 0, 1)
            col = (255, 255, 255)
            for _ in range(14):
                a = random.uniform(0, 2 * math.pi)
                r0 = random.uniform(190, 250)
                r1 = r0 + 30 + 70 * f
                cx, cy = RW / 2, RH * 0.52
                pygame.draw.line(s, col, (cx + math.cos(a) * r0, cy + math.sin(a) * r0 * 0.8),
                                 (cx + math.cos(a) * r1, cy + math.sin(a) * r1 * 0.8), 1)
        if self.rain_amt > 0.05:
            n = int(len(self.drops) * self.rain_amt)
            col = (170, 185, 215)
            for x, y in self.drops[:n]:
                pygame.draw.line(s, col, (x, y), (x + 4, y - 16), 1)
        if self.flash > 0:
            pygame.draw.rect(s, (255, 60, 60), (0, 0, RW, RH), int(10 * self.flash / 0.35) + 1)

    # ------------------------------------------------------------ HUD
    def render_hud(self):
        s = self.surf
        white = (255, 255, 255)
        # skill chain
        draw_text(s, "SKILL CHAIN", 20, (255, 220, 90), topleft=(12, 8))
        if self.chain_kinds:
            draw_text(s, "%d  x%d" % (int(self.chain_pts), len(self.chain_kinds)), 40, white, topleft=(12, 24))
            w = int(130 * clamp(self.chain_timer / 3.0, 0, 1))
            pygame.draw.rect(s, (40, 40, 60), (12, 56, 130, 7))
            pygame.draw.rect(s, (255, 220, 90), (12, 56, w, 7))
        else:
            draw_text(s, "drift, dodge, pass!", 22, (170, 170, 200), topleft=(12, 28))
        # time
        t = self.time_left
        tc = white if t >= 10 or int(self.t * 4) % 2 == 0 else (255, 70, 70)
        if t < 10 and self.state == "playing":
            tc = (255, 90, 90) if int(self.t * 4) % 2 == 0 else white
        draw_text(s, "TIME", 18, (200, 205, 240), center=(RW // 2, 12))
        draw_text(s, str(int(math.ceil(t))), 56, tc, center=(RW // 2, 40))
        # score / level
        draw_text(s, "{:,}".format(self.total), 36, white, topright=(RW - 12, 6))
        draw_text(s, "LV %d" % self.level, 22, (255, 220, 90), topright=(RW - 12, 34))
        need = 800 * self.level
        pygame.draw.rect(s, (40, 40, 60), (RW - 112, 58, 100, 6))
        pygame.draw.rect(s, (255, 120, 220), (RW - 112, 58, int(100 * clamp(self.xp / need, 0, 1)), 6))
        # speedometer
        cx, cy, r = RW - 80, RH - 64, 54
        frac = clamp(self.speed / (self.car["speed"] * 1.32), 0, 1)
        n = 22
        boost = self.boost_t > 0 or (self.nitro > 0 and self.state == "playing" and self.in_nitro)
        for i in range(n):
            a = math.radians(210 - i * 240 / (n - 1))
            lit = i <= frac * (n - 1)
            if not lit:
                col = (60, 62, 80)
            elif boost:
                col = (90, 220, 255)
            elif i >= n - 5:
                col = (255, 80, 70)
            elif i >= n - 9:
                col = (255, 200, 70)
            else:
                col = (255, 255, 255)
            pygame.draw.line(s, col, (cx + math.cos(a) * r * 0.76, cy - math.sin(a) * r * 0.76),
                             (cx + math.cos(a) * r, cy - math.sin(a) * r), 4)
        draw_text(s, str(int(self.speed * KMH)), 46, white, center=(cx, cy + 4))
        draw_text(s, "KM/H", 18, (190, 195, 225), center=(cx, cy + 28))
        # nitro
        draw_text(s, "NITRO", 18, (190, 235, 255), topleft=(12, RH - 38))
        pygame.draw.rect(s, (35, 40, 60), (12, RH - 22, 160, 12), border_radius=4)
        ncol = (255, 170, 60) if boost else (80, 210, 255)
        pygame.draw.rect(s, ncol, (12, RH - 22, int(160 * self.nitro / 100), 12), border_radius=4)
        pygame.draw.rect(s, (200, 220, 240), (12, RH - 22, 160, 12), 1, border_radius=4)
        # popups
        for i, (text, col, life) in enumerate(self.popups):
            f = clamp(life / 0.7, 0, 1)
            draw_text(s, text, 26, (int(col[0] * f), int(col[1] * f), int(col[2] * f)), topleft=(12, 78 + i * 24))
        # banner
        if self.banner:
            text, sub, col, life = self.banner
            f = clamp(life / 0.6, 0, 1)
            c = (int(col[0] * f), int(col[1] * f), int(col[2] * f))
            draw_text(s, text, 54, c, center=(RW // 2, 118))
            if sub:
                draw_text(s, sub, 26, (int(230 * f), int(230 * f), int(230 * f)), center=(RW // 2, 152))

    def render_overlay(self):
        s = self.surf
        white = (255, 255, 255)
        if self.state == "title":
            draw_text(s, "SUNSET RUSH", 84, (255, 200, 70), center=(RW // 2, 62))
            draw_text(s, "Drift. Dodge. Chain your skills!", 28, (240, 240, 255), center=(RW // 2, 108))
            s.blit(self.panel, (RW // 2 - 220, 140))
            C = CARS[self.car_idx]
            draw_text(s, "<   %s   >" % C["name"], 40, white, center=(RW // 2, 168))
            draw_car(s, RW // 2, 286, 150, C["color"], self.L, spoiler=True)
            for i, (label, val) in enumerate(zip(("SPEED", "HANDLING", "DRIFT"), C["bars"])):
                y = 308 + i * 20
                draw_text(s, label, 20, (210, 215, 240), midleft=(RW // 2 - 150, y + 6))
                for j in range(5):
                    pygame.draw.rect(s, (255, 200, 70) if j < val else (60, 62, 85),
                                     (RW // 2 - 40 + j * 30, y, 26, 12), border_radius=3)
            if int(self.t * 2) % 2 == 0:
                draw_text(s, "Press the joystick button to start", 32, white, center=(RW // 2, 392))
            draw_text(s, "Best: {:,}".format(self.high), 26, (255, 220, 90), center=(RW // 2, 424))
            draw_text(s, "Left/Right steer   Down brake   Up nitro   Hold button = drift", 20,
                      (200, 205, 230), center=(RW // 2, 452))
            draw_text(s, "Controls: %s" % self.controls.mode, 16, (150, 155, 185), center=(RW // 2, RH - 10))
        elif self.state == "countdown":
            n = int(math.ceil(self.cd))
            if n >= 1:
                draw_text(s, str(min(3, n)), 140, (255, 230, 90), center=(RW // 2, 150))
            draw_text(s, "GET READY!", 40, white, center=(RW // 2, 230))
        elif self.state == "finish":
            if self.finish_t < 2.6:
                draw_text(s, "TIME UP!", 100, (255, 90, 80), center=(RW // 2, RH // 2 - 30))
            else:
                s.blit(self.dim, (0, 0))
                draw_text(s, "RESULTS", 56, (255, 200, 70), center=(RW // 2, 60))
                rows = [("Skill score", "{:,}".format(self.total)),
                        ("Level reached", str(self.level)),
                        ("Distance", "%.1f km" % (self.dist * 6.94e-6)),
                        ("Top speed", "%d km/h" % self.top_speed),
                        ("Longest drift", "%.1f s" % self.longest_drift),
                        ("Best chain", "{:,}".format(self.best_chain)),
                        ("Near misses", str(self.near_count))]
                for i, (a, b) in enumerate(rows):
                    y = 120 + i * 36
                    draw_text(s, a, 30, (210, 215, 240), midleft=(RW // 2 - 190, y))
                    draw_text(s, b, 34, white, topright=(RW // 2 + 190, y - 12))
                if self.new_record:
                    draw_text(s, "NEW HIGH SCORE!", 44, (255, 220, 90), center=(RW // 2, 392))
                else:
                    draw_text(s, "Best: {:,}".format(self.high), 30, (255, 220, 90), center=(RW // 2, 392))
                if int(self.t * 2) % 2 == 0:
                    draw_text(s, "Press the joystick button", 32, white, center=(RW // 2, 438))

    def draw(self):
        self.render_scene()
        if self.state in ("playing", "countdown") or (self.state == "finish" and self.finish_t < 2.6):
            self.render_hud()
        self.render_overlay()
        pygame.transform.scale(self.surf, self.screen.get_size(), self.screen)


# =====================================================================
# MAIN LOOP
# =====================================================================
def main():
    pygame.init()
    flags = (pygame.FULLSCREEN | pygame.SCALED) if FULLSCREEN else 0
    screen = pygame.display.set_mode((WIDTH, HEIGHT), flags)
    pygame.display.set_caption("Sunset Rush")
    pygame.mouse.set_visible(not FULLSCREEN)
    clock = pygame.time.Clock()
    controls = Controls()
    game = Game(screen, controls)

    while True:
        dt = min(clock.tick(FPS) / 1000.0, 0.05)
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                pygame.quit()
                sys.exit()
            if event.type == pygame.JOYDEVICEADDED and controls.pad is None:
                controls.attach_pad(event.device_index)
        game.update(dt)
        game.draw()
        pygame.display.flip()


if __name__ == "__main__":
    main()