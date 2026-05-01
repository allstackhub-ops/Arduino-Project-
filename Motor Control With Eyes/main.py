#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════╗
║         ADVANCED BIOMETRIC EYE TRACKING & FATIGUE HUD                ║
║                                                                      ║
║   A highly professional, futuristic computer vision interface.       ║
║   Features:                                                          ║
║    - Precise Sub-pixel EAR (Eye Aspect Ratio) calculation            ║
║    - Smooth cinematic UI with alpha blending, animations & reticles  ║
║    - Dynamic state transitions (Active -> Drowsy -> Offline)         ║
║    - Real-time ocular telemetry graphing                             ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import cv2
import mediapipe as mp
import numpy as np
import math
import time
from collections import deque
import serial
import serial.tools.list_ports

# --- CONFIGURATION & COLORS (BGR) ---
COLOR_ACTIVE   = (0, 255, 120)    # Neon Green
COLOR_WARNING  = (0, 165, 255)    # Amber/Yellow
COLOR_CRITICAL = (0, 0, 255)      # Deep Red
COLOR_UI_BG    = (15, 15, 20)
COLOR_TEXT     = (220, 220, 220)
COLOR_GRID     = (30, 40, 30)

# EAR Thresholds
EAR_OPEN  = 0.25
EAR_CLOSE = 0.20

LEFT_EYE_PTS = [33, 160, 158, 133, 153, 144]
RIGHT_EYE_PTS = [362, 385, 387, 263, 373, 380]

class SmoothValue:
    """Smooths values for fluid UI animations using Exponential Moving Average"""
    def __init__(self, initial=0.0, speed=0.15):
        self.current = initial
        self.target = initial
        self.speed = speed

    def update(self):
        self.current += (self.target - self.current) * self.speed
        return self.current

