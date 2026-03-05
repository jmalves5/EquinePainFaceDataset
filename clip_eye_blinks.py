# This script will operate on the original data of Equine Pain face and extract eye blink instances (AU47, AU145, AU143).
import ffmpeg
import json
import os
import math
import subprocess

# Define base folders
base_path = "/home/joao/workspace/EquinePainFaceDataset/"
videos_path = base_path + "CleanAnEquinePainFaceDataset/videos/"
annotations_file_path = base_path + "CleanAnEquinePainFaceDataset/JSONAnnotations/corrected_blink_annotations.json" 
FPS=25

# Create output folders for each action unit
output_dir_au47 = base_path + "CleanAnEquinePainFaceDataset/corrected_AU_47_Clips"
output_dir_au145 = base_path + "CleanAnEquinePainFaceDataset/corrected_AU_145_Clips"
output_dir_au143 = base_path + "CleanAnEquinePainFaceDataset/corrected_AU_143_Clips"

# Create all output directories
for output_dir in [output_dir_au47, output_dir_au145, output_dir_au143]:
    try:
        os.makedirs(output_dir, exist_ok=True)
    except FileExistsError:
        print(f"Directory '{output_dir}' already exists.")
    except PermissionError:
        print(f"Permission denied: Unable to create '{output_dir}'.")
    except Exception as e:
        print(f"An error occurred: {e}")

def get_sec(time_str):
    """Get seconds from time."""
    h, m, s = time_str.split(':')
    return int(h) * 3600 + int(m) * 60 + int(math.ceil(float(s)))

# Find list of videos
list_video_names = os.listdir(videos_path)

# Opening JSON file
with open(annotations_file_path) as json_file:
    video_data = json.load(json_file)
    i_au47 = 0
    i_au145 = 0
    i_au143 = 0
    
    # Print the data of dictionary
    for video in list_video_names:
        for action_unit in video_data[video]:
            code = action_unit['Code']
            
            # Check for AU47
            if 'AU47' in code:
                # Use precise time format for frame-accurate clipping
                start_time = action_unit['Start time']
                end_time = action_unit['End time']
                # Clip the file
                input_file_path = videos_path + video
                
                # Use -ss after -i for frame-accurate seeking with full decode/re-encode
                subprocess.run(["ffmpeg", "-y", "-i", input_file_path, "-ss", start_time, "-to", end_time, "-avoid_negative_ts", "make_zero", f"{output_dir_au47}/clip_{i_au47}_{code}_{video}"])
                i_au47 = i_au47 + 1
            
            # Check for AU145
            if 'AU145' in code:
                # Use precise time format for frame-accurate clipping
                start_time = action_unit['Start time']
                end_time = action_unit['End time']
                # Clip the file
                input_file_path = videos_path + video
                
                # Use -ss after -i for frame-accurate seeking with full decode/re-encode
                subprocess.run(["ffmpeg", "-y", "-i", input_file_path, "-ss", start_time, "-to", end_time, "-avoid_negative_ts", "make_zero", f"{output_dir_au145}/clip_{i_au145}_{code}_{video}"])
                i_au145 = i_au145 + 1
            
            # Check for AU143
            if 'AU143' in code:
                # Use precise time format for frame-accurate clipping
                start_time = action_unit['Start time']
                end_time = action_unit['End time']
                # Clip the file
                input_file_path = videos_path + video
                
                # Use -ss after -i for frame-accurate seeking with full decode/re-encode
                subprocess.run(["ffmpeg", "-y", "-i", input_file_path, "-ss", start_time, "-to", end_time, "-avoid_negative_ts", "make_zero", f"{output_dir_au143}/clip_{i_au143}_{code}_{video}"])
                i_au143 = i_au143 + 1

print(f"Extraction complete!")
print(f"AU47 clips: {i_au47}")
print(f"AU145 clips: {i_au145}")
print(f"AU143 clips: {i_au143}")
