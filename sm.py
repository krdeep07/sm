"""
Mitsubishi PLC Live Dashboard (Ethernet / MC Protocol) - Read + Write D0-D30
=============================================================================

Live-reads D0 ... D30 every poll cycle and shows them in a table.
D10 additionally gets a mapped status TEXT.
You can write to ANY register D0-D30, one at a time or all at once.

INSTALL:
    pip install pymcprotocol matplotlib

RUN:
    python plc_dashboard_v2.py

NOTES:
- Uses pymcprotocol's Type3E class (MC protocol / "3E frame"), the most
  common Ethernet protocol for Mitsubishi Q/L/iQ-R/iQ-L PLCs, and FX
  series with an Ethernet module such as FX3U-ENET.
- Default port 5007 assumes you set that port number in the PLC's
  Ethernet module / built-in Ethernet parameters (GX Works). Change it
  in the app if yours is different.
- Edit D10_TEXT_MAP below to match what each value of D10 means in
  your process.
- Live reading and writing share the SAME background thread/socket so
  reads and writes never collide on the wire.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import queue
import time
from collections import deque

import pymcprotocol

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# ---------------------- CONFIG ----------------------
DEFAULT_IP = "192.168.3.39"
DEFAULT_PORT = 5007
DEFAULT_PLC_TYPE = "Q"   # "Q", "L", "QnA", "iQ-L", "iQ-R", "FX"
POLL_INTERVAL_SEC = 0.5
REG_RANGE = list(range(0, 31))  # D0 ... D30 inclusive
HEAD_DEVICE = "D0"
READ_SIZE = len(REG_RANGE)      # 31 registers read in a single batch call

# Special relays to monitor live (bit devices, read-only).
# SM411 = 0.2s clock pulse, SM412 = 1s clock pulse (standard on Q/L/iQ series).
SM_DEVICES = ["SM411", "SM412"]

# Map D10 raw value -> status text. EDIT THIS to match your process.
D10_TEXT_MAP = {
    0: "STOPPED",
    1: "RUNNING",
    2: "ALARM",
    3: "PAUSED",
}


def d10_to_text(value):
    if value in D10_TEXT_MAP:
        return D10_TEXT_MAP[value]
    return f"UNKNOWN ({value})"


class PLCWorker(threading.Thread):
    """Background thread: owns the PLC socket, handles reads + writes
    on the same connection so the GUI thread is never blocked."""

    def __init__(self, ip, port, plc_type, read_queue, cmd_queue, status_queue):
        super().__init__(daemon=True)
        self.ip = ip
        self.port = port
        self.plc_type = plc_type
        self.read_queue = read_queue
        self.cmd_queue = cmd_queue
        self.status_queue = status_queue
        self._stop_flag = threading.Event()
        self.pymc = pymcprotocol.Type3E(plctype=plc_type)

    def stop(self):
        self._stop_flag.set()

    def run(self):
        try:
            self.pymc.connect(self.ip, self.port)
            self.status_queue.put(("status", "Connected"))
        except Exception as e:
            self.status_queue.put(("error", f"Connection failed: {e}"))
            return

        while not self._stop_flag.is_set():
            # 1) flush any pending write commands first
            try:
                while True:
                    cmd = self.cmd_queue.get_nowait()
                    self._handle_write(cmd)
            except queue.Empty:
                pass

            # 2) read D0-D30 in a single batch call
            try:
                values = self.pymc.batchread_wordunits(headdevice=HEAD_DEVICE, readsize=READ_SIZE)
                self.read_queue.put(("batch", values))
            except Exception as e:
                self.status_queue.put(("error", f"Read failed: {e}"))

            # 3) read special relays SM411 / SM412 (bit devices)
            try:
                sm_values = {}
                for sm in SM_DEVICES:
                    bits = self.pymc.batchread_bitunits(headdevice=sm, readsize=1)
                    sm_values[sm] = bits[0]
                self.read_queue.put(("sm", sm_values))
            except Exception as e:
                self.status_queue.put(("error", f"SM read failed: {e}"))

            time.sleep(POLL_INTERVAL_SEC)

        try:
            self.pymc.close()
        except Exception:
            pass
        self.status_queue.put(("status", "Disconnected"))

    def _handle_write(self, cmd):
        kind, addr, value = cmd
        try:
            if kind == "single":
                self.pymc.batchwrite_wordunits(headdevice=addr, values=[value])
                self.status_queue.put(("status", f"Wrote {value} -> {addr}"))
            elif kind == "block":
                self.pymc.batchwrite_wordunits(headdevice=addr, values=value)
                self.status_queue.put(("status", f"Wrote block -> {addr} ({len(value)} regs)"))
        except Exception as e:
            self.status_queue.put(("error", f"Write failed: {e}"))


class Dashboard(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Mitsubishi PLC Live Dashboard - Read/Write D0-D30")
        self.geometry("980x760")

        self.read_queue = queue.Queue()
        self.cmd_queue = queue.Queue()
        self.status_queue = queue.Queue()
        self.worker = None

        self.d10_history = deque(maxlen=120)

        # live value display vars, one per register
        self.live_vars = {f"D{r}": tk.StringVar(value="--") for r in REG_RANGE}
        # write entry vars, one per register
        self.write_vars = {f"D{r}": tk.StringVar(value="0") for r in REG_RANGE}

        # live vars for special relays
        self.sm_vars = {sm: tk.StringVar(value="--") for sm in SM_DEVICES}

        self._build_connection_bar()
        self._build_status_panel()
        self._build_sm_panel()
        self._build_chart()
        self._build_register_table()
        self._build_log()

        self.after(200, self._poll_queues)

    # ---------------- UI sections ----------------
    def _build_connection_bar(self):
        frame = ttk.LabelFrame(self, text="PLC Connection")
        frame.pack(fill="x", padx=8, pady=6)

        ttk.Label(frame, text="IP:").grid(row=0, column=0, padx=4, pady=4)
        self.ip_var = tk.StringVar(value=DEFAULT_IP)
        ttk.Entry(frame, textvariable=self.ip_var, width=15).grid(row=0, column=1)

        ttk.Label(frame, text="Port:").grid(row=0, column=2, padx=4)
        self.port_var = tk.StringVar(value=str(DEFAULT_PORT))
        ttk.Entry(frame, textvariable=self.port_var, width=8).grid(row=0, column=3)

        ttk.Label(frame, text="PLC Type:").grid(row=0, column=4, padx=4)
        self.type_var = tk.StringVar(value=DEFAULT_PLC_TYPE)
        ttk.Combobox(frame, textvariable=self.type_var, width=8,
                     values=["Q", "L", "QnA", "iQ-L", "iQ-R", "FX"]).grid(row=0, column=5)

        self.connect_btn = ttk.Button(frame, text="Connect", command=self.connect_plc)
        self.connect_btn.grid(row=0, column=6, padx=8)

        self.disconnect_btn = ttk.Button(frame, text="Disconnect", command=self.disconnect_plc, state="disabled")
        self.disconnect_btn.grid(row=0, column=7, padx=4)

        self.conn_status_var = tk.StringVar(value="Disconnected")
        ttk.Label(frame, textvariable=self.conn_status_var, foreground="red").grid(row=0, column=8, padx=8)

    def _build_status_panel(self):
        frame = ttk.LabelFrame(self, text="D10 Status")
        frame.pack(fill="x", padx=8, pady=6)

        self.d10_raw_var = tk.StringVar(value="--")
        self.d10_text_var = tk.StringVar(value="--")

        ttk.Label(frame, text="Raw Value:", font=("Segoe UI", 11)).grid(row=0, column=0, padx=6, pady=6)
        ttk.Label(frame, textvariable=self.d10_raw_var, font=("Segoe UI", 14, "bold")).grid(row=0, column=1, padx=6)

        ttk.Label(frame, text="Status:", font=("Segoe UI", 11)).grid(row=0, column=2, padx=20)
        ttk.Label(frame, textvariable=self.d10_text_var, font=("Segoe UI", 14, "bold")).grid(row=0, column=3, padx=6)

    def _build_sm_panel(self):
        frame = ttk.LabelFrame(self, text="Special Relays (Live)")
        frame.pack(fill="x", padx=8, pady=6)

        self.sm_labels = {}
        for i, sm in enumerate(SM_DEVICES):
            ttk.Label(frame, text=f"{sm}:", font=("Segoe UI", 11)).grid(row=0, column=i * 2, padx=6, pady=6)
            lbl = ttk.Label(frame, textvariable=self.sm_vars[sm], font=("Segoe UI", 14, "bold"), foreground="gray")
            lbl.grid(row=0, column=i * 2 + 1, padx=6)
            self.sm_labels[sm] = lbl

    def _build_chart(self):
        frame = ttk.LabelFrame(self, text="D10 Trend")
        frame.pack(fill="both", expand=True, padx=8, pady=6)

        self.fig = Figure(figsize=(8, 2.2), dpi=90)
        self.ax = self.fig.add_subplot(111)
        self.line, = self.ax.plot([], [])
        self.ax.set_ylabel("D10")
        self.ax.set_xlabel("samples")

        self.canvas = FigureCanvasTkAgg(self.fig, master=frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    def _build_register_table(self):
        outer = ttk.LabelFrame(self, text="Registers D0 - D30  (Live Value | Write Value | Write)")
        outer.pack(fill="both", expand=True, padx=8, pady=6)

        canvas = tk.Canvas(outer)
        scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)

        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # header row
        headers = ["Register", "Live Value", "Write Value", ""]
        for col, h in enumerate(headers):
            ttk.Label(scroll_frame, text=h, font=("Segoe UI", 9, "bold")).grid(row=0, column=col, padx=6, pady=4)

        for i, reg in enumerate(REG_RANGE):
            addr = f"D{reg}"
            r = i + 1
            ttk.Label(scroll_frame, text=addr, width=6).grid(row=r, column=0, padx=4, pady=2)
            ttk.Label(scroll_frame, textvariable=self.live_vars[addr], width=10,
                      relief="sunken", anchor="center").grid(row=r, column=1, padx=4)
            ttk.Entry(scroll_frame, textvariable=self.write_vars[addr], width=10).grid(row=r, column=2, padx=4)
            ttk.Button(scroll_frame, text="Write",
                       command=lambda a=addr: self.write_single(a)).grid(row=r, column=3, padx=4, pady=2)

        btn_frame = ttk.Frame(outer)
        btn_frame.pack(fill="x", pady=4)
        ttk.Button(btn_frame, text="Write ALL (D0-D30)", command=self.write_all).pack(side="left", padx=6)
        ttk.Button(btn_frame, text="Copy Live -> Write column", command=self.copy_live_to_write).pack(side="left", padx=6)
        ttk.Button(btn_frame, text="Zero ALL (D0-D30)", command=self.zero_all).pack(side="left", padx=6)

    def _build_log(self):
        frame = ttk.LabelFrame(self, text="Log")
        frame.pack(fill="both", expand=False, padx=8, pady=6)
        self.log_text = tk.Text(frame, height=6, state="disabled")
        self.log_text.pack(fill="both", expand=True)

    # ---------------- Actions ----------------
    def connect_plc(self):
        if self.worker is not None:
            return
        ip = self.ip_var.get().strip()
        try:
            port = int(self.port_var.get().strip())
        except ValueError:
            messagebox.showerror("Error", "Port must be a number")
            return
        plc_type = self.type_var.get().strip()

        self.worker = PLCWorker(ip, port, plc_type, self.read_queue, self.cmd_queue, self.status_queue)
        self.worker.start()
        self.connect_btn.config(state="disabled")
        self.disconnect_btn.config(state="normal")

    def disconnect_plc(self):
        if self.worker:
            self.worker.stop()
            self.worker = None
        self.conn_status_var.set("Disconnected")
        self.connect_btn.config(state="normal")
        self.disconnect_btn.config(state="disabled")

    def write_single(self, addr):
        try:
            value = int(self.write_vars[addr].get())
        except ValueError:
            messagebox.showerror("Error", f"Value for {addr} must be an integer")
            return
        self.cmd_queue.put(("single", addr, value))

    def write_all(self):
        try:
            values = [int(self.write_vars[f"D{r}"].get()) for r in REG_RANGE]
        except ValueError:
            messagebox.showerror("Error", "All write values must be integers")
            return
        self.cmd_queue.put(("block", HEAD_DEVICE, values))

    def copy_live_to_write(self):
        """Convenience: pull current live values into the write column,
        so you can tweak just one or two before writing them back."""
        for r in REG_RANGE:
            addr = f"D{r}"
            live = self.live_vars[addr].get()
            if live != "--":
                self.write_vars[addr].set(live)

    def zero_all(self):
        for var in self.write_vars.values():
            var.set("0")
        self.cmd_queue.put(("block", HEAD_DEVICE, [0] * len(REG_RANGE)))

    # ---------------- Queue polling / GUI refresh ----------------
    def _poll_queues(self):
        try:
            while True:
                name, values = self.read_queue.get_nowait()
                if name == "batch":
                    for r, v in zip(REG_RANGE, values):
                        self.live_vars[f"D{r}"].set(str(v))
                    d10_val = values[REG_RANGE.index(10)]
                    self.d10_raw_var.set(str(d10_val))
                    self.d10_text_var.set(d10_to_text(d10_val))
                    self.d10_history.append(d10_val)
                    self._update_chart()
                elif name == "sm":
                    for sm, bit in values.items():
                        state = "ON" if bit else "OFF"
                        self.sm_vars[sm].set(state)
                        self.sm_labels[sm].config(foreground="green" if bit else "gray")
        except queue.Empty:
            pass

        try:
            while True:
                kind, msg = self.status_queue.get_nowait()
                if kind == "status" and msg == "Connected":
                    self.conn_status_var.set("Connected")
                elif kind == "status" and msg == "Disconnected":
                    self.conn_status_var.set("Disconnected")
                self._log(f"[{kind.upper()}] {msg}")
        except queue.Empty:
            pass

        self.after(200, self._poll_queues)

    def _update_chart(self):
        ys = list(self.d10_history)
        xs = list(range(len(ys)))
        self.line.set_data(xs, ys)
        self.ax.relim()
        self.ax.autoscale_view()
        self.canvas.draw_idle()

    def _log(self, msg):
        self.log_text.config(state="normal")
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def on_close(self):
        self.disconnect_plc()
        self.destroy()


if __name__ == "__main__":
    app = Dashboard()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()