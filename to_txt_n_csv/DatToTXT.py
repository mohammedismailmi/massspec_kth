import os

# Define your input file path (can be a relative path or an absolute path)
dat_file_path = "100PPMCH4-TR1, Position 1, RGA PrismaPro A 200 47505932, 002-11-2025 16'54'02.dat"

try:
    # 1. Get the absolute path of the input file
    absolute_dat_path = os.path.abspath(dat_file_path)
    
    # 2. Extract the directory name from that path
    file_directory = os.path.dirname(absolute_dat_path)
    
    # 3. Create the output file path in that same directory
    txt_file_path = os.path.join(file_directory, "650C-1%CH4_dat.txt")

    # 4. Open the .dat file to read and the .txt file to write
    # Note: If the file has non-text binary data, use 'rb' and 'wb' modes without encoding.
    with open(absolute_dat_path, "r", encoding="utf-8") as dat_file:
        content = dat_file.read()
        
    with open(txt_file_path, "w", encoding="utf-8") as txt_file:
        txt_file.write(content)
        
    print(f"Success! Saved output to: {txt_file_path}")

except FileNotFoundError:
    print(f"Error: The file '{dat_file_path}' was not found.")
