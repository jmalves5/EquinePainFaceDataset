#!/usr/bin/env python3
"""
Equine Pain Face Dataset Annotation Viewer
GUI application to view video clips with annotations
"""

import json
import tkinter as tk
from tkinter import ttk, messagebox
import cv2
from PIL import Image, ImageTk
import threading
import time
import os
from pathlib import Path


class AnnotationViewer:
    def __init__(self, root):
        self.root = root
        self.root.title("Equine Pain Face Dataset - Annotation Viewer")
        self.root.geometry("1400x800")
        
        # Paths (will be set after file selection)
        self.base_path = None
        self.json_path = None
        self.videos_path = None
        
        # Data
        self.annotations = {}  # Original annotations from JSON
        self.edited_annotations = {}  # Editable copy for export
        self.current_video = None
        self.current_annotation_index = 0
        self.cap = None
        self.playing = False
        self.video_thread = None
        self.class_checkboxes = {}  # Store checkbox variables by class
        self.annotation_items = []  # Store annotation display items
        self.has_edits = False  # Track if there are unsaved edits
        
        # UI setup
        self.setup_ui()
        
        # Prompt for JSON file and load
        if not self.select_json_file():
            messagebox.showwarning("No File Selected", "No annotations file selected. Please select a file to continue.")
            self.root.after(100, self.select_json_file_or_exit)
        else:
            self.load_annotations()
        
        # Keyboard shortcuts
        self.root.bind("<Left>", lambda e: self.step_back_frame())
        self.root.bind("<Right>", lambda e: self.step_forward_frame())
        self.root.bind("<space>", lambda e: self.toggle_play())
        self.root.bind("<Delete>", lambda e: self.delete_annotation())
        self.root.bind("<BackSpace>", lambda e: self.delete_annotation())
        
        # Knob adjustment shortcuts
        self.root.bind("<Shift-Left>", lambda e: self.adjust_knob('start', -0.1))
        self.root.bind("<Shift-Right>", lambda e: self.adjust_knob('start', 0.1))
        self.root.bind("<Control-Left>", lambda e: self.adjust_knob('end', -0.1))
        self.root.bind("<Control-Right>", lambda e: self.adjust_knob('end', 0.1))
        
    def setup_ui(self):
        """Setup the user interface"""
        # Main container
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Left panel - Video list
        left_panel = ttk.Frame(main_frame, width=250)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 5))
        
        ttk.Label(left_panel, text="Videos", font=("Arial", 12, "bold")).pack(pady=5)
        
        # Video listbox with scrollbar
        video_frame = ttk.Frame(left_panel)
        video_frame.pack(fill=tk.BOTH, expand=True)
        
        video_scrollbar = ttk.Scrollbar(video_frame)
        video_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.video_listbox = tk.Listbox(video_frame, yscrollcommand=video_scrollbar.set)
        self.video_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.video_listbox.bind('<<ListboxSelect>>', self.on_video_select)
        
        video_scrollbar.config(command=self.video_listbox.yview)
        
        # Right panel - Video and annotations
        right_panel = ttk.Frame(main_frame)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Video info
        info_frame = ttk.Frame(right_panel)
        info_frame.pack(fill=tk.X, pady=(0, 5))
        
        self.video_label = ttk.Label(info_frame, text="Select a video", font=("Arial", 14, "bold"))
        self.video_label.pack(side=tk.LEFT)
        
        ttk.Button(info_frame, text="Export JSON", command=self.export_json).pack(side=tk.RIGHT, padx=5)
        ttk.Button(info_frame, text="Dump All Clips", command=self.dump_all_clips).pack(side=tk.RIGHT, padx=5)
        ttk.Button(info_frame, text="Load JSON", command=self.reload_json).pack(side=tk.RIGHT, padx=5)
        
        self.annotation_count_label = ttk.Label(info_frame, text="", font=("Arial", 10))
        self.annotation_count_label.pack(side=tk.RIGHT)
        
        # Video display
        video_display_frame = ttk.Frame(right_panel, relief=tk.SUNKEN, borderwidth=2)
        video_display_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        
        self.video_canvas = tk.Canvas(video_display_frame, bg="black", width=800, height=450)
        self.video_canvas.pack(fill=tk.BOTH, expand=True)
        
        # Annotations panel - split into classes and annotations
        annotations_frame = ttk.Frame(right_panel)
        annotations_frame.pack(fill=tk.BOTH, pady=(0, 5), expand=True)
        
        # Left side: Classes with checkboxes
        classes_frame = ttk.LabelFrame(annotations_frame, text="Annotation Classes", padding=10)
        classes_frame.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 5))
        
        # Control buttons for classes
        class_control_frame = ttk.Frame(classes_frame)
        class_control_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Button(class_control_frame, text="Select All", command=self.select_all_classes).pack(side=tk.LEFT, padx=2)
        ttk.Button(class_control_frame, text="Deselect All", command=self.deselect_all_classes).pack(side=tk.LEFT, padx=2)
        
        # Scrollable frame for class checkboxes
        class_scroll_frame = ttk.Frame(classes_frame)
        class_scroll_frame.pack(fill=tk.BOTH, expand=True)
        
        class_canvas = tk.Canvas(class_scroll_frame, width=200)
        class_scrollbar = ttk.Scrollbar(class_scroll_frame, orient="vertical", command=class_canvas.yview)
        self.classes_container = ttk.Frame(class_canvas)
        
        self.classes_container.bind(
            "<Configure>",
            lambda e: class_canvas.configure(scrollregion=class_canvas.bbox("all"))
        )
        
        class_canvas.create_window((0, 0), window=self.classes_container, anchor="nw")
        class_canvas.configure(yscrollcommand=class_scrollbar.set)
        
        class_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        class_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Right side: Annotations list
        annotations_list_frame = ttk.LabelFrame(annotations_frame, text="Annotations", padding=10)
        annotations_list_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Scrollable frame for annotations
        ann_scroll_frame = ttk.Frame(annotations_list_frame)
        ann_scroll_frame.pack(fill=tk.BOTH, expand=True)
        
        ann_canvas = tk.Canvas(ann_scroll_frame)
        ann_scrollbar = ttk.Scrollbar(ann_scroll_frame, orient="vertical", command=ann_canvas.yview)
        self.annotations_container = ttk.Frame(ann_canvas)
        
        self.annotations_container.bind(
            "<Configure>",
            lambda e: ann_canvas.configure(scrollregion=ann_canvas.bbox("all"))
        )
        
        ann_canvas.create_window((0, 0), window=self.annotations_container, anchor="nw")
        ann_canvas.configure(yscrollcommand=ann_scrollbar.set)
        
        ann_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ann_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Control panel
        control_frame = ttk.Frame(right_panel)
        control_frame.pack(fill=tk.X)
        
        self.play_button = ttk.Button(control_frame, text="▶ Play Clip", command=self.toggle_play)
        self.play_button.pack(side=tk.LEFT, padx=2)
        
        self.stop_button = ttk.Button(control_frame, text="⏹ Stop", command=self.stop_video)
        self.stop_button.pack(side=tk.LEFT, padx=2)
        
        ttk.Separator(control_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        
        ttk.Button(control_frame, text="◀◀ Frame", command=self.step_back_frame).pack(side=tk.LEFT, padx=2)
        ttk.Button(control_frame, text="Frame ▶▶", command=self.step_forward_frame).pack(side=tk.LEFT, padx=2)
        
        ttk.Separator(control_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        
        ttk.Button(control_frame, text="⏮ Previous", command=self.previous_annotation).pack(side=tk.LEFT, padx=2)
        ttk.Button(control_frame, text="⏭ Next", command=self.next_annotation).pack(side=tk.LEFT, padx=2)
        
        self.clip_info_label = ttk.Label(control_frame, text="")
        self.clip_info_label.pack(side=tk.LEFT, padx=20)
        
        # Timeline canvas (replaces simple progress bar)
        timeline_frame = ttk.Frame(right_panel)
        timeline_frame.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Label(timeline_frame, text="Timeline:").pack(side=tk.LEFT, padx=(0, 5))
        
        self.timeline_canvas = tk.Canvas(timeline_frame, height=60, bg="white", relief=tk.SUNKEN, borderwidth=1)
        self.timeline_canvas.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Timeline adjustment controls
        timeline_controls = ttk.Frame(right_panel)
        timeline_controls.pack(fill=tk.X, pady=(2, 0))
        
        ttk.Label(timeline_controls, text="Adjust:").pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(timeline_controls, text="◄ Start", width=10, command=lambda: self.adjust_knob('start', -0.1)).pack(side=tk.LEFT, padx=2)
        ttk.Button(timeline_controls, text="Start ►", width=10, command=lambda: self.adjust_knob('start', 0.1)).pack(side=tk.LEFT, padx=2)
        
        ttk.Separator(timeline_controls, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        
        ttk.Button(timeline_controls, text="◄ End", width=10, command=lambda: self.adjust_knob('end', -0.1)).pack(side=tk.LEFT, padx=2)
        ttk.Button(timeline_controls, text="End ►", width=10, command=lambda: self.adjust_knob('end', 0.1)).pack(side=tk.LEFT, padx=2)
        
        ttk.Label(timeline_controls, text="(Shift+←/→: Start, Ctrl+←/→: End)", font=("Arial", 8), foreground="gray").pack(side=tk.LEFT, padx=10)
        
        # Timeline interaction variables
        self.timeline_duration = 0  # Total duration of current clip (including +1s buffer)
        self.timeline_start = 0  # Annotation start time (relative to video)
        self.timeline_end = 0  # Annotation end time (relative to video)
        self.dragging_knob = None  # 'start' or 'end' when dragging
        self.playback_position = 0  # Current playback position
        
        # Bind mouse events for dragging
        self.timeline_canvas.bind("<Button-1>", self.on_timeline_click)
        self.timeline_canvas.bind("<B1-Motion>", self.on_timeline_drag)
        self.timeline_canvas.bind("<ButtonRelease-1>", self.on_timeline_release)
        self.timeline_canvas.bind("<Configure>", lambda e: self.draw_timeline())
        self.timeline_canvas.bind("<Motion>", self.on_timeline_motion)
        
        # Schedule initial timeline draw after window is shown
        self.root.after(100, self.draw_timeline)
        
        # Annotation editing panel
        edit_frame = ttk.LabelFrame(right_panel, text="Edit Current Annotation", padding=10)
        edit_frame.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Label(edit_frame, text="Code:").pack(side=tk.LEFT, padx=(0, 5))
        
        self.edit_code_var = tk.StringVar()
        self.edit_code_entry = ttk.Entry(edit_frame, textvariable=self.edit_code_var, width=15)
        self.edit_code_entry.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Label(edit_frame, text="Start:").pack(side=tk.LEFT, padx=(10, 5))
        self.edit_start_var = tk.StringVar()
        self.edit_start_label = ttk.Label(edit_frame, textvariable=self.edit_start_var, width=12, relief=tk.SUNKEN)
        self.edit_start_label.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Label(edit_frame, text="End:").pack(side=tk.LEFT, padx=(10, 5))
        self.edit_end_var = tk.StringVar()
        self.edit_end_label = ttk.Label(edit_frame, textvariable=self.edit_end_var, width=12, relief=tk.SUNKEN)
        self.edit_end_label.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Label(edit_frame, text="Duration:").pack(side=tk.LEFT, padx=(10, 5))
        self.edit_duration_var = tk.StringVar()
        self.edit_duration_label = ttk.Label(edit_frame, textvariable=self.edit_duration_var, width=8, relief=tk.SUNKEN)
        self.edit_duration_label.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(edit_frame, text="Save Edit", command=self.save_annotation_edit).pack(side=tk.LEFT, padx=2)
        ttk.Button(edit_frame, text="Revert", command=self.revert_annotation_edit).pack(side=tk.LEFT, padx=2)
        ttk.Button(edit_frame, text="Delete", command=self.delete_annotation).pack(side=tk.LEFT, padx=2)
        
        self.edit_status_label = ttk.Label(edit_frame, text="", foreground="green")
        self.edit_status_label.pack(side=tk.LEFT, padx=10)
        
    def select_json_file(self):
        """Prompt user to select a JSON annotations file"""
        from tkinter import filedialog
        
        # Default to looking in the script directory
        default_dir = Path(__file__).parent
        
        filepath = filedialog.askopenfilename(
            title="Select Annotations JSON File",
            initialdir=default_dir,
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if not filepath:
            return False  # User cancelled
        
        self.json_path = Path(filepath)
        
        # Try to infer videos path
        # Assume videos are in a sibling 'videos' folder or parent's 'videos' folder
        json_parent = self.json_path.parent
        
        # Check common patterns
        possible_video_paths = [
            json_parent.parent / "videos",  # ../videos (if JSON is in JSONAnnotations)
            json_parent / "videos",  # ./videos (if JSON is in base folder)
            json_parent.parent.parent / "videos",  # ../../videos
        ]
        
        for video_path in possible_video_paths:
            if video_path.exists() and video_path.is_dir():
                self.videos_path = video_path
                break
        
        # If not found, ask user
        if self.videos_path is None:
            messagebox.showwarning(
                "Videos Folder Not Found",
                "Could not automatically locate videos folder. Please select it."
            )
            video_dir = filedialog.askdirectory(
                title="Select Videos Folder",
                initialdir=json_parent
            )
            if video_dir:
                self.videos_path = Path(video_dir)
            else:
                # Default to JSON folder
                self.videos_path = json_parent
        
        self.base_path = self.json_path.parent.parent if (self.json_path.parent.name == "JSONAnnotations") else self.json_path.parent
        
        # Update window title with loaded file
        self.root.title(f"Equine Pain Face Dataset - {self.json_path.name}")
        
        return True
    
    def select_json_file_or_exit(self):
        """Retry file selection or exit"""
        if not self.select_json_file():
            self.root.destroy()
        else:
            self.load_annotations()
    
    def load_annotations(self):
        """Load annotations from JSON file"""
        if not self.json_path:
            messagebox.showerror("Error", "No JSON file selected")
            return
            
        try:
            with open(self.json_path, 'r') as f:
                self.annotations = json.load(f)
            
            # Create editable copy with deep copy
            import copy
            self.edited_annotations = copy.deepcopy(self.annotations)
            
            # Populate video listbox
            for video_name in sorted(self.annotations.keys()):
                self.video_listbox.insert(tk.END, video_name)
                
            messagebox.showinfo("Success", f"Loaded {len(self.annotations)} videos with annotations")
        except FileNotFoundError:
            messagebox.showerror("Error", f"Annotations file not found: {self.json_path}")
        except json.JSONDecodeError:
            messagebox.showerror("Error", "Invalid JSON format in annotations file")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load annotations: {str(e)}")
    
    def on_video_select(self, event):
        """Handle video selection from listbox"""
        selection = self.video_listbox.curselection()
        if not selection:
            return
            
        video_name = self.video_listbox.get(selection[0])
        self.load_video(video_name)
    
    def get_annotation_class(self, code):
        """Extract class from annotation code by removing R/L suffix"""
        if code.endswith('R') or code.endswith('L'):
            return code[:-1]
        return code
    
    def load_video(self, video_name):
        """Load a video and its annotations"""
        self.stop_video()
        
        self.current_video = video_name
        self.current_annotation_index = 0
        
        # Update video info
        self.video_label.config(text=video_name)
        video_annotations = self.edited_annotations.get(video_name, [])
        self.annotation_count_label.config(text=f"{len(video_annotations)} annotations")
        
        # Extract unique classes
        classes = {}
        for ann in video_annotations:
            cls = self.get_annotation_class(ann['Code'])
            if cls not in classes:
                classes[cls] = 0
            classes[cls] += 1
        
        # Clear previous class checkboxes
        for widget in self.classes_container.winfo_children():
            widget.destroy()
        self.class_checkboxes = {}
        
        # Create checkbox for each class
        for cls in sorted(classes.keys()):
            frame = ttk.Frame(self.classes_container)
            frame.pack(fill=tk.X, padx=5, pady=2)
            
            var = tk.BooleanVar(value=True)  # Selected by default
            self.class_checkboxes[cls] = var
            
            cb = ttk.Checkbutton(frame, variable=var, command=self.update_displayed_annotations)
            cb.pack(side=tk.LEFT)
            
            label = ttk.Label(frame, text=f"{cls} ({classes[cls]})")
            label.pack(side=tk.LEFT, padx=5)
        
        # Clear previous annotation items
        for widget in self.annotations_container.winfo_children():
            widget.destroy()
        self.annotation_items = []
        
        # Create display item for each annotation
        for idx, ann in enumerate(video_annotations):
            frame = ttk.Frame(self.annotations_container)
            frame.pack(fill=tk.X, padx=5, pady=2)
            
            # Annotation details
            label_text = f"{idx+1}. {ann['Code']} | {ann['Start time']} → {ann['End time']} ({ann['Duration (s)']}s)"
            label = tk.Label(frame, text=label_text, cursor="hand2", anchor="w", background="white", padx=5, pady=2)
            label.pack(side=tk.LEFT, fill=tk.X, expand=True)
            
            # Make label clickable
            label.bind("<Button-1>", lambda e, i=idx: self.select_and_load_annotation(i))
            
            self.annotation_items.append((frame, label, idx, ann))
        
        # Update display
        self.update_displayed_annotations()
        
        # Load first visible annotation if available
        if video_annotations:
            self.load_clip(0)
            self.highlight_current_annotation()
    
    def select_and_load_annotation(self, index):
        """Load annotation when clicked"""
        self.current_annotation_index = index
        self.load_clip(index)
        self.highlight_current_annotation()
    
    def highlight_current_annotation(self):
        """Highlight the currently playing annotation"""
        for frame, label, idx, ann in self.annotation_items:
            if idx == self.current_annotation_index:
                label.configure(background="#cce5ff", relief=tk.SOLID, borderwidth=1)
            else:
                label.configure(background="white", relief=tk.FLAT, borderwidth=0)
    
    def is_annotation_visible(self, ann):
        """Check if annotation should be visible based on class selection"""
        cls = self.get_annotation_class(ann['Code'])
        return self.class_checkboxes.get(cls, tk.BooleanVar(value=True)).get()
    
    def seconds_to_time(self, seconds):
        """Convert seconds to time string HH:MM:SS.mmm"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"
    
    def save_annotation_edit(self):
        """Save the edited annotation code and timing"""
        if not self.current_video:
            return
        
        video_annotations = self.edited_annotations.get(self.current_video, [])
        if self.current_annotation_index >= len(video_annotations):
            return
        
        new_code = self.edit_code_var.get().strip()
        if not new_code:
            messagebox.showwarning("Invalid Code", "Annotation code cannot be empty")
            return
        
        # Get the annotation
        annotation = video_annotations[self.current_annotation_index]
        old_code = annotation['Code']
        
        # Update code
        annotation['Code'] = new_code
        
        # Update timing from timeline
        new_start_time = self.seconds_to_time(self.timeline_start)
        new_end_time = self.seconds_to_time(self.timeline_end)
        new_duration = self.timeline_end - self.timeline_start
        
        annotation['Start time'] = new_start_time
        annotation['End time'] = new_end_time
        annotation['Duration (s)'] = round(new_duration, 2)
        
        # Mark as having edits
        self.has_edits = True
        
        # Update display
        changes = []
        if old_code != new_code:
            changes.append(f"Code: {old_code} → {new_code}")
        changes.append(f"Timing updated")
        self.edit_status_label.config(text=f"✓ Saved: {', '.join(changes)}", foreground="green")
        
        # Refresh the annotations list to show the new code
        self.load_video(self.current_video)
        self.load_clip(self.current_annotation_index)
    
    def revert_annotation_edit(self):
        """Revert the current annotation to original"""
        if not self.current_video:
            return
        
        video_annotations = self.edited_annotations.get(self.current_video, [])
        original_annotations = self.annotations.get(self.current_video, [])
        
        if self.current_annotation_index >= len(video_annotations):
            return
        
        # Revert to original
        video_annotations[self.current_annotation_index]['Code'] = \
            original_annotations[self.current_annotation_index]['Code']
        
        # Update display
        self.edit_status_label.config(text="✓ Reverted to original", foreground="blue")
        
        # Refresh the annotations list
        self.load_video(self.current_video)
        self.load_clip(self.current_annotation_index)
    
    def delete_annotation(self):
        """Delete the current annotation"""
        if not self.current_video:
            return
        
        video_annotations = self.edited_annotations.get(self.current_video, [])
        if self.current_annotation_index >= len(video_annotations):
            return
        
        # Get annotation info for confirmation
        annotation = video_annotations[self.current_annotation_index]
        
        # Confirm deletion
        response = messagebox.askyesno(
            "Delete Annotation",
            f"Are you sure you want to delete this annotation?\n\n"
            f"Code: {annotation['Code']}\n"
            f"Start: {annotation['Start time']}\n"
            f"End: {annotation['End time']}\n"
            f"Duration: {annotation['Duration (s)']}s\n\n"
            f"This action can be undone by not saving the export."
        )
        
        if not response:
            return  # User cancelled
        
        # Delete the annotation
        deleted_code = annotation['Code']
        del video_annotations[self.current_annotation_index]
        
        # Mark as having edits
        self.has_edits = True
        
        # Update status
        self.edit_status_label.config(
            text=f"✓ Deleted: {deleted_code}", 
            foreground="red"
        )
        
        # Determine which annotation to load next
        if len(video_annotations) == 0:
            # No annotations left for this video
            messagebox.showinfo("No Annotations", f"All annotations deleted for {self.current_video}")
            self.stop_video()
            self.current_annotation_index = 0
            # Reload to clear the display
            self.load_video(self.current_video)
        else:
            # Load the same index (which is now the next annotation) or previous if at end
            if self.current_annotation_index >= len(video_annotations):
                self.current_annotation_index = len(video_annotations) - 1
            
            # Reload the video to refresh the list, then load the new current annotation
            self.load_video(self.current_video)
            self.load_clip(self.current_annotation_index)
    
    def reload_json(self):
        """Reload or load a different JSON annotations file"""
        # Check for unsaved changes
        if self.has_edits:
            response = messagebox.askyesnocancel(
                "Unsaved Changes",
                "You have unsaved changes. Do you want to export them before loading a new file?\\n\\n"
                "Yes: Export and then load new file\\n"
                "No: Discard changes and load new file\\n"
                "Cancel: Don't load new file"
            )
            
            if response is None:  # Cancel
                return
            elif response:  # Yes - export first
                self.export_json()
        
        # Properly cleanup video resources
        self.playing = False
        
        # Wait for video thread to finish
        if self.video_thread and self.video_thread.is_alive():
            time.sleep(0.2)  # Give thread time to finish
        
        # Release video capture
        if self.cap:
            self.cap.release()
            self.cap = None
        
        # Clear current data
        self.video_listbox.delete(0, tk.END)
        for widget in self.classes_container.winfo_children():
            widget.destroy()
        for widget in self.annotations_container.winfo_children():
            widget.destroy()
        
        self.annotations = {}
        self.edited_annotations = {}
        self.current_video = None
        self.current_annotation_index = 0
        self.has_edits = False
        
        # Select and load new file
        if self.select_json_file():
            self.load_annotations()
        else:
            messagebox.showinfo("Cancelled", "No new file loaded. Previous data cleared.")
    
    def dump_all_clips(self):
        """Dump all video clips based on current annotations"""
        import subprocess
        from tkinter import filedialog
        
        if not self.edited_annotations:
            messagebox.showerror("Error", "No annotations loaded")
            return
        
        if not self.videos_path or not self.videos_path.exists():
            messagebox.showerror("Error", f"Videos folder not found: {self.videos_path}")
            return
        
        # Group annotations by class first to show available classes
        clips_by_class = {}
        for video_name, annotations in self.edited_annotations.items():
            for ann in annotations:
                cls = self.get_annotation_class(ann['Code'])
                if cls not in clips_by_class:
                    clips_by_class[cls] = []
                clips_by_class[cls].append((video_name, ann))
        
        # Create class selection dialog
        selection_window = tk.Toplevel(self.root)
        selection_window.title("Select Classes to Export")
        selection_window.geometry("400x500")
        selection_window.transient(self.root)
        selection_window.grab_set()
        
        ttk.Label(selection_window, text="Select classes to export as clips:", 
                  font=("Arial", 12, "bold")).pack(pady=10)
        
        # Frame for checkboxes
        checkbox_frame = ttk.Frame(selection_window)
        checkbox_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Create scrollable area
        canvas = tk.Canvas(checkbox_frame)
        scrollbar = ttk.Scrollbar(checkbox_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Create checkboxes for each class
        class_vars = {}
        for cls in sorted(clips_by_class.keys()):
            var = tk.BooleanVar(value=True)
            class_vars[cls] = var
            clip_count = len(clips_by_class[cls])
            cb = ttk.Checkbutton(
                scrollable_frame, 
                text=f"{cls} ({clip_count} clips)",
                variable=var
            )
            cb.pack(anchor=tk.W, padx=10, pady=2)
        
        # Button frame
        button_frame = ttk.Frame(selection_window)
        button_frame.pack(fill=tk.X, padx=20, pady=10)
        
        ttk.Button(button_frame, text="Select All", 
                   command=lambda: [var.set(True) for var in class_vars.values()]).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Deselect All", 
                   command=lambda: [var.set(False) for var in class_vars.values()]).pack(side=tk.LEFT, padx=5)
        
        # Result variable
        proceed = [False]
        
        def on_ok():
            proceed[0] = True
            selection_window.destroy()
        
        def on_cancel():
            selection_window.destroy()
        
        # OK/Cancel buttons
        action_frame = ttk.Frame(selection_window)
        action_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
        
        ttk.Button(action_frame, text="Export Selected", command=on_ok).pack(side=tk.RIGHT, padx=5)
        ttk.Button(action_frame, text="Cancel", command=on_cancel).pack(side=tk.RIGHT, padx=5)
        
        # Wait for dialog to close
        self.root.wait_window(selection_window)
        
        if not proceed[0]:
            return
        
        # Filter to only selected classes
        selected_classes = [cls for cls, var in class_vars.items() if var.get()]
        
        if not selected_classes:
            messagebox.showwarning("No Selection", "No classes selected for export.")
            return
        
        clips_by_class = {cls: clips_by_class[cls] for cls in selected_classes}
        
        # Calculate total clips for selected classes
        total_clips = sum(len(clips) for clips in clips_by_class.values())
        
        # Ask user to confirm
        result = messagebox.askyesno(
            "Confirm Clip Dump",
            f"This will create {total_clips} video clips from {len(selected_classes)} selected classes.\n\n"
            f"Videos path: {self.videos_path}\n"
            f"Output will be created in folders like 'corrected_CLASS_Clips'\n\n"
            f"Selected classes: {', '.join(selected_classes)}\n\n"
            f"This may take several minutes. Continue?"
        )
        
        if not result:
            return
        
        # Determine output base directory (parent of videos_path)
        output_base = self.videos_path.parent if self.videos_path.parent else self.videos_path
        
        # Create output directories
        output_dirs = {}
        for cls in clips_by_class.keys():
            output_dir = output_base / f"corrected_{cls}_Clips"
            output_dirs[cls] = output_dir
            try:
                output_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create directory {output_dir}: {e}")
                return
        
        # Process clips
        total_processed = 0
        total_failed = 0
        
        # Create progress window
        progress_window = tk.Toplevel(self.root)
        progress_window.title("Dumping Clips")
        progress_window.geometry("500x150")
        progress_window.transient(self.root)
        
        progress_label = ttk.Label(progress_window, text="Processing clips...", font=("Arial", 10))
        progress_label.pack(pady=10)
        
        progress_bar = ttk.Progressbar(progress_window, length=400, mode='determinate')
        progress_bar.pack(pady=10)
        progress_bar['maximum'] = total_clips
        
        status_label = ttk.Label(progress_window, text="", font=("Arial", 9))
        status_label.pack(pady=5)
        
        progress_window.update()
        
        # Process each class
        for cls, clips in clips_by_class.items():
            output_dir = output_dirs[cls]
            clip_index = 0
            
            for video_name, ann in clips:
                # Update progress
                progress_label.config(text=f"Processing {cls}: {clip_index + 1}/{len(clips)}")
                status_label.config(text=f"{video_name} - {ann['Code']}")
                progress_bar['value'] = total_processed
                progress_window.update()
                
                # Get video path
                video_path = self.videos_path / video_name
                if not video_path.exists():
                    print(f"Warning: Video not found: {video_path}")
                    total_failed += 1
                    total_processed += 1
                    continue
                
                # Get clip parameters with maximum time precision
                # Use original time format (HH:MM:SS.mmm) for precision
                start_time = ann['Start time']
                end_time = ann['End time']
                
                # Output file
                output_file = output_dir / f"clip_{clip_index}_{ann['Code']}_{video_name}"
                
                # Run ffmpeg with precise clipping (decode and re-encode)
                # Use -ss after -i for frame-accurate seeking with full decode/re-encode
                try:
                    subprocess.run(
                        [
                            "ffmpeg", "-y",
                            "-i", str(video_path),
                            "-ss", start_time,
                            "-to", end_time,
                            "-avoid_negative_ts", "make_zero",
                            str(output_file)
                        ],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=True
                    )
                    clip_index += 1
                except subprocess.CalledProcessError as e:
                    print(f"Error processing clip {clip_index} from {video_name}: {e}")
                    total_failed += 1
                
                total_processed += 1
        
        # Final update
        progress_bar['value'] = total_clips
        progress_window.destroy()
        
        # Show summary
        summary = f"Clip dump complete!\n\n"
        summary += f"Total clips processed: {total_processed}\n"
        summary += f"Successful: {total_processed - total_failed}\n"
        if total_failed > 0:
            summary += f"Failed: {total_failed}\n"
        summary += f"\nOutput location: {output_base}\n\n"
        summary += "Folders created:\n"
        for cls, output_dir in output_dirs.items():
            clip_count = len(clips_by_class[cls])
            summary += f"  - {output_dir.name} ({clip_count} clips)\n"
        
        messagebox.showinfo("Dump Complete", summary)
    
    def export_json(self):
        """Export edited annotations to a new JSON file"""
        from tkinter import filedialog
        
        # Default filename with timestamp
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"annotations_edited_{timestamp}.json"
        
        # Determine initial directory
        if self.json_path:
            initial_dir = self.json_path.parent
        elif self.base_path:
            initial_dir = self.base_path
        else:
            initial_dir = Path.cwd()
        
        # Ask for save location
        filepath = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile=default_name,
            initialdir=initial_dir
        )
        
        if not filepath:
            return  # User cancelled
        
        try:
            with open(filepath, 'w') as f:
                json.dump(self.edited_annotations, f, indent=4)
            
            messagebox.showinfo("Export Successful", 
                              f"Annotations exported to:\n{filepath}")
            self.has_edits = False
        except Exception as e:
            messagebox.showerror("Export Failed", f"Failed to export annotations:\n{str(e)}")
    
    def update_displayed_annotations(self):
        """Update the display when checkboxes change"""
        video_annotations = self.edited_annotations.get(self.current_video, [])
        visible_count = 0
        
        # Show/hide annotations based on class selection
        for frame, label, idx, ann in self.annotation_items:
            if self.is_annotation_visible(ann):
                frame.pack(fill=tk.X, padx=5, pady=2)
                visible_count += 1
            else:
                frame.pack_forget()
        
        self.annotation_count_label.config(
            text=f"{visible_count}/{len(video_annotations)} annotations visible"
        )
    
    def select_all_classes(self):
        """Select all class checkboxes"""
        for var in self.class_checkboxes.values():
            var.set(True)
        self.update_displayed_annotations()
    
    def deselect_all_classes(self):
        """Deselect all class checkboxes"""
        for var in self.class_checkboxes.values():
            var.set(False)
        self.update_displayed_annotations()
    
    def time_to_seconds(self, time_str):
        """Convert time string HH:MM:SS.mmm to seconds"""
        parts = time_str.split(':')
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
        return hours * 3600 + minutes * 60 + seconds
    
    def load_clip(self, annotation_index):
        """Load a specific annotation clip"""
        self.stop_video()
        
        # Wait for video thread to finish before releasing capture
        if self.video_thread and self.video_thread.is_alive():
            time.sleep(0.2)  # Give thread time to exit playback loop
        
        if not self.current_video:
            return
            
        video_annotations = self.edited_annotations.get(self.current_video, [])
        if annotation_index >= len(video_annotations):
            return
            
        annotation = video_annotations[annotation_index]
        video_path = self.videos_path / self.current_video
        
        if not video_path.exists():
            messagebox.showerror("Error", f"Video file not found: {video_path}")
            return
        
        # Open video - release previous capture first
        if self.cap:
            self.cap.release()
            self.cap = None
            time.sleep(0.1)  # Brief pause after release
            
        self.cap = cv2.VideoCapture(str(video_path))
        
        # Get start frame (1 second before annotation start)
        start_time = max(0, self.time_to_seconds(annotation["Start time"]) - 1.0)
        fps = self.cap.get(cv2.CAP_PROP_FPS)
        start_frame = int(start_time * fps)
        
        # Set to start frame
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        
        # Display first frame
        ret, frame = self.cap.read()
        if ret:
            self.display_frame(frame, annotation["Code"])
        
        # Update clip info
        self.clip_info_label.config(
            text=f"Clip {annotation_index + 1}/{len(video_annotations)} - {annotation['Code']} "
                 f"({annotation['Duration (s)']}s)"
        )
        
        # Update edit fields
        self.edit_code_var.set(annotation['Code'])
        self.edit_start_var.set(annotation['Start time'])
        self.edit_end_var.set(annotation['End time'])
        self.edit_duration_var.set(f"{annotation['Duration (s)']}s")
        self.edit_status_label.config(text="")
        
        # Setup timeline
        self.timeline_start = self.time_to_seconds(annotation['Start time'])
        self.timeline_end = self.time_to_seconds(annotation['End time'])
        # Timeline shows -1s before to +1s after (fixed window)
        self.clip_start = max(0, self.timeline_start - 1.0)
        clip_end = self.timeline_end + 1.0
        self.timeline_duration = clip_end - self.clip_start
        self.playback_position = 0
        self.draw_timeline()
    
    def display_frame(self, frame, annotation_code=""):
        """Display a frame on the canvas"""
        # Add annotation text to frame
        if annotation_code:
            cv2.putText(frame, annotation_code, (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        
        # Convert BGR to RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Resize to fit canvas
        canvas_width = self.video_canvas.winfo_width()
        canvas_height = self.video_canvas.winfo_height()
        
        if canvas_width > 1 and canvas_height > 1:
            h, w = frame_rgb.shape[:2]
            aspect = w / h
            
            if canvas_width / canvas_height > aspect:
                new_height = canvas_height
                new_width = int(new_height * aspect)
            else:
                new_width = canvas_width
                new_height = int(new_width / aspect)
            
            frame_rgb = cv2.resize(frame_rgb, (new_width, new_height))
        
        # Convert to ImageTk
        img = Image.fromarray(frame_rgb)
        photo = ImageTk.PhotoImage(image=img)
        
        # Display on canvas
        self.video_canvas.delete("all")
        self.video_canvas.create_image(
            self.video_canvas.winfo_width() // 2,
            self.video_canvas.winfo_height() // 2,
            image=photo, anchor=tk.CENTER
        )
        self.video_canvas.image = photo
    
    def toggle_play(self):
        """Toggle play/pause"""
        if self.playing:
            self.pause_video()
        else:
            self.play_video()
    
    def play_video(self):
        """Play the current annotation clip"""
        if not self.cap or not self.current_video:
            return
        
        self.playing = True
        self.play_button.config(text="⏸ Pause")
        
        if self.video_thread and self.video_thread.is_alive():
            return
        
        self.video_thread = threading.Thread(target=self._play_loop, daemon=True)
        self.video_thread.start()
    
    def pause_video(self):
        """Pause video playback"""
        self.playing = False
        self.play_button.config(text="▶ Play Clip")
    
    def stop_video(self):
        """Stop video playback"""
        self.playing = False
        self.play_button.config(text="▶ Play Clip")
        self.playback_position = 0
        self.draw_timeline()
    
    def step_back_frame(self):
        """Step back one frame"""
        if not self.cap or not self.current_video:
            return
        
        # Pause if playing
        if self.playing:
            self.pause_video()
        
        # Get current position and step back
        current_pos = self.cap.get(cv2.CAP_PROP_POS_FRAMES)
        new_pos = max(0, current_pos - 2)  # -2 because read() advances position
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, new_pos)
        
        # Read and display frame
        ret, frame = self.cap.read()
        if ret:
            video_annotations = self.edited_annotations.get(self.current_video, [])
            if self.current_annotation_index < len(video_annotations):
                annotation = video_annotations[self.current_annotation_index]
                self.display_frame(frame, annotation["Code"])
                
                # Update playback position and timeline
                fps = self.cap.get(cv2.CAP_PROP_FPS)
                current_time = self.cap.get(cv2.CAP_PROP_POS_FRAMES) / fps
                self.playback_position = current_time - self.clip_start
                self.draw_timeline()
    
    def step_forward_frame(self):
        """Step forward one frame"""
        if not self.cap or not self.current_video:
            return
        
        # Pause if playing
        if self.playing:
            self.pause_video()
        
        # Read and display next frame
        ret, frame = self.cap.read()
        if ret:
            video_annotations = self.edited_annotations.get(self.current_video, [])
            if self.current_annotation_index < len(video_annotations):
                annotation = video_annotations[self.current_annotation_index]
                self.display_frame(frame, annotation["Code"])
                
                # Update playback position and timeline
                fps = self.cap.get(cv2.CAP_PROP_FPS)
                current_time = self.cap.get(cv2.CAP_PROP_POS_FRAMES) / fps
                self.playback_position = current_time - self.clip_start
                self.draw_timeline()
        else:
            # If at end, loop back to start of clip
            video_annotations = self.edited_annotations.get(self.current_video, [])
            if self.current_annotation_index < len(video_annotations):
                annotation = video_annotations[self.current_annotation_index]
                start_time = max(0, self.time_to_seconds(annotation["Start time"]) - 1.0)
                fps = self.cap.get(cv2.CAP_PROP_FPS)
                start_frame = int(start_time * fps)
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
                ret, frame = self.cap.read()
                if ret:
                    self.display_frame(frame, annotation["Code"])
                    # Update playback position and timeline
                    current_time = self.cap.get(cv2.CAP_PROP_POS_FRAMES) / fps
                    self.playback_position = current_time - self.clip_start
                    self.draw_timeline()
    
    def _play_loop(self):
        """Video playback loop (runs in separate thread)"""
        if not self.current_video or not self.cap:
            return
            
        video_annotations = self.edited_annotations.get(self.current_video, [])
        if self.current_annotation_index >= len(video_annotations):
            return
            
        annotation = video_annotations[self.current_annotation_index]
        # Start 1 second before, end 1 second after
        start_time = max(0, self.time_to_seconds(annotation["Start time"]) - 1.0)
        end_time = self.time_to_seconds(annotation["End time"]) + 1.0
        duration = end_time - start_time
        
        try:
            fps = self.cap.get(cv2.CAP_PROP_FPS)
            frame_delay = 1.0 / 25.0  # Fixed 25 FPS playback
            start_frame = int(start_time * fps)
            
            while self.playing and self.cap:
                ret, frame = self.cap.read()
                if not ret or not self.cap:
                    # Restart from beginning of clip
                    if self.cap:
                        self.cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
                    continue
                
                # Check if we've reached the end of the clip
                current_pos = self.cap.get(cv2.CAP_PROP_POS_FRAMES)
                current_time = current_pos / fps
                video_start = max(0, self.time_to_seconds(annotation["Start time"]) - 1.0)
                elapsed = current_time - video_start
                
                if elapsed > duration:
                    # Loop back to start of clip
                    if self.cap:
                        self.cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
                    continue
                
                # Update playback position
                self.playback_position = elapsed
                self.root.after(0, self.draw_timeline)
                
                # Display frame
                self.root.after(0, lambda f=frame.copy(), c=annotation["Code"]: 
                              self.display_frame(f, c))
                
                # Wait for next frame
                time.sleep(frame_delay)
        except Exception as e:
            print(f"Playback error: {e}")
        finally:
            self.playing = False
            self.root.after(0, lambda: self.play_button.config(text="▶ Play Clip"))
    
    def next_annotation(self):
        """Go to next visible annotation"""
        if not self.current_video:
            return
            
        video_annotations = self.edited_annotations.get(self.current_video, [])
        
        # Find next visible annotation
        for i in range(self.current_annotation_index + 1, len(video_annotations)):
            if self.is_annotation_visible(video_annotations[i]):
                self.current_annotation_index = i
                self.load_clip(i)
                self.highlight_current_annotation()
                return
    
    def previous_annotation(self):
        """Go to previous visible annotation"""
        if not self.current_video:
            return
            
        video_annotations = self.edited_annotations.get(self.current_video, [])
        
        # Find previous visible annotation
        for i in range(self.current_annotation_index - 1, -1, -1):
            if self.is_annotation_visible(video_annotations[i]):
                self.current_annotation_index = i
                self.load_clip(i)
                self.highlight_current_annotation()
                return
    
    def draw_timeline(self):
        """Draw the interactive timeline with draggable knobs"""
        self.timeline_canvas.delete("all")
        
        if self.timeline_duration <= 0:
            return
        
        canvas_width = self.timeline_canvas.winfo_width()
        canvas_height = self.timeline_canvas.winfo_height()
        
        if canvas_width <= 1:
            canvas_width = 800  # Default width
        
        padding = 40
        timeline_width = canvas_width - 2 * padding
        timeline_y = canvas_height // 2
        
        # Draw timeline background
        self.timeline_canvas.create_line(padding, timeline_y, canvas_width - padding, timeline_y, 
                                        fill="gray", width=2)
        
        # Calculate pixel positions
        def time_to_pixel(time_seconds):
            relative_time = time_seconds - self.clip_start
            fraction = relative_time / self.timeline_duration
            return padding + fraction * timeline_width
        
        start_x = time_to_pixel(self.timeline_start)
        end_x = time_to_pixel(self.timeline_end)
        
        # Draw annotation range (green bar)
        self.timeline_canvas.create_rectangle(start_x, timeline_y - 8, end_x, timeline_y + 8,
                                             fill="#90EE90", outline="#228B22", width=2, tags="range")
        
        # Draw playback position (red line) - show during playback or when seeking
        if self.playback_position > 0:
            playback_time = self.clip_start + self.playback_position
            playback_x = time_to_pixel(playback_time)
            self.timeline_canvas.create_line(playback_x, 10, playback_x, canvas_height - 10,
                                           fill="red", width=3, tags="playhead")
            # Draw a triangle at the top for easier visibility
            triangle_size = 6
            self.timeline_canvas.create_polygon(
                playback_x, 10,
                playback_x - triangle_size, 10 - triangle_size,
                playback_x + triangle_size, 10 - triangle_size,
                fill="red", outline="darkred", width=1, tags="playhead"
            )
        
        # Draw start knob (circle)
        knob_radius = 8
        self.timeline_canvas.create_oval(start_x - knob_radius, timeline_y - knob_radius,
                                        start_x + knob_radius, timeline_y + knob_radius,
                                        fill="#4CAF50", outline="black", width=2, tags="start_knob")
        self.timeline_canvas.create_text(start_x, timeline_y - 20, text="Start", 
                                        fill="black", font=("Arial", 9, "bold"))
        
        # Draw end knob (circle)
        self.timeline_canvas.create_oval(end_x - knob_radius, timeline_y - knob_radius,
                                        end_x + knob_radius, timeline_y + knob_radius,
                                        fill="#F44336", outline="black", width=2, tags="end_knob")
        self.timeline_canvas.create_text(end_x, timeline_y - 20, text="End",
                                        fill="black", font=("Arial", 9, "bold"))
        
        # Draw time labels
        self.timeline_canvas.create_text(padding, canvas_height - 5, 
                                        text=self.seconds_to_time(self.clip_start),
                                        anchor=tk.W, font=("Arial", 8))
        self.timeline_canvas.create_text(canvas_width - padding, canvas_height - 5,
                                        text=self.seconds_to_time(self.clip_start + self.timeline_duration),
                                        anchor=tk.E, font=("Arial", 8))
        
        # Update duration display
        duration = self.timeline_end - self.timeline_start
        self.edit_start_var.set(self.seconds_to_time(self.timeline_start))
        self.edit_end_var.set(self.seconds_to_time(self.timeline_end))
        self.edit_duration_var.set(f"{duration:.2f}s")
    
    def on_timeline_click(self, event):
        """Handle mouse click on timeline"""
        canvas_width = self.timeline_canvas.winfo_width()
        padding = 40
        timeline_width = canvas_width - 2 * padding
        
        def time_to_pixel(time_seconds):
            relative_time = time_seconds - self.clip_start
            fraction = relative_time / self.timeline_duration
            return padding + fraction * timeline_width
        
        start_x = time_to_pixel(self.timeline_start)
        end_x = time_to_pixel(self.timeline_end)
        
        # Check if clicking on start or end knob
        knob_threshold = 12
        if abs(event.x - start_x) < knob_threshold:
            self.dragging_knob = 'start'
        elif abs(event.x - end_x) < knob_threshold:
            self.dragging_knob = 'end'
        else:
            # Clicking on timeline - seek to that position
            self.dragging_knob = 'seek'
            self.seek_to_timeline_position(event.x)
    
    def on_timeline_drag(self, event):
        """Handle mouse drag on timeline"""
        if self.dragging_knob is None:
            return
        
        # Pause playback while dragging
        if self.playing:
            self.pause_video()
        
        canvas_width = self.timeline_canvas.winfo_width()
        padding = 40
        timeline_width = canvas_width - 2 * padding
        
        # Convert pixel position to time
        pixel_pos = max(padding, min(event.x, canvas_width - padding))
        fraction = (pixel_pos - padding) / timeline_width
        new_time = self.clip_start + fraction * self.timeline_duration
        
        # Update the appropriate knob or seek position
        if self.dragging_knob == 'start':
            # Start cannot be after end
            self.timeline_start = min(new_time, self.timeline_end - 0.1)
        elif self.dragging_knob == 'end':
            # End cannot be before start
            self.timeline_end = max(new_time, self.timeline_start + 0.1)
        elif self.dragging_knob == 'seek':
            # Seek to the dragged position
            self.seek_to_timeline_position(event.x)
            return
        
        # Redraw timeline
        self.draw_timeline()
    
    def on_timeline_release(self, event):
        """Handle mouse release on timeline"""
        self.dragging_knob = None
    
    def on_timeline_motion(self, event):
        """Handle mouse motion over timeline to change cursor"""
        if self.dragging_knob:
            return  # Don't change cursor while dragging
        
        canvas_width = self.timeline_canvas.winfo_width()
        padding = 40
        timeline_width = canvas_width - 2 * padding
        
        def time_to_pixel(time_seconds):
            relative_time = time_seconds - self.clip_start
            fraction = relative_time / self.timeline_duration if self.timeline_duration > 0 else 0
            return padding + fraction * timeline_width
        
        start_x = time_to_pixel(self.timeline_start)
        end_x = time_to_pixel(self.timeline_end)
        
        # Check if hovering over start or end knob
        knob_threshold = 12
        if abs(event.x - start_x) < knob_threshold or abs(event.x - end_x) < knob_threshold:
            self.timeline_canvas.config(cursor="hand2")
        else:
            self.timeline_canvas.config(cursor="crosshair")
    
    def adjust_knob(self, knob_type, delta_seconds):
        """Adjust the start or end knob by the specified number of seconds"""
        if not self.current_video:
            return
        
        video_annotations = self.edited_annotations.get(self.current_video, [])
        if self.current_annotation_index >= len(video_annotations):
            return
        
        # Pause if playing
        if self.playing:
            self.pause_video()
        
        # Adjust the appropriate knob
        if knob_type == 'start':
            new_start = self.timeline_start + delta_seconds
            # Start cannot be negative or after end
            self.timeline_start = max(0, min(new_start, self.timeline_end - 0.1))
        elif knob_type == 'end':
            new_end = self.timeline_end + delta_seconds
            # End cannot be before start
            self.timeline_end = max(self.timeline_start + 0.1, new_end)
        
        # Seek to the adjusted position to show the frame
        fps = self.cap.get(cv2.CAP_PROP_FPS)
        if knob_type == 'start':
            target_time = self.timeline_start
        else:
            target_time = self.timeline_end
        
        target_frame = int(target_time * fps)
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
        
        ret, frame = self.cap.read()
        if ret:
            annotation = video_annotations[self.current_annotation_index]
            self.display_frame(frame, annotation["Code"])
            
            # Update playback position relative to the fixed clip_start
            current_time = self.cap.get(cv2.CAP_PROP_POS_FRAMES) / fps
            self.playback_position = current_time - self.clip_start
        
        # Redraw timeline with updated position
        self.draw_timeline()
    
    def seek_to_timeline_position(self, pixel_x):
        """Seek video to the time position at the given pixel coordinate"""
        if not self.cap or not self.current_video:
            return
        
        canvas_width = self.timeline_canvas.winfo_width()
        padding = 40
        timeline_width = canvas_width - 2 * padding
        
        # Convert pixel to time
        pixel_pos = max(padding, min(pixel_x, canvas_width - padding))
        fraction = (pixel_pos - padding) / timeline_width
        
        target_time = self.clip_start + fraction * self.timeline_duration
        
        # Set video to that position
        fps = self.cap.get(cv2.CAP_PROP_FPS)
        target_frame = int(target_time * fps)
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
        
        # Update playback position for display
        self.playback_position = target_time - self.clip_start
        
        # Read and display the frame
        ret, frame = self.cap.read()
        if ret:
            video_annotations = self.edited_annotations.get(self.current_video, [])
            if self.current_annotation_index < len(video_annotations):
                annotation = video_annotations[self.current_annotation_index]
                self.display_frame(frame, annotation["Code"])
        
        # Update timeline to show new position
        self.draw_timeline()
    
    def cleanup(self):
        """Cleanup resources"""
        self.playing = False
        
        # Wait for video thread to finish
        if self.video_thread and self.video_thread.is_alive():
            time.sleep(0.2)  # Give thread time to finish
        
        if self.cap:
            self.cap.release()
            self.cap = None


def main():
    root = tk.Tk()
    app = AnnotationViewer(root)
    root.protocol("WM_DELETE_WINDOW", lambda: [app.cleanup(), root.destroy()])
    root.mainloop()


if __name__ == "__main__":
    main()
