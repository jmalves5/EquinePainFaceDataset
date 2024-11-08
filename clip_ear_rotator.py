# This script will operate on the original data of Equine Pain face and extract only the Ear Rotator instances.
import ffmpeg
import json
import os
import math
import subprocess

# Define base folders
base_path = "/home/joao/workspace/EquinePainFaceDataset/"
videos_path = base_path + "CleanAnEquinePainFaceDataset/videos/"
annotations_file_path = base_path + "CleanAnEquinePainFaceDataset/JSONAnnotations/annotations.json" 
FPS=46.875

# Create output folder
output_dir = base_path + "CleanAnEquinePainFaceDataset/EAD_104_Clips"

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
    i = 0
    # Print the data of dictionary
    for video in list_video_names:
        # print("\n")
        # print(video)
        for action_unit in video_data[video]:
            if 'EAD104' in action_unit['Code']:
                # print("\n")
                # print(action_unit['Code'])
                # print(action_unit['Start time'])
                # print(action_unit['End time'])

                # Convert start time to frames
                action_start = str(get_sec(action_unit['Start time'])-1)
                action_end = str(get_sec(action_unit['End time']))
                duration = str(int(math.ceil(action_unit['Duration (s)']))+1)
                # Clip the file
                input_file_path = videos_path + video

                subprocess.run(["ffmpeg", "-ss", action_start, "-i", input_file_path, "-c", "copy", "-t", duration, f"{output_dir}/clip_{i}_{action_unit['Code']}_{video}"])
                # create gifs: ffmpeg -i CleanAnEquinePainFaceDataset/EAD_104_Clips/clip_2_EAD104R_S5.mp4  -r 30   -vf scale=1080:-1   -ss 00:00:00 -to 00:00:02   blink.gif

                i = i + 1


        
    
