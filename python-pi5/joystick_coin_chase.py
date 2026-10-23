#!/usr/bin/env python3
"""
COIN CHASE  -  a joystick game for Raspberry Pi
================================================
Run around the arena collecting gold coins while ghosts chase you.
Every 5 coins, another ghost joins the hunt! Grab the glowing star to
make the ghosts turn blue and run away - touch a blue ghost to send it
home for bonus points. You have 3 lives.

Scoring:  coin = 10   blue ghost = 50   star = 25

Controls
  Joystick / arrow keys / WASD ... move
  Joystick button (press down) / Space / Enter ... start / restart (moving the stick works too)
  Esc ............................ quit

Run:   python3 coin_chase.py
Needs: pygame  ->  sudo apt install python3-pygame
Put this file in the same folder as ADC0834.py (raphael-kit/python-pi5),
or keep raphael-kit in your home folder - the game will find it.
Keep your hand off the joystick while the game starts (it measures the center).
"""
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
# HELPERS
# =====================================================================
HIGH_SCORE_FILE = os.path.join(game_folder(),
                               "coin_chase_highscore.txt")
_fonts = {}


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


def draw_text(surf, text, size, color, center=None, topleft=None, topright=None):
    if size not in _fonts:
        _fonts[size] = pygame.font.Font(None, size)
    img = _fonts[size].render(text, True, color)
    rect = img.get_rect()
    if center:
        rect.center = center
    elif topleft:
        rect.topleft = topleft
    elif topright:
        rect.topright = topright
    surf.blit(img, rect)


# The play area (leaves room at the top for the score bar)
TOP = 50
ARENA = pygame.Rect(20, TOP + 10, WIDTH - 40, HEIGHT - TOP - 30)
GHOST_COLORS = [(255, 70, 70), (255, 150, 220), (80, 230, 255), (255, 170, 60), (170, 255, 90)]
FRIGHT_TIME = 6.0
MAX_GHOSTS = 6


def random_spot(margin=30, avoid=None, min_dist=0):
    for _ in range(100):
        x = random.uniform(ARENA.left + margin, ARENA.right - margin)
        y = random.uniform(ARENA.top + margin, ARENA.bottom - margin)
        if avoid is None or math.hypot(x - avoid[0], y - avoid[1]) >= min_dist:
            return x, y
    return x, y


# =====================================================================
# GAME OBJECTS
# =====================================================================
class Player:
    def __init__(self):
        self.x, self.y = ARENA.center
        self.r = 16
        self.speed = 260
        self.dir_x, self.dir_y = 1.0, 0.0
        self.invincible = 2.0       # a short safe time at the start of each life

    def update(self, dt, ax, ay):
        self.x = max(ARENA.left + self.r, min(ARENA.right - self.r, self.x + ax * self.speed * dt))
        self.y = max(ARENA.top + self.r, min(ARENA.bottom - self.r, self.y + ay * self.speed * dt))
        if ax or ay:
            self.dir_x, self.dir_y = ax, ay
        self.invincible = max(0.0, self.invincible - dt)

    def draw(self, surf, t):
        if self.invincible > 0 and int(t * 12) % 2 == 0:
            return
        # A chomping yellow circle that faces the way you're moving
        mouth = abs(math.sin(t * 12)) * 0.6 + 0.05
        facing = math.atan2(self.dir_y, self.dir_x)
        pts = [(self.x, self.y)]
        steps = 24
        for i in range(steps + 1):
            a = facing + mouth + (2 * math.pi - 2 * mouth) * i / steps
            pts.append((self.x + math.cos(a) * self.r, self.y + math.sin(a) * self.r))
        pygame.draw.polygon(surf, (255, 225, 50), pts)
        ex = self.x + math.cos(facing - 1.2) * self.r * 0.5
        ey = self.y + math.sin(facing - 1.2) * self.r * 0.5
        pygame.draw.circle(surf, (30, 30, 30), (int(ex), int(ey)), 3)