class HUDSystem:
    def __init__(self):
        self.mp_face_mesh = mp.solutions.face_mesh
        # Use refine_landmarks=True to get iris tracking for the reticles
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.7
        )
        
        self.fatigue_level = SmoothValue(0.0, 0.05)
        self.ear_left = SmoothValue(0.3, 0.2)
        self.ear_right = SmoothValue(0.3, 0.2)
        
        self.closed_frames = 0
        self.total_blinks = 0
        self.is_blinking = False
        
        # Telemetry graphs
        self.history_l = deque([0.3]*100, maxlen=100)
        self.history_r = deque([0.3]*100, maxlen=100)
        self.log_msgs = deque(maxlen=6)
        
        self.frame_count = 0
        self.fps = SmoothValue(30.0, 0.1)
        self.last_time = time.time()
        self.log("System core initialized.")
        self.log("Awaiting biometric lock...")

        # --- ARDUINO SETUP ---
        self.arduino = None
        self.last_motor_state = -1 # -1 unknown, 0 off, 1 on
        self.init_arduino()

    def init_arduino(self):
        try:
            port = None
            for p in serial.tools.list_ports.comports():
                if "Arduino" in p.description or "CH340" in p.description or "USB Serial" in p.description:
                    port = p.device
                    break
            
            if port:
                self.arduino = serial.Serial(port, 9600, timeout=1)
                time.sleep(2) # Wait for Arduino to reset
                self.log(f"Hardware linked on {port}")
            else:
                self.log("No hardware detected (Software Mode)")
        except Exception as e:
            self.log(f"Comms error: {e}")

    def set_motor(self, state):
        if self.arduino and state != self.last_motor_state:
            try:
                cmd = b'1' if state == 1 else b'0'
                self.arduino.write(cmd)
                self.log(f"CMD: MOTOR {'ON' if state == 1 else 'OFF'}")
                self.last_motor_state = state
            except Exception:
                pass

    def log(self, msg):
        ts = time.strftime("%H:%M:%S")
        self.log_msgs.appendleft(f"[{ts}] {msg}")

    def calc_ear(self, lms, indices, w, h):
        p = [np.array([lms[i].x * w, lms[i].y * h]) for i in indices]
        v1 = np.linalg.norm(p[1] - p[5])
        v2 = np.linalg.norm(p[2] - p[4])
        hor = np.linalg.norm(p[0] - p[3])
        if hor == 0: return 0.0
        return (v1 + v2) / (2.0 * hor)

    def draw_corner_box(self, img, x, y, w, h, color, thick=2, length=20):
        cv2.line(img, (x, y), (x+length, y), color, thick, cv2.LINE_AA)
        cv2.line(img, (x, y), (x, y+length), color, thick, cv2.LINE_AA)
        cv2.line(img, (x+w, y), (x+w-length, y), color, thick, cv2.LINE_AA)
        cv2.line(img, (x+w, y), (x+w, y+length), color, thick, cv2.LINE_AA)
        cv2.line(img, (x, y+h), (x+length, y+h), color, thick, cv2.LINE_AA)
        cv2.line(img, (x, y+h), (x, y+h-length), color, thick, cv2.LINE_AA)
        cv2.line(img, (x+w, y+h), (x+w-length, y+h), color, thick, cv2.LINE_AA)
        cv2.line(img, (x+w, y+h), (x+w, y+h-length), color, thick, cv2.LINE_AA)

    def draw_reticle(self, img, cx, cy, radius, color, rotation):
        cv2.circle(img, (cx, cy), radius, color, 1, cv2.LINE_AA)
        # Inner crosshair
        size = int(radius * 0.4)
        cv2.line(img, (cx-size, cy), (cx+size, cy), color, 1, cv2.LINE_AA)
        cv2.line(img, (cx, cy-size), (cx, cy+size), color, 1, cv2.LINE_AA)
        # Outer rotating segments
        for i in range(3):
            angle = rotation + i * (2*math.pi/3)
            x1 = int(cx + math.cos(angle) * (radius + 4))
            y1 = int(cy + math.sin(angle) * (radius + 4))
            x2 = int(cx + math.cos(angle) * (radius + 12))
            y2 = int(cy + math.sin(angle) * (radius + 12))
            cv2.line(img, (x1, y1), (x2, y2), color, 2, cv2.LINE_AA)

    def render_graph(self, img, x, y, w, h, data, color, title):
        cv2.rectangle(img, (x, y), (x+w, y+h), (20,20,20), -1)
        self.draw_corner_box(img, x, y, w, h, color, thick=1, length=10)
        cv2.putText(img, title, (x+5, y+15), cv2.FONT_HERSHEY_SIMPLEX, 0.4, COLOR_TEXT, 1)
        
        if len(data) > 1:
            pts = []
            for i, val in enumerate(data):
                px = int(x + (i / len(data)) * w)
                norm_val = max(0, min(1, (val - 0.15) / 0.25))
                py = int(y + h - norm_val * h)
                pts.append((px, py))
            cv2.polylines(img, [np.array(pts, np.int32)], False, color, 1, cv2.LINE_AA)
            
            thresh_y = int(y + h - ((EAR_CLOSE - 0.15) / 0.25) * h)
            cv2.line(img, (x, thresh_y), (x+w, thresh_y), (80, 80, 80), 1, cv2.LINE_AA)

    def run(self):
        cap = cv2.VideoCapture(0)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

        if not cap.isOpened():
            print("Failed to open camera.")
            return

        cv2.namedWindow("Advanced Biometric System", cv2.WINDOW_NORMAL)

        while True:
            ret, frame = cap.read()
            if not ret: break
            
            frame = cv2.flip(frame, 1)
            img_h, img_w = frame.shape[:2]
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # FPS Calculation
            now = time.time()
            dt = now - self.last_time
            self.last_time = now
            if dt > 0: self.fps.target = 1.0 / dt
            self.fps.update()
            self.frame_count += 1
            
            # Create base overlay for HUD elements
            overlay = np.zeros_like(frame)
            
            # Background Grid
            grid_spacing = 60
            for x in range(0, img_w, grid_spacing):
                cv2.line(overlay, (x, 0), (x, img_h), COLOR_GRID, 1)
            for y in range(0, img_h, grid_spacing):
                cv2.line(overlay, (0, y), (img_w, y), COLOR_GRID, 1)

            res = self.face_mesh.process(rgb)
            state_color = COLOR_ACTIVE
            status_text = "BIOMETRICS: NOMINAL"
            
            if res.multi_face_landmarks:
                lms = res.multi_face_landmarks[0].landmark
                
                # EAR Processing
                el = self.calc_ear(lms, LEFT_EYE_PTS, img_w, img_h)
                er = self.calc_ear(lms, RIGHT_EYE_PTS, img_w, img_h)
                self.ear_left.target = el
                self.ear_right.target = er
                self.ear_left.update()
                self.ear_right.update()
                
                avg_ear = (self.ear_left.current + self.ear_right.current) / 2.0
                self.history_l.append(self.ear_left.current)
                self.history_r.append(self.ear_right.current)
                
                # Blink and Fatigue Logic
                if avg_ear < EAR_CLOSE:
                    self.closed_frames += 1
                    if not self.is_blinking:
                        self.is_blinking = True
                else:
                    if self.is_blinking:
                        self.total_blinks += 1
                        self.is_blinking = False
                        if self.closed_frames > 20:
                            self.log(f"Micro-sleep detected ({self.closed_frames} frames)")
                        else:
                            self.log("Blink registered")
                    self.closed_frames = max(0, self.closed_frames - 2)

                if self.closed_frames > 5:
                    self.fatigue_level.target = min(1.0, self.fatigue_level.target + 0.02)
                else:
                    self.fatigue_level.target = max(0.0, self.fatigue_level.target - 0.005)
                self.fatigue_level.update()

                fatigue = self.fatigue_level.current
                if fatigue > 0.7 or self.closed_frames > 30:
                    state_color = COLOR_CRITICAL
                    status_text = "SYSTEM ALERT: USER OFFLINE (EYES CLOSED)"
                    self.set_motor(0)
                elif fatigue > 0.3 or self.closed_frames > 10:
                    state_color = COLOR_WARNING
                    status_text = "WARNING: DROWSINESS DETECTED"
                    self.set_motor(1)
                else:
                    state_color = COLOR_ACTIVE
                    status_text = "BIOMETRICS: ACTIVE (EYES OPEN)"
                    self.set_motor(1)

                # Draw Visuals on face
                # 468 = Left iris, 473 = Right iris (MediaPipe specific)
                left_c = (int(lms[468].x * img_w), int(lms[468].y * img_h))
                right_c = (int(lms[473].x * img_w), int(lms[473].y * img_h))
                
                rot = self.frame_count * 0.05
                self.draw_reticle(overlay, left_c[0], left_c[1], 18, state_color, rot)
                self.draw_reticle(overlay, right_c[0], right_c[1], 18, state_color, -rot)

                # Bounding Box around face
                xs = [lm.x * img_w for lm in lms]
                ys = [lm.y * img_h for lm in lms]
                fx, fy = int(min(xs)), int(min(ys))
                fw, fh = int(max(xs)-fx), int(max(ys)-fy)
                self.draw_corner_box(overlay, fx-20, fy-20, fw+40, fh+40, state_color, thick=2, length=30)
                
                # Connecting lines from eyes to UI panels
                cv2.line(overlay, (left_c[0]-25, left_c[1]), (320, left_c[1]), state_color, 1, cv2.LINE_AA)
                cv2.line(overlay, (right_c[0]+25, right_c[1]), (img_w-320, right_c[1]), state_color, 1, cv2.LINE_AA)

            else:
                self.history_l.append(0)
                self.history_r.append(0)
                state_color = COLOR_CRITICAL
                status_text = "TARGET LOST"
                self.fatigue_level.target = 0.0
                self.fatigue_level.update()
                self.set_motor(0)

            # Blend grid & face tracking graphics
            cv2.addWeighted(overlay, 0.8, frame, 1.0, 0, frame)
            
            # --- Panels ---
            panel_bg = np.zeros_like(frame)
            
            # Left Panel
            cv2.rectangle(panel_bg, (15, 25), (330, 290), COLOR_UI_BG, -1)
            self.draw_corner_box(panel_bg, 15, 25, 315, 265, state_color, thick=2, length=15)
            
            # Right Panel
            cv2.rectangle(panel_bg, (img_w-330, 25), (img_w-15, 210), COLOR_UI_BG, -1)
            self.draw_corner_box(panel_bg, img_w-330, 25, 315, 185, state_color, thick=2, length=15)
            
            cv2.addWeighted(panel_bg, 0.85, frame, 1.0, 0, frame)

            # --- Left Panel Content ---
            cv2.putText(frame, "TELEMETRY", (30, 50), cv2.FONT_HERSHEY_DUPLEX, 0.6, state_color, 1)
            cv2.putText(frame, f"STATUS: {status_text}", (30, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.45, COLOR_TEXT if state_color != COLOR_CRITICAL else COLOR_CRITICAL, 1)
            cv2.putText(frame, f"FPS: {self.fps.current:.1f}", (30, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.45, COLOR_TEXT, 1)
            cv2.putText(frame, f"BLINKS: {self.total_blinks}", (30, 115), cv2.FONT_HERSHEY_SIMPLEX, 0.45, COLOR_TEXT, 1)
            
            # Fatigue Bar
            cv2.putText(frame, "FATIGUE LEVEL:", (30, 145), cv2.FONT_HERSHEY_SIMPLEX, 0.45, COLOR_TEXT, 1)
            bar_w = 280
            cv2.rectangle(frame, (30, 155), (30+bar_w, 170), (40,40,40), -1)
            f_w = int(self.fatigue_level.current * bar_w)
            cv2.rectangle(frame, (30, 155), (30+f_w, 170), state_color, -1)
            cv2.rectangle(frame, (30, 155), (30+bar_w, 170), (100,100,100), 1)
            
            # System Log
            cv2.putText(frame, "SYSTEM LOG:", (30, 200), cv2.FONT_HERSHEY_SIMPLEX, 0.4, state_color, 1)
            for i, msg in enumerate(self.log_msgs):
                cv2.putText(frame, msg, (30, 220 + i*15), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (180,180,180), 1)

            # --- Right Panel Content ---
            cv2.putText(frame, "OCULAR SCANNERS", (img_w-315, 50), cv2.FONT_HERSHEY_DUPLEX, 0.6, state_color, 1)
            self.render_graph(frame, img_w-315, 70, 285, 50, self.history_l, state_color, f"L-EAR: {self.ear_left.current:.3f}")
            self.render_graph(frame, img_w-315, 140, 285, 50, self.history_r, state_color, f"R-EAR: {self.ear_right.current:.3f}")

            # Critical Warning Overlay effect
            if state_color == COLOR_CRITICAL:
                if (self.frame_count % 14) < 7:  # Flash
                    alert = np.full_like(frame, (0, 0, 50), dtype=np.uint8)
                    cv2.addWeighted(alert, 0.3, frame, 1.0, 0, frame)
                    text = "SYSTEM OFFLINE / EYES CLOSED"
                    ts, _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_DUPLEX, 1.0, 2)
                    cv2.putText(frame, text, (img_w//2 - ts[0]//2, img_h//2), 
                                cv2.FONT_HERSHEY_DUPLEX, 1.0, COLOR_CRITICAL, 2)
            
            # Top/Bottom cinematic bars
            cv2.rectangle(frame, (0, 0), (img_w, 20), (10,10,10), -1)
            cv2.rectangle(frame, (0, img_h-25), (img_w, img_h), (10,10,10), -1)
            cv2.putText(frame, "[Q] EXIT SYSTEM | Advanced Biometric Eye Tracker", (10, img_h - 8), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (150,150,150), 1)

            cv2.imshow("Advanced Biometric System", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    import io, sys
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    
    print("Initializing Advanced Biometric HUD...")
    system = HUDSystem()
    system.run()