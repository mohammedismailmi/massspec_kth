import os

# Define your binary input file path
bin_file_path = "/Users/mi/Downloads/Pfeiffer Vacuum/data/001-22-2026/650C-1%CH4.bin"

try:
    # 1. Get the absolute path of the input file
    absolute_bin_path = os.path.abspath(bin_file_path)
    
    # 2. Extract the directory name from that path
    file_directory = os.path.dirname(absolute_bin_path)
    
    # 3. Create the output file path in that same directory
    txt_file_path = os.path.join(file_directory, "650C-1%CH4_bin.txt")

    # 4. Open the .bin file to read as bytes ('rb')
    with open(absolute_bin_path, "rb") as bin_file:
        content = bin_file.read()
        
    # 5. Open the .txt file to write text ('w')
    with open(txt_file_path, "w", encoding="utf-8") as txt_file:
        # Convert raw binary bytes to a readable string format
        txt_file.write(str(content))
        
    print(f"Success! Saved output to: {txt_file_path}")

except FileNotFoundError:
    print(f"Error: The file '{bin_file_path}' was not found.")
