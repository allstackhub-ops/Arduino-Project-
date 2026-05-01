import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import serial
import serial.tools.list_ports
import copy
import json

# Set theme
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class MatrixApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("LED Matrix Studio Pro")
        self.geometry("850x650")
        self.minsize(800, 600)
        
        self.serial_conn = None
        self.grid_data = [[0]*8 for _ in range(8)]
        self.buttons = []
        
        # Animation State
        self.frames = []
        self.current_frame_idx = -1 # -1 means working on a new unsaved frame
        self.is_playing = False
        self.play_idx = 0
        
        self.setup_ui()
        self.refresh_ports()
        
    def setup_ui(self):
        # Configure grid layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=3)
        self.grid_rowconfigure(0, weight=1)
        
        # =========================================================================
        # LEFT PANEL: Controls & Settings
        # =========================================================================
        left_panel = ctk.CTkFrame(self, corner_radius=10)
        left_panel.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        
        # Connection Section
        conn_label = ctk.CTkLabel(left_panel, text="Hardware Connection", font=ctk.CTkFont(size=16, weight="bold"))
        conn_label.pack(pady=(15, 5), padx=10, anchor="w")
        
        self.port_var = ctk.StringVar(value="Select Port")
        self.port_menu = ctk.CTkOptionMenu(left_panel, variable=self.port_var, values=["No Ports Found"])
        self.port_menu.pack(pady=5, padx=15, fill="x")
        
        btn_row_conn = ctk.CTkFrame(left_panel, fg_color="transparent")
        btn_row_conn.pack(pady=5, padx=15, fill="x")
        
        refresh_btn = ctk.CTkButton(btn_row_conn, text="Refresh", width=80, command=self.refresh_ports)
        refresh_btn.pack(side="left", padx=(0, 5), expand=True)
        
        self.connect_btn = ctk.CTkButton(btn_row_conn, text="Connect", width=80, fg_color="#28a745", hover_color="#218838", command=self.toggle_connect)
        self.connect_btn.pack(side="right", padx=(5, 0), expand=True)
        
        # Transform Tools Section
        tools_label = ctk.CTkLabel(left_panel, text="Transform Tools", font=ctk.CTkFont(size=16, weight="bold"))
        tools_label.pack(pady=(20, 5), padx=10, anchor="w")
        
        shift_row1 = ctk.CTkFrame(left_panel, fg_color="transparent")
        shift_row1.pack(pady=2, padx=15, fill="x")
        ctk.CTkButton(shift_row1, text="▲ Up", command=lambda: self.shift("up")).pack(side="left", padx=2, expand=True)
        ctk.CTkButton(shift_row1, text="▼ Down", command=lambda: self.shift("down")).pack(side="right", padx=2, expand=True)

        shift_row2 = ctk.CTkFrame(left_panel, fg_color="transparent")
        shift_row2.pack(pady=2, padx=15, fill="x")
        ctk.CTkButton(shift_row2, text="◀ Left", command=lambda: self.shift("left")).pack(side="left", padx=2, expand=True)
        ctk.CTkButton(shift_row2, text="▶ Right", command=lambda: self.shift("right")).pack(side="right", padx=2, expand=True)
        
        ctk.CTkButton(left_panel, text="Invert Colors", command=self.invert_grid).pack(pady=(5, 15), padx=15, fill="x")
        ctk.CTkButton(left_panel, text="Clear Grid", fg_color="#dc3545", hover_color="#c82333", command=self.clear_grid).pack(pady=5, padx=15, fill="x")
        
        # Project Management Section
        proj_label = ctk.CTkLabel(left_panel, text="Project Files", font=ctk.CTkFont(size=16, weight="bold"))
        proj_label.pack(pady=(20, 5), padx=10, anchor="w")
        
        ctk.CTkButton(left_panel, text="Save Animation (.json)", command=self.save_project).pack(pady=2, padx=15, fill="x")
        ctk.CTkButton(left_panel, text="Load Animation (.json)", command=self.load_project).pack(pady=2, padx=15, fill="x")

        # =========================================================================
        # RIGHT PANEL: Canvas & Animation
        # =========================================================================
        right_panel = ctk.CTkFrame(self, fg_color="transparent")
        right_panel.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        right_panel.grid_rowconfigure(0, weight=1)
        right_panel.grid_rowconfigure(1, weight=0)
        
        # Drawing Canvas Frame
        canvas_frame = ctk.CTkFrame(right_panel, corner_radius=10)
        canvas_frame.grid(row=0, column=0, pady=(0, 10), sticky="nsew")
        
        canvas_label = ctk.CTkLabel(canvas_frame, text="Design Canvas", font=ctk.CTkFont(size=20, weight="bold"))
        canvas_label.pack(pady=(15, 0))
        
        # Center the grid
        grid_container = ctk.CTkFrame(canvas_frame, fg_color="transparent")
        grid_container.pack(expand=True)
        
        for r in range(8):
            row_btns = []
            for c in range(8):
                btn = ctk.CTkButton(grid_container, text="", width=45, height=45, fg_color="#333333", hover_color="#555555", corner_radius=5, command=lambda r=r, c=c: self.toggle_pixel(r, c))
                btn.grid(row=r, column=c, padx=2, pady=2)
                row_btns.append(btn)
            self.buttons.append(row_btns)
            
        send_btn = ctk.CTkButton(canvas_frame, text="Send Current Frame to Display", fg_color="#17a2b8", hover_color="#138496", font=ctk.CTkFont(weight="bold"), command=self.send_data)
        send_btn.pack(pady=15, padx=20, fill="x")
            
        # Animation Timeline Frame
        timeline_frame = ctk.CTkFrame(right_panel, corner_radius=10, height=180)
        timeline_frame.grid(row=1, column=0, sticky="nsew")
        
        timeline_title = ctk.CTkLabel(timeline_frame, text="Animation Timeline", font=ctk.CTkFont(size=16, weight="bold"))
        timeline_title.pack(pady=(10, 0))

        self.frame_info_lbl = ctk.CTkLabel(timeline_frame, text="Total Frames: 0  |  Current Selected: None", font=ctk.CTkFont(weight="normal"), text_color="#aaaaaa")
        self.frame_info_lbl.pack(pady=(0, 5))
        
        timeline_ctrls = ctk.CTkFrame(timeline_frame, fg_color="transparent")
        timeline_ctrls.pack(pady=5, padx=10, fill="x")
        
        # Frame editing buttons
        ctk.CTkButton(timeline_ctrls, text="➕ Add Frame", width=90, fg_color="#28a745", hover_color="#218838", command=self.add_frame).pack(side="left", padx=2, expand=True)
        ctk.CTkButton(timeline_ctrls, text="Save Edits", width=90, command=self.update_current_frame).pack(side="left", padx=2, expand=True)
        ctk.CTkButton(timeline_ctrls, text="Duplicate", width=90, command=self.duplicate_frame).pack(side="left", padx=2, expand=True)
        ctk.CTkButton(timeline_ctrls, text="🗑 Delete", width=90, fg_color="#dc3545", hover_color="#c82333", command=self.delete_frame).pack(side="left", padx=2, expand=True)
        
        nav_ctrls = ctk.CTkFrame(timeline_frame, fg_color="transparent")
        nav_ctrls.pack(pady=5, padx=10, fill="x")
        
        ctk.CTkButton(nav_ctrls, text="◀ Prev Frame", width=100, command=self.prev_frame).pack(side="left", padx=2)
        ctk.CTkButton(nav_ctrls, text="Next Frame ▶", width=100, command=self.next_frame).pack(side="left", padx=2)
        
        self.play_btn = ctk.CTkButton(nav_ctrls, text="▶ Play Animation", width=140, font=ctk.CTkFont(weight="bold"), fg_color="#007bff", hover_color="#0056b3", command=self.toggle_animation)
        self.play_btn.pack(side="right", padx=2)
        
        speed_frame = ctk.CTkFrame(timeline_frame, fg_color="transparent")
        speed_frame.pack(pady=10, padx=20, fill="x")
        
        self.speed_lbl = ctk.CTkLabel(speed_frame, text="Speed: 200 ms", font=ctk.CTkFont(weight="bold"))
        self.speed_lbl.pack(side="left", padx=(0, 10))
        self.speed_scale = ctk.CTkSlider(speed_frame, from_=50, to=1000, number_of_steps=95, command=self.update_speed_lbl)
        self.speed_scale.set(200)
        self.speed_scale.pack(side="left", fill="x", expand=True)

    # --- Core Logic ---
    def update_speed_lbl(self, val):
        self.speed_lbl.configure(text=f"Speed: {int(val)} ms")
        
    def refresh_ports(self):
        ports = [port.device for port in serial.tools.list_ports.comports()]
        if ports:
            self.port_menu.configure(values=ports)
            self.port_var.set(ports[0])
        else:
            self.port_menu.configure(values=["No Ports Found"])
            self.port_var.set("No Ports Found")
            
    def toggle_connect(self):
        if self.serial_conn and self.serial_conn.is_open:
            self.is_playing = False
            self.play_btn.configure(text="▶ Play Animation", fg_color="#007bff", hover_color="#0056b3")
            self.serial_conn.close()
            self.connect_btn.configure(text="Connect", fg_color="#28a745", hover_color="#218838")
        else:
            port = self.port_var.get()
            if port and "No" not in port:
                try:
                    self.serial_conn = serial.Serial(port, 9600, timeout=1)
                    self.connect_btn.configure(text="Disconnect", fg_color="#dc3545", hover_color="#c82333")
                except Exception as e:
                    messagebox.showerror("Connection Error", str(e))
                    
    def toggle_pixel(self, r, c):
        if self.grid_data[r][c] == 0:
            self.grid_data[r][c] = 1
            self.buttons[r][c].configure(fg_color="#ffc107", hover_color="#e0a800")
        else:
            self.grid_data[r][c] = 0
            self.buttons[r][c].configure(fg_color="#333333", hover_color="#555555")
            
    def clear_grid(self):
        for r in range(8):
            for c in range(8):
                self.grid_data[r][c] = 0
                self.buttons[r][c].configure(fg_color="#333333", hover_color="#555555")
                
    def invert_grid(self):
        for r in range(8):
            for c in range(8):
                self.grid_data[r][c] = 1 - self.grid_data[r][c]
                color = "#ffc107" if self.grid_data[r][c] == 1 else "#333333"
                h_color = "#e0a800" if self.grid_data[r][c] == 1 else "#555555"
                self.buttons[r][c].configure(fg_color=color, hover_color=h_color)
                
    def shift(self, direction):
        new_grid = [[0]*8 for _ in range(8)]
        if direction == "up":
            for r in range(7): new_grid[r] = copy.copy(self.grid_data[r+1])
        elif direction == "down":
            for r in range(1, 8): new_grid[r] = copy.copy(self.grid_data[r-1])
        elif direction == "left":
            for r in range(8):
                for c in range(7): new_grid[r][c] = self.grid_data[r][c+1]
        elif direction == "right":
            for r in range(8):
                for c in range(1, 8): new_grid[r][c] = self.grid_data[r][c-1]
        
        self.load_grid(new_grid)
        
    def load_grid(self, grid):
        self.grid_data = copy.deepcopy(grid)
        for r in range(8):
            for c in range(8):
                color = "#ffc107" if self.grid_data[r][c] == 1 else "#333333"
                h_color = "#e0a800" if self.grid_data[r][c] == 1 else "#555555"
                self.buttons[r][c].configure(fg_color=color, hover_color=h_color)

    # --- Timeline Management ---
    def update_timeline_lbl(self):
        if not self.frames:
            self.frame_info_lbl.configure(text="Total Frames: 0  |  Current Selected: None")
        else:
            self.frame_info_lbl.configure(text=f"Total Frames: {len(self.frames)}  |  Current Selected: Frame {self.current_frame_idx + 1}")

    def add_frame(self):
        self.frames.append(copy.deepcopy(self.grid_data))
        self.current_frame_idx = len(self.frames) - 1
        self.update_timeline_lbl()
        
    def update_current_frame(self):
        if self.current_frame_idx >= 0 and self.current_frame_idx < len(self.frames):
            self.frames[self.current_frame_idx] = copy.deepcopy(self.grid_data)
        else:
            messagebox.showwarning("Warning", "No frame selected to update.")

    def duplicate_frame(self):
        if self.current_frame_idx >= 0 and self.current_frame_idx < len(self.frames):
            self.frames.insert(self.current_frame_idx + 1, copy.deepcopy(self.frames[self.current_frame_idx]))
            self.current_frame_idx += 1
            self.update_timeline_lbl()
        else:
            self.add_frame()

    def delete_frame(self):
        if self.current_frame_idx >= 0 and self.current_frame_idx < len(self.frames):
            self.frames.pop(self.current_frame_idx)
            if self.current_frame_idx >= len(self.frames):
                self.current_frame_idx = len(self.frames) - 1
            
            if self.current_frame_idx >= 0:
                self.load_grid(self.frames[self.current_frame_idx])
            else:
                self.clear_grid()
                
            self.update_timeline_lbl()

    def prev_frame(self):
        if self.frames and self.current_frame_idx > 0:
            self.current_frame_idx -= 1
            self.load_grid(self.frames[self.current_frame_idx])
            self.update_timeline_lbl()

    def next_frame(self):
        if self.frames and self.current_frame_idx < len(self.frames) - 1:
            self.current_frame_idx += 1
            self.load_grid(self.frames[self.current_frame_idx])
            self.update_timeline_lbl()

    # --- Project Management ---
    def save_project(self):
        if not self.frames:
            messagebox.showwarning("Warning", "No frames to save!")
            return
        filepath = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json")])
        if filepath:
            try:
                with open(filepath, 'w') as f:
                    json.dump({"frames": self.frames}, f)
                messagebox.showinfo("Success", "Animation saved successfully!")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save: {e}")

    def load_project(self):
        filepath = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
        if filepath:
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                if "frames" in data:
                    self.frames = data["frames"]
                    self.current_frame_idx = 0 if self.frames else -1
                    if self.frames:
                        self.load_grid(self.frames[0])
                    self.update_timeline_lbl()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load: {e}")

    # --- Animation & Hardware ---
    def toggle_animation(self):
        if not self.frames:
            messagebox.showwarning("Warning", "Please add some frames to animate!")
            return
            
        if not self.serial_conn or not self.serial_conn.is_open:
            messagebox.showwarning("Warning", "Please connect to the Arduino first!")
            return
            
        if self.is_playing:
            self.is_playing = False
            self.play_btn.configure(text="▶ Play Animation", fg_color="#007bff", hover_color="#0056b3")
        else:
            self.is_playing = True
            self.play_btn.configure(text="⏹ Stop Animation", fg_color="#dc3545", hover_color="#c82333")
            self.play_idx = 0
            self.animate()
            
    def animate(self):
        if self.is_playing and self.frames:
            frame = self.frames[self.play_idx]
            self.load_grid(frame)
            self.send_data()
            
            self.current_frame_idx = self.play_idx
            self.update_timeline_lbl()
            
            self.play_idx = (self.play_idx + 1) % len(self.frames)
            
            delay = int(self.speed_scale.get())
            self.after(delay, self.animate)
            
    def send_data(self):
        if not self.serial_conn or not self.serial_conn.is_open:
            if not self.is_playing:
                messagebox.showwarning("Warning", "Please connect to the Arduino first!")
            return
            
        data_bytes = bytearray()
        for r in range(8):
            byte_val = 0
            for c in range(8):
                if self.grid_data[r][c] == 1:
                    byte_val |= (1 << (7 - c))
            data_bytes.append(byte_val)
            
        try:
            self.serial_conn.write(data_bytes)
        except Exception as e:
            if not self.is_playing:
                messagebox.showerror("Send Error", str(e))
            self.is_playing = False
            self.play_btn.configure(text="▶ Play Animation", fg_color="#007bff", hover_color="#0056b3")

if __name__ == "__main__":
    app = MatrixApp()
    app.mainloop()