class Ghost:
    def __init__(self, index, player):
        self.color = GHOST_COLORS[index % len(GHOST_COLORS)]
        self.r = 17
        self.spawn(player)
        self.base_speed = 95 + index * 12
        self.wobble = random.uniform(0, 6.28)
        self.eaten_timer = 0.0

    def spawn(self, player):
        # Always appear in a corner far away from the player
        corners = [(ARENA.left + 30, ARENA.top + 30), (ARENA.right - 30, ARENA.top + 30),
                   (ARENA.left + 30, ARENA.bottom - 30), (ARENA.right - 30, ARENA.bottom - 30)]
        corners.sort(key=lambda c: -math.hypot(c[0] - player.x, c[1] - player.y))
        self.x, self.y = random.choice(corners[:2])

    def update(self, dt, player, frightened, level):
        if self.eaten_timer > 0:            # eaten ghosts wait a moment, then come back
            self.eaten_timer -= dt
            if self.eaten_timer <= 0:
                self.spawn(player)
            return
        self.wobble += dt * 3
        dx, dy = player.x - self.x, player.y - self.y
        dist = math.hypot(dx, dy) or 1
        dx, dy = dx / dist, dy / dist
        # Add a little zig-zag so ghosts don't move in a perfectly straight line
        dx += math.cos(self.wobble) * 0.35
        dy += math.sin(self.wobble) * 0.35
        if frightened:
            dx, dy = -dx, -dy
            speed = 70
        else:
            speed = self.base_speed + level * 6
        n = math.hypot(dx, dy) or 1
        self.x += dx / n * speed * dt
        self.y += dy / n * speed * dt
        self.x = max(ARENA.left + self.r, min(ARENA.right - self.r, self.x))
        self.y = max(ARENA.top + self.r, min(ARENA.bottom - self.r, self.y))

    def active(self):
        return self.eaten_timer <= 0

    def draw(self, surf, t, frightened, fright_left):
        if not self.active():
            return
        x, y, r = self.x, self.y, self.r
        if frightened:
            flashing = fright_left < 2 and int(t * 8) % 2 == 0
            color = (240, 240, 255) if flashing else (50, 70, 230)
        else:
            color = self.color
        pygame.draw.circle(surf, color, (int(x), int(y - 3)), r)
        pygame.draw.rect(surf, color, (x - r, y - 3, 2 * r, r))
        # wavy skirt at the bottom
        for i in range(4):
            bx = x - r + r / 4 + i * r / 2
            off = 3 if (int(t * 8) + i) % 2 else 0
            pygame.draw.circle(surf, color, (int(bx), int(y + r - 4 + off)), int(r / 4) + 1)
        if frightened:
            pygame.draw.circle(surf, (255, 255, 255), (int(x - 6), int(y - 5)), 3)
            pygame.draw.circle(surf, (255, 255, 255), (int(x + 6), int(y - 5)), 3)
            pygame.draw.lines(surf, (255, 255, 255), False,
                              [(x - 9, y + 6), (x - 5, y + 3), (x - 1, y + 6), (x + 3, y + 3), (x + 7, y + 6)], 2)
        else:
            for ex in (-6, 6):
                pygame.draw.circle(surf, (255, 255, 255), (int(x + ex), int(y - 5)), 5)
                pygame.draw.circle(surf, (20, 40, 160), (int(x + ex + 1), int(y - 4)), 2)


class Coin:
    def __init__(self, avoid):
        self.x, self.y = random_spot(30, avoid, 120)
        self.r = 11
        self.phase = random.uniform(0, 6.28)

    def draw(self, surf, t):
        w = max(2, int(abs(math.cos(t * 3 + self.phase)) * self.r))   # spinning coin
        rect = pygame.Rect(0, 0, w * 2, self.r * 2)
        rect.center = (int(self.x), int(self.y))
        pygame.draw.ellipse(surf, (255, 200, 30), rect)
        pygame.draw.ellipse(surf, (200, 140, 0), rect, 2)


class Star:
    def __init__(self, avoid):
        self.x, self.y = random_spot(40, avoid, 150)
        self.r = 15
        self.life = 8.0             # disappears if you don't grab it in time

    def draw(self, surf, t):
        if self.life < 2 and int(t * 8) % 2 == 0:
            return
        spin = t * 2
        pts = []
        for i in range(10):
            rad = self.r + 4 if i % 2 == 0 else (self.r + 4) * 0.45
            a = spin + i * math.pi / 5
            pts.append((self.x + math.cos(a) * rad, self.y + math.sin(a) * rad))
        pygame.draw.circle(surf, (90, 70, 20), (int(self.x), int(self.y)), self.r + 8)
        pygame.draw.polygon(surf, (255, 255, 120), pts)


