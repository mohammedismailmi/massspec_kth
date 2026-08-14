import os

# Define your input file path (can be a relative path or an absolute path)
isi_file_path = "/Users/mi/Downloads/Pfeiffer Vacuum/data/001-22-2026/650C-1%CH4.isi"

try:
    # 1. Get the absolute path of the input file
    absolute_isi_path = os.path.abspath(isi_file_path)
    
    # 2. Extract the directory name from that path
    file_directory = os.path.dirname(absolute_isi_path)
    
    # 3. Create the output file path in that same directory
    txt_file_path = os.path.join(file_directory, "650C-1%CH4_isi.txt")

    # 4. Open the .isi file to read and the .txt file to write
    with open(absolute_isi_path, "r", encoding="utf-8") as isi_file:
        content = isi_file.read()
        
    with open(txt_file_path, "w", encoding="utf-8") as txt_file:
        txt_file.write(content)
        
    print(f"Success! Saved output to: {txt_file_path}")

except FileNotFoundError:
    print(f"Error: The file '{isi_file_path}' was not found.")
