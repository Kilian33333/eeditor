import os
import tkinter as tk
from tkinter import ttk

START_DIR = os.getcwd()
WINDOW_WIDTH = 900
WINDOW_HEIGHT = 600
FONT = ("Courier New", 12)
TAB = " " * 4

BG = "#1e1e1e"
PANEL = "#252526"
FG = "#d4d4d4"
MUTED = "#858585"
SELECT = "#37373d"
ERROR = "#cf6679"


class Editor:
    def __init__(self, root):
        self.root = root
        self.root.title("Mini Editor")
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root_dir = os.path.abspath(START_DIR)
        self.current_file = None
        self.prompt_action = None
        self.prompt_path = None

        self.style()
        self.ui()
        self.keys()
        self.load_tree()
        self.update_status()

    def style(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure("Treeview", background=PANEL, foreground=FG,
                    fieldbackground=PANEL, borderwidth=0)
        s.map("Treeview", background=[("selected", SELECT)])

    def ui(self):
        self.root.configure(bg=BG)

        top = tk.Frame(self.root, bg=PANEL)
        top.pack(fill="x")

        for name, cmd in (
            ("Neu", self.new_file),
            ("Öffnen", self.ask_open),
            ("Speichern", self.save_file),
            ("Ordner", self.ask_folder),
            ("Umbenennen", self.ask_rename),
            ("Löschen", self.ask_delete),
        ):
            tk.Button(top, text=name, command=cmd, bg=PANEL, fg=FG,
                      activebackground=SELECT, activeforeground=FG,
                      relief="flat", padx=8, pady=4).pack(side="left")

        main = tk.PanedWindow(self.root, orient="horizontal", bg=BG, sashwidth=4, bd=0)
        main.pack(fill="both", expand=True)

        self.tree = ttk.Treeview(main, show="tree")
        self.tree.bind("<<TreeviewOpen>>", self.open_folder)
        self.tree.bind("<Double-1>", self.double_click)
        main.add(self.tree, width=240)

        editor = tk.Frame(main, bg=BG)
        main.add(editor)

        self.lines = tk.Text(editor, width=4, padx=6, takefocus=0,
                             bg=PANEL, fg=MUTED, font=FONT,
                             relief="flat", state="disabled")
        self.lines.pack(side="left", fill="y")

        self.text = tk.Text(editor, undo=True, wrap="none", bg=BG, fg=FG,
                            insertbackground=FG, selectbackground=SELECT,
                            font=FONT, relief="flat")
        self.text.pack(side="left", fill="both", expand=True)

        scroll = tk.Scrollbar(editor, command=self.scroll_y)
        scroll.pack(side="right", fill="y")
        self.text.configure(yscrollcommand=lambda a, b: self.scrolled(a, b, scroll))

        self.prompt = tk.Frame(self.root, bg=PANEL)
        self.prompt_label = tk.Label(self.prompt, bg=PANEL, fg=FG, padx=8)
        self.prompt_entry = tk.Entry(self.prompt, bg=BG, fg=FG,
                                     insertbackground=FG, relief="flat")
        self.prompt_ok = tk.Button(self.prompt, text="OK", command=self.prompt_done,
                                   bg=PANEL, fg=FG, relief="flat")
        self.prompt_cancel = tk.Button(self.prompt, text="Abbrechen",
                                       command=self.prompt_hide,
                                       bg=PANEL, fg=FG, relief="flat")

        self.prompt_label.pack(side="left")
        self.prompt_entry.pack(side="left", fill="x", expand=True, padx=4, pady=4)
        self.prompt_ok.pack(side="left", padx=2)
        self.prompt_cancel.pack(side="left", padx=2)
        self.prompt_entry.bind("<Return>", lambda e: self.prompt_done())
        self.prompt_entry.bind("<Escape>", lambda e: self.prompt_hide())

        self.status = tk.Label(self.root, bg=PANEL, fg=MUTED, anchor="w", padx=8)
        self.status.pack(fill="x", side="bottom")

        self.text.bind("<KeyRelease>", lambda e: self.update_status())
        self.text.bind("<ButtonRelease>", lambda e: self.update_status())
        self.text.bind("<Configure>", lambda e: self.update_lines())
        self.text.bind("<Tab>", self.tab)

    def keys(self):
        self.root.bind("<Control-n>", lambda e: self.new_file())
        self.root.bind("<Control-o>", lambda e: self.ask_open())
        self.root.bind("<Control-s>", lambda e: self.save_file())
        self.root.bind("<Control-z>", lambda e: self.undo())
        self.root.bind("<Control-y>", lambda e: self.redo())

    def prompt_show(self, label, value, action, path=None):
        self.prompt_action = action
        self.prompt_path = path
        self.prompt_label.config(text=label)
        self.prompt_entry.delete(0, "end")
        self.prompt_entry.insert(0, value)
        if not self.prompt.winfo_ismapped():
            self.prompt.pack(fill="x", side="bottom", before=self.status)
        self.prompt_entry.focus_set()
        self.prompt_entry.selection_range(0, "end")

    def prompt_hide(self):
        self.prompt.pack_forget()
        self.prompt_action = None
        self.prompt_path = None
        self.text.focus_set()

    def prompt_done(self):
        value = self.prompt_entry.get().strip()
        action = self.prompt_action
        path = self.prompt_path
        self.prompt_hide()
        if action and value:
            action(value, path)

    def info(self, text, error=False):
        self.status.config(text=text, fg=ERROR if error else MUTED)

    def selected_path(self):
        item = self.tree.focus()
        return self.tree.item(item, "values")[0] if item else self.root_dir

    def selected_dir(self):
        path = self.selected_path()
        return path if os.path.isdir(path) else os.path.dirname(path)

    def scrolled(self, a, b, scroll):
        scroll.set(a, b)
        self.lines.yview_moveto(a)

    def scroll_y(self, *args):
        self.text.yview(*args)
        self.lines.yview(*args)

    def load_tree(self):
        self.tree.delete(*self.tree.get_children())
        root = self.tree.insert("", "end", text=self.root_dir,
                                values=[self.root_dir], open=True)
        self.add_children(root, self.root_dir)

    def add_children(self, parent, path):
        try:
            names = sorted(os.listdir(path),
                           key=lambda n: (not os.path.isdir(os.path.join(path, n)), n.lower()))
        except OSError:
            return

        for name in names:
            full = os.path.join(path, name)
            item = self.tree.insert(parent, "end", text=name, values=[full])
            if os.path.isdir(full):
                self.tree.insert(item, "end", text="...", values=[""])

    def open_folder(self, event=None):
        item = self.tree.focus()
        path = self.selected_path()
        if os.path.isdir(path):
            self.tree.delete(*self.tree.get_children(item))
            self.add_children(item, path)

    def double_click(self, event=None):
        path = self.selected_path()
        if os.path.isfile(path):
            self.open_file(path)

    def ask_open(self):
        self.prompt_show("Öffnen:", self.selected_path(), self.open_from_prompt)

    def open_from_prompt(self, value, path=None):
        self.open_file(os.path.abspath(value))

    def open_file(self, path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = f.read()
        except UnicodeDecodeError:
            try:
                with open(path, "r", encoding="latin-1") as f:
                    data = f.read()
            except OSError as e:
                self.info(str(e), True)
                return
        except OSError as e:
            self.info(str(e), True)
            return

        self.current_file = path
        self.text.delete("1.0", "end")
        self.text.insert("1.0", data)
        self.text.edit_reset()
        self.update_status()

    def new_file(self):
        self.current_file = None
        self.text.delete("1.0", "end")
        self.text.edit_reset()
        self.update_status()

    def save_file(self):
        if self.current_file:
            self.write_file(self.current_file)
        else:
            path = os.path.join(self.selected_dir(), "neu.txt")
            self.prompt_show("Speichern unter:", path, self.save_from_prompt)

    def save_from_prompt(self, value, path=None):
        self.current_file = os.path.abspath(value)
        self.write_file(self.current_file)

    def write_file(self, path):
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.text.get("1.0", "end-1c"))
        except OSError as e:
            self.info(str(e), True)
            return

        self.load_tree()
        self.update_status()

    def ask_folder(self):
        self.prompt_show("Neuer Ordner:", "neuer_ordner", self.new_folder)

    def new_folder(self, value, path=None):
        try:
            os.mkdir(os.path.join(self.selected_dir(), value))
            self.load_tree()
            self.info("Ordner erstellt")
        except OSError as e:
            self.info(str(e), True)

    def ask_rename(self):
        path = self.selected_path()
        self.prompt_show("Umbenennen:", os.path.basename(path), self.rename_item, path)

    def rename_item(self, value, old):
        new = os.path.join(os.path.dirname(old), value)
        try:
            os.rename(old, new)
            if self.current_file == old:
                self.current_file = new
            self.load_tree()
            self.update_status()
        except OSError as e:
            self.info(str(e), True)

    def ask_delete(self):
        path = self.selected_path()
        if path == self.root_dir:
            self.info("Startordner wird nicht gelöscht.", True)
            return
        self.prompt_show("Zum Löschen JA eingeben:", "", self.delete_item, path)

    def delete_item(self, value, path):
        if value != "JA":
            self.info("Löschen abgebrochen")
            return

        try:
            if os.path.isdir(path):
                os.rmdir(path)
            else:
                os.remove(path)
        except OSError as e:
            self.info(str(e), True)
            return

        if self.current_file == path:
            self.new_file()
        self.load_tree()
        self.info("Gelöscht")

    def tab(self, event=None):
        self.text.insert("insert", TAB)
        return "break"

    def undo(self):
        try:
            self.text.edit_undo()
        except tk.TclError:
            pass
        self.update_status()

    def redo(self):
        try:
            self.text.edit_redo()
        except tk.TclError:
            pass
        self.update_status()

    def update_lines(self):
        count = int(self.text.index("end-1c").split(".")[0])
        nums = "\n".join(str(i) for i in range(1, count + 1))
        self.lines.config(state="normal")
        self.lines.delete("1.0", "end")
        self.lines.insert("1.0", nums)
        self.lines.config(state="disabled")

    def update_status(self):
        self.update_lines()
        name = os.path.basename(self.current_file) if self.current_file else "Neue Datei"
        line = self.text.index("insert").split(".")[0]
        self.status.config(text=f"{name}    Zeile {line}", fg=MUTED)


if __name__ == "__main__":
    root = tk.Tk()
    Editor(root)
    root.mainloop()