# =====================================================================
# THE GAME
# =====================================================================
class Game:
    def __init__(self, screen, controls):
        self.screen = screen
        self.controls = controls
        self.high = load_high_score()
        self.state = "title"
        self.t = 0.0
        self.reset()

    def reset(self):
        self.player = Player()
        self.score = 0
        self.coins_collected = 0
        self.lives = 3
        self.ghosts = [Ghost(0, self.player)]
        self.coins = [Coin((self.player.x, self.player.y)) for _ in range(5)]
        self.star = None
        self.star_timer = random.uniform(10, 15)
        self.fright = 0.0
        self.chain = 0
        self.popups = []            # floating "+10" texts
        self.particles = []
        self.message = ""
        self.message_timer = 0.0
        self.state_timer = 0.0
        self.new_record = False

    def popup(self, x, y, text, color):
        self.popups.append([x, y, text, color, 1.0])

    def burst(self, x, y, color, count=14, speed=180):
        for _ in range(count):
            a = random.uniform(0, 2 * math.pi)
            s = random.uniform(40, speed)
            self.particles.append([x, y, math.cos(a) * s, math.sin(a) * s, random.uniform(0.3, 0.7), color])

    def announce(self, text):
        self.message, self.message_timer = text, 2.0

    # ---------- update ----------
    def update(self, dt):
        self.t += dt
        ax, ay = self.controls.axes()
        pressed = self.controls.button_pressed()
        moved = ax != 0 or ay != 0

        for p in self.particles:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[4] -= dt
        self.particles = [p for p in self.particles if p[4] > 0]
        for p in self.popups:
            p[1] -= 40 * dt
            p[4] -= dt
        self.popups = [p for p in self.popups if p[4] > 0]
        self.message_timer = max(0.0, self.message_timer - dt)

        if self.state == "title":
            if pressed or moved:
                self.reset()
                self.state = "playing"
        elif self.state == "playing":
            self.update_play(dt, ax, ay)
        elif self.state == "gameover":
            self.state_timer += dt
            if self.state_timer > 1.5 and (pressed or moved):
                self.reset()
                self.state = "playing"

    def update_play(self, dt, ax, ay):
        p = self.player
        p.update(dt, ax, ay)
        level = self.coins_collected // 5
        frightened = self.fright > 0
        self.fright = max(0.0, self.fright - dt)

        for g in self.ghosts:
            g.update(dt, p, frightened, level)

        # Coins
        for c in list(self.coins):
            if math.hypot(c.x - p.x, c.y - p.y) < c.r + p.r:
                self.coins.remove(c)
                self.score += 10
                self.coins_collected += 1
                self.popup(c.x, c.y, "+10", (255, 220, 80))
                self.burst(c.x, c.y, (255, 210, 60))
                self.coins.append(Coin((p.x, p.y)))
                if self.coins_collected % 5 == 0 and len(self.ghosts) < MAX_GHOSTS:
                    self.ghosts.append(Ghost(len(self.ghosts), p))
                    self.announce("A new ghost joins the chase!")

        # Power star
        if self.star is None:
            self.star_timer -= dt
            if self.star_timer <= 0:
                self.star = Star((p.x, p.y))
        else:
            self.star.life -= dt
            if math.hypot(self.star.x - p.x, self.star.y - p.y) < self.star.r + p.r:
                self.fright = FRIGHT_TIME
                self.chain = 0
                self.score += 25
                self.popup(self.star.x, self.star.y, "POWER!", (255, 255, 120))
                self.burst(self.star.x, self.star.y, (255, 255, 120), 30, 260)
                self.star = None
                self.star_timer = random.uniform(12, 18)
            elif self.star.life <= 0:
                self.star = None
                self.star_timer = random.uniform(8, 14)

        # Ghost collisions
        for g in self.ghosts:
            if not g.active():
                continue
            if math.hypot(g.x - p.x, g.y - p.y) < g.r + p.r - 6:
                if self.fright > 0:
                    self.chain += 1
                    pts = 50 * self.chain          # 50, 100, 150... for eating several in a row
                    self.score += pts
                    self.popup(g.x, g.y, f"+{pts}", (120, 200, 255))
                    self.burst(g.x, g.y, (80, 120, 255), 24, 220)
                    g.eaten_timer = 3.0
                elif p.invincible <= 0:
                    self.lose_life()
                    break

    def lose_life(self):
        p = self.player
        self.burst(p.x, p.y, (255, 225, 50), 40, 280)
        self.lives -= 1
        if self.lives <= 0:
            self.state = "gameover"
            self.state_timer = 0.0
            if self.score > self.high:
                self.high = self.score
                self.new_record = True
                save_high_score(self.score)
            return
        # Respawn in the middle and push the ghosts back to the corners
        self.player = Player()
        for g in self.ghosts:
            g.spawn(self.player)
        self.fright = 0.0
        self.announce(f"Ouch! {self.lives} lives left")

    # ---------- draw ----------
    def draw(self):
        surf = self.screen
        surf.fill((10, 10, 30))
        # floor tiles
        for gx in range(ARENA.left, ARENA.right, 40):
            for gy in range(ARENA.top, ARENA.bottom, 40):
                if (gx // 40 + gy // 40) % 2 == 0:
                    pygame.draw.rect(surf, (16, 16, 44), (gx, gy, 40, 40))
        pygame.draw.rect(surf, (60, 80, 255), ARENA.inflate(8, 8), 4, border_radius=8)

        if self.state != "title":
            for c in self.coins:
                c.draw(surf, self.t)
            if self.star:
                self.star.draw(surf, self.t)
            for g in self.ghosts:
                g.draw(surf, self.t, self.fright > 0, self.fright)
            if self.state == "playing":
                self.player.draw(surf, self.t)

        for x, y, _, _, life, color in self.particles:
            pygame.draw.circle(surf, color, (int(x), int(y)), max(1, int(life * 6)))
        for x, y, text, color, life in self.popups:
            draw_text(surf, text, 30, color, center=(x, y))

        # Score bar
        draw_text(surf, f"Score: {self.score}", 36, (255, 255, 255), topleft=(20, 14))
        draw_text(surf, f"Best: {self.high}", 36, (255, 220, 80), topright=(WIDTH - 20, 14))
        for i in range(self.lives if self.state == "playing" else 0):
            cx, cy = WIDTH / 2 - 30 + i * 30, 28
            pygame.draw.polygon(surf, (255, 225, 50),
                                [(cx, cy)] + [(cx + math.cos(a / 10) * 10, cy + math.sin(a / 10) * 10)
                                              for a in range(5, 59)])
        if self.state == "playing" and self.fright > 0:
            bar = int(160 * self.fright / FRIGHT_TIME)
            pygame.draw.rect(surf, (80, 120, 255), (WIDTH / 2 - 80, 44, bar, 5))

        if self.message_timer > 0 and self.state == "playing":
            draw_text(surf, self.message, 40, (255, 255, 255), center=(WIDTH / 2, HEIGHT / 2 - 150))

        if self.state == "title":
            draw_text(surf, "COIN CHASE", 96, (255, 220, 80), center=(WIDTH / 2, HEIGHT / 2 - 100))
            draw_text(surf, "Grab the coins. Run from the ghosts!", 34, (200, 200, 255),
                      center=(WIDTH / 2, HEIGHT / 2 - 30))
            draw_text(surf, "Get the star and the ghosts run from YOU!", 34, (255, 255, 140),
                      center=(WIDTH / 2, HEIGHT / 2 + 10))
            if int(self.t * 2) % 2 == 0:
                draw_text(surf, "Move the joystick to start", 40, (255, 255, 255),
                          center=(WIDTH / 2, HEIGHT / 2 + 80))
            draw_text(surf, f"Controls: {self.controls.mode}", 22, (120, 120, 160),
                      center=(WIDTH / 2, HEIGHT - 12))

        if self.state == "gameover":
            draw_text(surf, "GAME OVER", 100, (255, 90, 90), center=(WIDTH / 2, HEIGHT / 2 - 70))
            draw_text(surf, f"Score: {self.score}   Coins: {self.coins_collected}", 44, (255, 255, 255),
                      center=(WIDTH / 2, HEIGHT / 2 + 5))
            if self.new_record:
                draw_text(surf, "NEW RECORD!", 48, (255, 220, 80), center=(WIDTH / 2, HEIGHT / 2 + 60))
            if self.state_timer > 1.5 and int(self.t * 2) % 2 == 0:
                draw_text(surf, "Move the joystick to play again", 34, (200, 200, 255),
                          center=(WIDTH / 2, HEIGHT / 2 + 120))


# =====================================================================
# MAIN LOOP
# =====================================================================
def main():
    pygame.init()
    flags = (pygame.FULLSCREEN | pygame.SCALED) if FULLSCREEN else 0
    screen = pygame.display.set_mode((WIDTH, HEIGHT), flags)
    pygame.display.set_caption("Coin Chase")
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