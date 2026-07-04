import os
import pygame
import sys

START_DIR = os.getcwd()
W, H = 900, 600
FPS = 30
FONT_SIZE = 18
TAB = " " * 4

BG = (30, 30, 30)
PANEL = (37, 37, 38)
FG = (212, 212, 212)
MUTED = (135, 135, 135)
SELECT = (55, 55, 61)
ERR = (207, 102, 121)

TOP, STATUS, PROMPT = 32, 24, 34
TREE_W, LINE_W, PAD = 250, 54, 8


def list_dir(path):
    try:
        return sorted(os.listdir(path),
                      key=lambda n: (not os.path.isdir(os.path.join(path, n)), n.lower()))
    except OSError:
        return []


class Editor:
    def __init__(self):
        pygame.init()
        pygame.mouse.set_visible(False)
        pygame.key.set_repeat(380, 32)
        self.screen = pygame.display.set_mode((W, H))
        pygame.display.set_caption("Pygame Editor")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("monospace", FONT_SIZE)
        self.small = pygame.font.SysFont("monospace", 15)
        self.cw, self.lh = self.font.size("M")

        self.root = os.path.abspath(START_DIR)
        self.file = None
        self.lines = [""]
        self.cx = self.cy = 0
        self.sx = self.sy = 0

        self.expanded = {self.root}
        self.selected = self.root
        self.tree_scroll = 0
        self.rows = []

        self.status = "Neue Datei    Zeile 1"
        self.error = False

        self.prompt_label = ""
        self.prompt_text = ""
        self.prompt_action = None
        self.prompt_path = None

        self.undo = []
        self.redo = []

        self.buttons = [
            ("Neu", self.new_file),
            ("Oeffnen", self.ask_open),
            ("Speichern", self.save),
            ("Ordner", self.ask_folder),
            ("Umbenennen", self.ask_rename),
            ("Loeschen", self.ask_delete),
            ("Programm beenden", self.quit)
        ]
        self.button_rects = []

    def run(self):
        while True:
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    pygame.quit()
                    return
                if e.type == pygame.KEYDOWN:
                    self.key(e)
                if e.type == pygame.MOUSEBUTTONDOWN:
                    self.mouse(e)
                if e.type == pygame.MOUSEWHEEL:
                    self.wheel(e)
            self.draw()
            pygame.display.flip()
            self.clock.tick(FPS)

    def snapshot(self):
        self.undo.append(([x[:] for x in self.lines], self.cx, self.cy))
        self.undo = self.undo[-100:]
        self.redo.clear()

    def restore(self, state):
        self.lines = [x[:] for x in state[0]]
        self.cx, self.cy = state[1], state[2]
        self.fix_cursor()
        self.update_status()

    def key(self, e):
        if self.prompt_action:
            return self.prompt_key(e)

        ctrl = e.mod & pygame.KMOD_CTRL
        if ctrl and e.key == pygame.K_n: self.new_file()
        elif ctrl and e.key == pygame.K_o: self.ask_open()
        elif ctrl and e.key == pygame.K_s: self.save()
        elif ctrl and e.key == pygame.K_z: self.do_undo()
        elif ctrl and e.key == pygame.K_y: self.do_redo()
        elif e.key == pygame.K_LEFT: self.left()
        elif e.key == pygame.K_RIGHT: self.right()
        elif e.key == pygame.K_UP: self.cy = max(0, self.cy - 1); self.fix_cursor()
        elif e.key == pygame.K_DOWN: self.cy = min(len(self.lines) - 1, self.cy + 1); self.fix_cursor()
        elif e.key == pygame.K_HOME: self.cx = 0
        elif e.key == pygame.K_END: self.cx = len(self.lines[self.cy])
        elif e.key == pygame.K_BACKSPACE: self.backspace()
        elif e.key == pygame.K_DELETE: self.delete()
        elif e.key == pygame.K_RETURN: self.enter()
        elif e.key == pygame.K_TAB: self.insert(TAB)
        elif e.unicode and e.unicode >= " " and not ctrl: self.insert(e.unicode)

        self.keep_visible()
        self.update_status()

    def prompt_key(self, e):
        if e.key == pygame.K_ESCAPE:
            self.hide_prompt()
        elif e.key == pygame.K_RETURN:
            action, text, path = self.prompt_action, self.prompt_text.strip(), self.prompt_path
            self.hide_prompt()
            if action and text:
                action(text, path)
        elif e.key == pygame.K_BACKSPACE:
            self.prompt_text = self.prompt_text[:-1]
        elif e.unicode and e.unicode >= " ":
            self.prompt_text += e.unicode

    def mouse(self, e):
        button = e.button

        # Linke und rechte Maustaste tauschen
        if button == 1:
            button = 3
        elif button == 3:
            button = 1

        x, y = e.pos

        if button == 1:
            # Linksklick-Logik
            for rect, action in self.button_rects:
                if rect.collidepoint(x, y):
                    action()
                    return
            if x < TREE_W and y >= TOP:
                self.click_tree(y)
            elif x >= TREE_W + LINE_W:
                self.click_text(x, y)

    elif button == 3:
        # Rechtsklick-Logik
        print("Rechtsklick")

    def wheel(self, e):
        x, _ = pygame.mouse.get_pos()
        if x < TREE_W:
            self.tree_scroll = max(0, self.tree_scroll - e.y)
        else:
            self.sy = max(0, self.sy - e.y * 3)

    def insert(self, text):
        self.snapshot()
        line = self.lines[self.cy]
        self.lines[self.cy] = line[:self.cx] + text + line[self.cx:]
        self.cx += len(text)

    def enter(self):
        self.snapshot()
        line = self.lines[self.cy]
        self.lines[self.cy] = line[:self.cx]
        self.lines.insert(self.cy + 1, line[self.cx:])
        self.cy += 1
        self.cx = 0

    def backspace(self):
        if self.cx == 0 and self.cy == 0:
            return
        self.snapshot()
        if self.cx:
            line = self.lines[self.cy]
            self.lines[self.cy] = line[:self.cx - 1] + line[self.cx:]
            self.cx -= 1
        else:
            old = self.lines.pop(self.cy)
            self.cy -= 1
            self.cx = len(self.lines[self.cy])
            self.lines[self.cy] += old

    def delete(self):
        line = self.lines[self.cy]
        if self.cx < len(line):
            self.snapshot()
            self.lines[self.cy] = line[:self.cx] + line[self.cx + 1:]
        elif self.cy < len(self.lines) - 1:
            self.snapshot()
            self.lines[self.cy] += self.lines.pop(self.cy + 1)

    def left(self):
        if self.cx: self.cx -= 1
        elif self.cy: self.cy -= 1; self.cx = len(self.lines[self.cy])

    def right(self):
        if self.cx < len(self.lines[self.cy]): self.cx += 1
        elif self.cy < len(self.lines) - 1: self.cy += 1; self.cx = 0

    def do_undo(self):
        if self.undo:
            self.redo.append(([x[:] for x in self.lines], self.cx, self.cy))
            self.restore(self.undo.pop())

    def do_redo(self):
        if self.redo:
            self.undo.append(([x[:] for x in self.lines], self.cx, self.cy))
            self.restore(self.redo.pop())

    def fix_cursor(self):
        self.cy = max(0, min(self.cy, len(self.lines) - 1))
        self.cx = max(0, min(self.cx, len(self.lines[self.cy])))

    def editor_rect(self):
        bottom = H - STATUS - (PROMPT if self.prompt_action else 0)
        return pygame.Rect(TREE_W + LINE_W, TOP, W - TREE_W - LINE_W, bottom - TOP)

    def keep_visible(self):
        visible = max(1, self.editor_rect().h // self.lh)
        if self.cy < self.sy: self.sy = self.cy
        if self.cy >= self.sy + visible: self.sy = self.cy - visible + 1

    def prompt(self, label, text, action, path=None):
        self.prompt_label, self.prompt_text = label, text
        self.prompt_action, self.prompt_path = action, path

    def hide_prompt(self):
        self.prompt_label = self.prompt_text = ""
        self.prompt_action = self.prompt_path = None

    def info(self, text, error=False):
        self.status, self.error = text, error

    def build_rows(self):
        rows = []

        parent = os.path.dirname(self.root)
        if parent != self.root:
            rows.append(("..", -1))

        def add(path, depth):
            rows.append((path, depth))
            if path in self.expanded and os.path.isdir(path):
                for n in list_dir(path):
                    add(os.path.join(path, n), depth + 1)

        add(self.root, 0)
        self.rows = rows

    def click_tree(self, y):
        self.build_rows()
        i = (y - TOP) // self.lh + self.tree_scroll
        if not 0 <= i < len(self.rows):
            return
    
        path, _ = self.rows[i]
    
        if path == "..":
            self.root = os.path.dirname(self.root)
            self.selected = self.root
            self.expanded = {self.root}
            return
    
        self.selected = path
    
        if os.path.isdir(path):
            if path in self.expanded:
                self.expanded.remove(path)
            else:
                self.expanded.add(path)
        else:
            self.open_file(path)

    def click_text(self, x, y):
        r = self.editor_rect()
        if not r.collidepoint(x, y):
            return
        self.cy = self.sy + (y - r.y) // self.lh
        self.cx = max(0, (x - r.x - PAD) // self.cw)
        self.fix_cursor()
        self.update_status()

    def selected_dir(self):
        return self.selected if os.path.isdir(self.selected) else os.path.dirname(self.selected)

    def ask_open(self):
        self.prompt("Oeffnen:", self.selected, lambda v, p: self.open_file(os.path.abspath(v)))

    def open_file(self, path):
        try:
            try:
                data = open(path, "r", encoding="utf-8").read()
                data = data.replace("\x00", "")
            except UnicodeDecodeError:
                data = open(path, "r", encoding="latin-1").read()
        except OSError as e:
            self.info(str(e), True)
            return
        self.file = self.selected = path
        self.lines = data.splitlines() or [""]
        self.cx = self.cy = self.sx = self.sy = 0
        self.undo.clear(); self.redo.clear()
        self.update_status()

    def new_file(self):
        self.file = None
        self.lines = [""]
        self.cx = self.cy = self.sx = self.sy = 0
        self.undo.clear(); self.redo.clear()
        self.update_status()

    def save(self):
        if self.file:
            self.write(self.file)
        else:
            self.prompt("Speichern unter:", os.path.join(self.selected_dir(), "neu.txt"),
                        lambda v, p: self.write(os.path.abspath(v), set_file=True))

    def write(self, path, set_file=False):
        try:
            open(path, "w", encoding="utf-8").write("\n".join(self.lines))
        except OSError as e:
            self.info(str(e), True)
            return
        if set_file:
            self.file = path
        self.selected = path
        self.update_status()

    def ask_folder(self):
        self.prompt("Neuer Ordner:", "neuer_ordner",
                    lambda v, p: self.make_folder(v))

    def make_folder(self, name):
        try: os.mkdir(os.path.join(self.selected_dir(), name))
        except OSError as e: self.info(str(e), True); return
        self.info("Ordner erstellt")

    def ask_rename(self):
        self.prompt("Umbenennen:", os.path.basename(self.selected), self.rename, self.selected)

    def rename(self, name, old):
        new = os.path.join(os.path.dirname(old), name)
        try: os.rename(old, new)
        except OSError as e: self.info(str(e), True); return
        if self.file == old: self.file = new
        self.selected = new
        self.update_status()

    def ask_delete(self):
        if self.selected == self.root:
            self.info("Startordner wird nicht geloescht.", True)
            return
        self.prompt("Zum Loeschen JA eingeben:", "", self.delete_path, self.selected)

    def delete_path(self, value, path):
        if value != "JA":
            self.info("Loeschen abgebrochen")
            return
        try:
            if os.path.isdir(path): os.rmdir(path)
            else: os.remove(path)
        except OSError as e:
            self.info(str(e), True); return
        if self.file == path: self.new_file()
        self.selected = self.root
        self.info("Geloescht")

    def update_status(self):
        name = os.path.basename(self.file) if self.file else "Neue Datei"
        self.status, self.error = f"{name}    Zeile {self.cy + 1}", False

    def txt(self, text, pos, color=FG, font=None):
        text = str(text).replace("\x00", "")
        self.screen.blit((font or self.font).render(text, True, color), pos)

    def draw(self):
        self.screen.fill(BG)
        self.draw_top()
        self.draw_tree()
        self.draw_editor()
        self.draw_prompt()
        self.draw_status()
        self.draw_main_cursor()

    def draw_top(self):
        pygame.draw.rect(self.screen, PANEL, (0, 0, W, TOP))
        self.button_rects = []
        x = 4
        for text, action in self.buttons:
            bw = self.small.size(text)[0] + 18
            rect = pygame.Rect(x, 3, bw, TOP - 6)
            self.button_rects.append((rect, action))
            pygame.draw.rect(self.screen, SELECT, rect)
            self.txt(text, (x + 9, 8), FG, self.small)
            x += bw + 4

    def draw_tree(self):
        bottom = H - STATUS - (PROMPT if self.prompt_action else 0)
        pygame.draw.rect(self.screen, PANEL, (0, TOP, TREE_W, bottom - TOP))
        self.build_rows()
        y = TOP
        for path, depth in self.rows[self.tree_scroll:self.tree_scroll + (bottom - TOP) // self.lh]:
            if path == self.selected:
                pygame.draw.rect(self.screen, SELECT, (0, y, TREE_W, self.lh))
            name = os.path.basename(path) or path
            pre = "- " if os.path.isdir(path) and path in self.expanded else "+ " if os.path.isdir(path) else "  "
            self.txt((pre + name)[:30], (6 + depth * 14, y + 1), FG if os.path.isdir(path) else MUTED)
            y += self.lh

    def draw_editor(self):
        r = self.editor_rect()
        pygame.draw.rect(self.screen, PANEL, (TREE_W, TOP, LINE_W, r.h))
        pygame.draw.rect(self.screen, BG, r)
        for i in range(r.h // self.lh):
            n = self.sy + i
            if n >= len(self.lines): break
            y = r.y + i * self.lh
            self.txt(str(n + 1).rjust(4), (TREE_W + 6, y + 1), MUTED)
            self.txt(self.lines[n][self.sx:], (r.x + PAD, y + 1), FG)
        x = r.x + PAD + (self.cx - self.sx) * self.cw
        y = r.y + (self.cy - self.sy) * self.lh
        pygame.draw.rect(self.screen, FG, (x, y + 2, 2, self.lh - 4))

    def draw_prompt(self):
        if not self.prompt_action:
            return
        y = H - STATUS - PROMPT
        pygame.draw.rect(self.screen, PANEL, (0, y, W, PROMPT))
        self.txt(self.prompt_label, (8, y + 8), FG, self.small)
        lx = self.small.size(self.prompt_label)[0] + 18
        pygame.draw.rect(self.screen, BG, (lx, y + 5, W - lx - 70, PROMPT - 10))
        self.txt(self.prompt_text, (lx + 6, y + 8), FG, self.small)
        self.txt("Enter", (W - 58, y + 8), MUTED, self.small)

    def draw_status(self):
        y = H - STATUS
        pygame.draw.rect(self.screen, PANEL, (0, y, W, STATUS))
        self.txt(self.status, (8, y + 4), ERR if self.error else MUTED, self.small)
    
    def draw_main_cursor(self):
        mx, my = pygame.mouse.get_pos()

        pygame.draw.line(self.screen, (255,255,255), (mx-10,my), (mx+10,my), 1)
        pygame.draw.line(self.screen, (255,255,255), (mx,my-10), (mx,my+10), 1)

    def quit(self):
        pygame.quit()
        sys.exit()

if __name__ == "__main__":
    Editor().run()
