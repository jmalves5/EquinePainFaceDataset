import pandas as pd
import json

film_data = []

full_json_dict = {}

# Ranges are built to start at 0, this is how you get a range from 1-12
for i in range(1, 12+1):
    single_data = pd.read_excel(f"CleanAnEquinePainFaceDataset/XLSAnnotations/S{i}.xlsx")
    film_data.append((f"S{i}.mp4", single_data))

for (name, data) in film_data:
    # Create film annotation list
    annot_list = []
    for i in range(0, len(data)):
        # Append annotation to film list
        annot_list.append(
            {
                "Code": data["Code"][i],
                "Duration (s)": data["Duration (s)"][i],
                "Start time": data["Start time"][i],
                "End time": data["End time"][i],
            }
        )
    
    # Update JSON annotation with film name and film annotation list
    full_json_dict[name] = annot_list
    

with open('CleanAnEquinePainFaceDataset/JSONAnnotations/annotations.json', 'w') as fp:
    json.dump(full_json_dict, fp, indent=4)