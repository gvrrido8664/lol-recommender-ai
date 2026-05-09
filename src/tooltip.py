import tkinter as tk

class Tooltip:
    """
    Componente reutilizable para mostrar un tooltip.

    El tooltip aparece cuando el usuario pasa el mouse sobre el icono asociado
    y desaparece cuando el mouse sale del área del icono. Pensado para
    mostrar información del objeto sin ocupar espacio permanente en la interfaz
    y posteriormente poder agregar runas.
    """
    def __init__(self, widget, text="", delay=300):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.tooltip_window = None
        self.after_id = None

        self.widget.bind("<Enter>", self.schedule)
        self.widget.bind("<Leave>", self.hide)
        self.widget.bind("<Motion>", self.move)

    def schedule(self, event=None):
        self.cancel()
        self.after_id = self.widget.after(self.delay, self.show)

    def cancel(self):
        if self.after_id:
            self.widget.after_cancel(self.after_id)
            self.after_id = None

    def show(self):
        if self.tooltip_window or not self.text:
            return

        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 10

        self.tooltip_window = tk.Toplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_geometry(f"+{x}+{y}")

        frame = tk.Frame(
            self.tooltip_window,
            background="#1f2937",
            borderwidth=1,
            relief="solid"
        )
        frame.pack()

        label = tk.Label(
            frame,
            text=self.text,
            justify="left",
            background="#1f2937",
            foreground="#ffffff",
            font=("Segoe UI", 9),
            wraplength=300,
            padx=10,
            pady=8
        )
        label.pack()

    def move(self, event=None):
        if self.tooltip_window and event:
            x = self.widget.winfo_rootx() + event.x + 20
            y = self.widget.winfo_rooty() + event.y + 20
            self.tooltip_window.wm_geometry(f"+{x}+{y}")

    def hide(self, event=None):
        self.cancel()
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None